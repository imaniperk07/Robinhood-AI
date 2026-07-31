import json
from datetime import datetime, timezone

import yfinance as yf

from athena import analyze_stock
from report_generator import get_technical_summary
from tradingview_ratings import get_rating as get_tradingview_rating
from pullback_indicator import check_pullback_risk
from smart_alerts import check_ticker as check_smart_alerts
from technical_analysis import detect_candlestick_patterns
from fact_checker import get_earnings_date, strip_json_fence
from news_analysis import get_news
from dashboard import INDICES, get_index_data, overall_sentiment
from jarvis import client, MODEL
from ai_cost_tracker import track_ai_usage
from database import storage

CONFIDENCE_THRESHOLD = 75  # 0-100 scale, matches Athena/Opportunity Hunter/Wealth Builder
POSITION_SIZE_USD = 500
MIN_REWARD_RISK_RATIO = 1.5  # target_pct must be at least this many times stop_loss_pct
MIN_TRADES_FOR_TRACK_RECORD = 5  # don't feed a strategy's history back until it's a real sample

# Controlled vocabulary, not free text — keeps get_strategy_performance()'s aggregation
# clean instead of fragmenting into slightly-different strings per trade.
SWING_STRATEGIES = [
    "Trend Pullback", "Support/Resistance Bounce", "Breakout Confirmation",
    "Candlestick Reversal", "Momentum Continuation", "Fundamental + Technical Confluence",
]
DAY_STRATEGIES = [
    "Opening Range Breakout", "Gap & Go", "Gap Fade", "VWAP Bounce", "VWAP Rejection",
    "Inside Bar Breakout", "Bull Flag Continuation", "Candlestick Reversal",
]


def get_strategy_track_record(strategy_name: str) -> dict | None:
    """This strategy's own historical performance on this system, for feeding back into
    the evaluation prompt — the feedback loop that lets consistently-good strategies earn
    a bit more benefit of the doubt over time. None until there's a real sample size."""
    for row in storage.get_strategy_performance():
        if row["strategy"] == strategy_name and row["total_trades"] >= MIN_TRADES_FOR_TRACK_RECORD:
            return row
    return None


def get_volume_confirmation(ticker: str) -> dict | None:
    """Is the current move actually backed by real trading volume, or just price
    drifting on thin volume? Unlike smart_alerts' volume-spike check (which only
    speaks up when volume is unusually high), this always reports the ratio so it can
    be weighed as a genuine confirmation signal, not just an anomaly alert."""
    history = yf.Ticker(ticker).history(period="1mo")
    if len(history) < 21:
        return None
    volumes = history["Volume"]
    today_volume = volumes.iloc[-1]
    avg_volume_20d = volumes.iloc[-21:-1].mean()
    if avg_volume_20d <= 0:
        return None
    ratio = today_volume / avg_volume_20d
    return {"volume_ratio": round(float(ratio), 2), "confirmed": bool(ratio >= 1.0)}


def get_candlestick_signals(ticker: str) -> list[dict]:
    """Candlestick patterns on the most recent candle, via TA-Lib. 3mo lookback gives
    enough prior-trend context for reversal patterns to actually mean something."""
    history = yf.Ticker(ticker).history(period="3mo")
    if history.empty:
        return []
    return detect_candlestick_patterns(history)


def gather_signals(ticker: str) -> dict:
    """Cheap signals only — no NewsAPI, no Claude. Used for the pre-filter, so this
    can run against the whole candidate universe every scan cycle without worry."""
    return {
        "athena": analyze_stock(ticker),
        "technical": get_technical_summary(ticker, include_news_score=False),
        "tradingview_rating": get_tradingview_rating(ticker),
        "pullback_risk": check_pullback_risk(ticker),
        "smart_alerts": check_smart_alerts(ticker),
        "volume": get_volume_confirmation(ticker),
        "candlestick_patterns": get_candlestick_signals(ticker),
    }


def passes_prefilter(signals: dict) -> bool:
    """Cheap gate before spending a NewsAPI call or a Claude call on this ticker."""
    athena = signals.get("athena")
    technical = signals.get("technical")
    pullback = signals.get("pullback_risk")

    if not athena or not technical:
        return False
    if athena["confidence_score"] < 50:
        return False
    if technical["score_100"] < 50:
        return False
    if pullback and pullback["risk_level"] == "HIGH":
        return False
    return True


def get_market_sentiment() -> str:
    results = [r for r in (get_index_data(name, ticker) for name, ticker in INDICES.items()) if r]
    return overall_sentiment(results) if results else "Unknown"


def format_track_record_context(strategy_names: list[str]) -> str:
    """One line per strategy with a real track record (>= MIN_TRADES_FOR_TRACK_RECORD
    closed trades), for the caller to fold into its prompt before Claude picks which
    strategy applies — lets a consistently-good strategy earn a bit more benefit of the
    doubt, and a consistently-poor one get more scrutiny, without a separate ML system."""
    lines = []
    for name in strategy_names:
        record = get_strategy_track_record(name)
        if record:
            lines.append(f"- {name}: {record['win_rate']}% win rate over {record['total_trades']} trades, "
                          f"avg return {record['avg_return_pct']:+.2f}%")
    return "\n".join(lines) if lines else "No strategy has a large enough sample yet (fewer than 5 closed trades each)."


