import json
from datetime import datetime, timezone

import yfinance as yf

from day_trading_signals import (
    get_intraday_history, get_opening_range, get_gap_info, get_vwap_position,
    get_inside_bar_setup, get_flag_pattern, get_intraday_volume_signal,
    get_intraday_candlestick_patterns,
)
from trade_decision_engine import DAY_STRATEGIES, CONFIDENCE_THRESHOLD, MIN_REWARD_RISK_RATIO, format_track_record_context
from fact_checker import strip_json_fence
from jarvis import client, MODEL
from ai_cost_tracker import track_ai_usage


def gather_day_signals(ticker: str) -> dict:
    """Cheap signals only — no NewsAPI, no Claude. Fetches intraday history once and
    reuses it across every intraday-based signal (unlike the swing engine, where each
    signal source fetches its own daily history — intraday data is a heavier fetch and
    this runs on a much faster cadence, so avoiding redundant calls matters more here)."""
    intraday = get_intraday_history(ticker)
    daily = yf.Ticker(ticker).history(period="1mo")
    return {
        "_intraday_empty": intraday.empty,
        "opening_range": get_opening_range(intraday),
        "gap": get_gap_info(ticker),
        "vwap": get_vwap_position(intraday),
        "inside_bar": get_inside_bar_setup(daily),
        "flag": get_flag_pattern(intraday),
        "volume": get_intraday_volume_signal(intraday),
        "candlestick_patterns": get_intraday_candlestick_patterns(intraday),
    }


def passes_day_prefilter(signals: dict) -> bool:
    """Cheap gate — is there an actual actionable day-trading setup here, or just an
    ordinary quiet session? No point spending a Claude call otherwise."""
    if signals.get("_intraday_empty"):
        return False

    opening_range = signals.get("opening_range")
    gap = signals.get("gap")
    flag = signals.get("flag")
    inside_bar = signals.get("inside_bar")

    has_orb = bool(opening_range and opening_range["breakout"] != "Inside")
    has_gap = bool(gap and abs(gap["gap_pct"]) >= 0.5)
    has_flag = flag is not None
    has_inside_bar = bool(inside_bar and inside_bar["is_inside_bar"])

    return has_orb or has_gap or has_flag or has_inside_bar


def evaluate_day_trade(ticker: str, signals: dict, market_sentiment: str, portfolio_tickers: list[str]) -> dict | None:
    """One Claude call combining day-trading-specific signals into a final decision.
    Deliberately no NewsAPI call — day-trade setups lean on price action (ORB, gap,
    VWAP, flag, candlestick, volume), not a fresh news fetch, keeping this track's API
    cost low despite its much faster scan cadence than the swing track."""
    if ticker in portfolio_tickers:
        return None

    opening_range = signals.get("opening_range")
    gap = signals.get("gap")
    vwap = signals.get("vwap")
    inside_bar = signals.get("inside_bar")
    flag = signals.get("flag")
    volume = signals.get("volume")
    patterns = signals.get("candlestick_patterns") or []

    pattern_line = ", ".join(f"{p['name']} ({p['signal']})" for p in patterns) if patterns else "none detected"
    track_record_context = format_track_record_context(DAY_STRATEGIES)

    prompt = f"""Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Evaluate {ticker} as a candidate DAY TRADE (holding period of minutes to a few hours,
closed out the same session) using ONLY the signals below.

This system's own track record so far, by strategy (factor this in, but don't let a
small sample override what you're actually seeing in the signals below):
{track_record_context}

1. OPENING RANGE — {f"high ${opening_range['range_high']} / low ${opening_range['range_low']}, current price is {opening_range['breakout']} the range" if opening_range else "unavailable"}

2. GAP — {f"{gap['direction']} {gap['gap_pct']}% from yesterday's close" if gap else "unavailable"}
   A real gap can be traded WITH it (Gap & Go) or AGAINST it if it looks likely to fill
   (Gap Fade) — decide which reading the other signals actually support, don't default to Gap & Go.

3. VWAP — {f"price is currently {vwap['position']} VWAP (${vwap['vwap']})" if vwap else "unavailable"}

4. INSIDE BAR — {f"today's range IS fully inside yesterday's (${inside_bar['mother_bar_low']}-${inside_bar['mother_bar_high']}) — a breakout setup" if inside_bar and inside_bar['is_inside_bar'] else "no inside-bar setup"}

5. FLAG PATTERN — {f"{flag['direction']} flagpole move of {flag['pole_move_pct']}%, {'consolidating (real flag)' if flag['consolidating'] else 'not yet consolidating — too early to call it a flag'}" if flag else "no flagpole move detected"}

6. CANDLESTICK PATTERNS on the most recent bar: {pattern_line}

7. VOLUME — {f"{volume['volume_ratio']}x this session's average so far ({'elevated' if volume['elevated'] else 'normal'})" if volume else "unavailable"}

8. MARKET DIRECTION — overall market sentiment today: {market_sentiment}

Day trades need MUCH tighter targets/stops than a multi-day swing trade — think fractions
of a percent to low single digits, not the 5-10% ranges appropriate for a multi-week hold.
Your suggested target_pct MUST still be at least {MIN_REWARD_RISK_RATIO}x your stop_loss_pct.

Respond with ONLY valid JSON in exactly this shape, no other text:
{{"probability_score": <integer 0-100, overall confidence this is a good day trade right now>,
  "risk_level": "LOW" | "MODERATE" | "HIGH",
  "primary_strategy": <the ONE strategy from this list that most decisively drove this decision — exactly one of: {DAY_STRATEGIES}>,
  "target_pct": <float, small — e.g. 0.5 to 3.0>,
  "stop_loss_pct": <float, small — e.g. 0.3 to 2.0>,
  "expected_holding_time": "<short phrase, e.g. '30-90 minutes', 'rest of session'>",
  "reason_for_entry": "<2-3 sentences citing the specific signals above>"}}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        track_ai_usage(
            agent="Trading Engine", model=MODEL,
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens,
            feature="day_trade_decision",
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        decision = json.loads(strip_json_fence(text))
    except Exception as e:
        print(f"Day trade evaluation failed for {ticker}: {e}")
        return None

    decision["ticker"] = ticker
    decision["athena_confidence"] = None  # day trades don't use Athena's fundamental score
    decision["news_summary"] = "N/A — day trades evaluate price action, not news"
    decision["technical_analysis"] = f"ORB: {opening_range}; Gap: {gap}; VWAP: {vwap}"
    decision["strategy_type"] = "Day"
    if decision.get("primary_strategy") not in DAY_STRATEGIES:
        decision["primary_strategy"] = "Candlestick Reversal"  # safe fallback if Claude drifts off-list
    return decision


if __name__ == "__main__":
    test_ticker = "AAPL"
    test_signals = gather_day_signals(test_ticker)
    print(f"{test_ticker} day signals:", json.dumps(test_signals, indent=2, default=str))
    print("passes day prefilter:", passes_day_prefilter(test_signals))
    if passes_day_prefilter(test_signals):
        decision_result = evaluate_day_trade(test_ticker, test_signals, "Mixed", [])
        print(json.dumps(decision_result, indent=2))