def evaluate_trade(ticker: str, signals: dict, market_sentiment: str, portfolio_tickers: list[str]) -> dict | None:
    """One Claude call combining every gathered signal + fresh news into a final trade
    decision. Only call this for tickers that already passed passes_prefilter() — this
    is the expensive step (1 NewsAPI call + 1 Claude call), deliberately gated.
    Returns None if the ticker is already held, or if the call/parse fails."""
    if ticker in portfolio_tickers:
        return None

    earnings_date = get_earnings_date(ticker)
    try:
        recent_news = get_news(ticker, max_articles=5)
    except Exception:
        recent_news = []
    athena = signals["athena"]
    technical = signals["technical"]
    tv_rating = signals.get("tradingview_rating")
    pullback = signals.get("pullback_risk")
    alerts = signals.get("smart_alerts") or []
    volume = signals.get("volume")
    patterns = signals.get("candlestick_patterns") or []
    headlines = [a.get("title", "") for a in recent_news]

    if patterns:
        pattern_line = ", ".join(f"{p['name']} ({p['signal']})" for p in patterns)
    else:
        pattern_line = "none detected"

    if volume:
        volume_line = f"{volume['volume_ratio']}x its 20-day average ({'confirms' if volume['confirmed'] else 'does NOT confirm'} the move)"
    else:
        volume_line = "unavailable"

    track_record_context = format_track_record_context(SWING_STRATEGIES)

    prompt = f"""Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Evaluate {ticker} as a candidate SWING TRADE (holding period of days to a few weeks) using
ONLY the signals below — don't use outside knowledge about the company. Work through these
five checks in order before deciding — don't just average the numbers, reason about whether
each one genuinely supports the trade:

This system's own track record so far, by strategy (factor this in, but don't let a small
sample override what you're actually seeing in the signals below):
{track_record_context}

1. NEWS & CATALYSTS — is there a real catalyst, or is this just noise?
   Recent news headlines: {headlines or 'none found'}
   Next/most recent earnings date: {earnings_date or 'unknown'} (an earnings date inside the
   expected holding window is a real risk, not a catalyst to trade around blindly)

2. TREND CONFIRMATION — does the technical picture actually confirm a tradeable trend?
   Technical summary: {technical['summary']} (score {technical['score_100']}/100)
   TradingView technical rating: {tv_rating or 'unavailable'}
   Pullback/overextension risk: {pullback['risk_level'] if pullback else 'unavailable'} ({pullback['signals'] if pullback else []})
   Other alerts triggered: {alerts or 'none'}
   Candlestick patterns on the most recent candle: {pattern_line}
   Weigh any detected pattern using two filters, don't treat it as automatically meaningful:
   (a) LOCATION — the technical summary above states the current support/resistance levels;
   a pattern near one of those levels is far more meaningful than the same pattern in open
   air, away from any level.
   (b) TREND CONTEXT — a reversal pattern only matters in the context of an existing trend to
   reverse (e.g. a bullish reversal pattern after a downtrend is meaningful; the same pattern
   with no prior trend, or fighting an already-strong trend in the pattern's own direction, is
   closer to noise).

3. VOLUME CONFIRMATION — is the move backed by real participation, or thin/low-conviction trading?
   Today's volume vs 20-day average: {volume_line}

4. MARKET DIRECTION — does the broader market support this trade, or is it fighting the tape?
   Overall market sentiment today: {market_sentiment}

5. FUNDAMENTAL BACKDROP & RISK/REWARD — is the underlying business sound, and does the
   trade offer meaningfully more upside than downside?
   Athena fundamental confidence: {athena['confidence_score']}/100
   Bull case: {athena['bull_case']}
   Bear case: {athena['bear_case']}
   Your suggested target_pct MUST be at least {MIN_REWARD_RISK_RATIO}x your suggested
   stop_loss_pct — if you can't find a stop/target pair with a genuinely favorable
   risk/reward, say so honestly with a low probability_score rather than forcing a ratio
   that technically clears {MIN_REWARD_RISK_RATIO}x but isn't realistic for this setup.

Assume entry near the current market price (not provided here — the caller fills in the
real fill price). Respond with ONLY valid JSON in exactly this shape, no other text:
{{"probability_score": <integer 0-100, overall confidence this is a good swing trade right now>,
  "risk_level": "LOW" | "MODERATE" | "HIGH",
  "primary_strategy": <the ONE strategy from this list that most decisively drove this decision — exactly one of: {SWING_STRATEGIES}>,
  "target_pct": <float, suggested target as a % gain from entry, e.g. 8.0>,
  "stop_loss_pct": <float, suggested stop-loss as a % loss from entry, e.g. 4.0>,
  "expected_holding_time": "<short phrase, e.g. '3-10 trading days'>",
  "reason_for_entry": "<2-3 sentences citing the specific signals above, addressing at least the catalyst, volume, and risk/reward checks>"}}"""

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
            feature="trade_decision",
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        decision = json.loads(strip_json_fence(text))
    except Exception as e:
        print(f"Trade evaluation failed for {ticker}: {e}")
        return None

    decision["ticker"] = ticker
    decision["athena_confidence"] = athena["confidence_score"]
    decision["news_summary"] = "; ".join(headlines[:3]) or "No recent headlines found."
    decision["technical_analysis"] = technical["summary"]
    decision["strategy_type"] = "Swing"
    if decision.get("primary_strategy") not in SWING_STRATEGIES:
        decision["primary_strategy"] = "Fundamental + Technical Confluence"  # safe fallback if Claude drifts off-list
    return decision


if __name__ == "__main__":
    test_ticker = "AAPL"
    test_signals = gather_signals(test_ticker)
    print(f"{test_ticker} signals:", json.dumps(
        {k: (v if k != "athena" else {"confidence_score": v["confidence_score"]} if v else None) for k, v in test_signals.items()},
        indent=2, default=str,
    ))
    print("passes prefilter:", passes_prefilter(test_signals))
    if passes_prefilter(test_signals):
        decision_result = evaluate_trade(test_ticker, test_signals, get_market_sentiment(), [])
        print(json.dumps(decision_result, indent=2))
