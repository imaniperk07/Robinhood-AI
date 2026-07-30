import json
from datetime import datetime, timezone

from athena import analyze_stock
from report_generator import get_technical_summary
from tradingview_ratings import get_rating as get_tradingview_rating
from pullback_indicator import check_pullback_risk
from smart_alerts import check_ticker as check_smart_alerts
from fact_checker import get_earnings_date, strip_json_fence
from news_analysis import get_news
from dashboard import INDICES, get_index_data, overall_sentiment
from jarvis import client, MODEL
from ai_cost_tracker import track_ai_usage

CONFIDENCE_THRESHOLD = 75  # 0-100 scale, matches Athena/Opportunity Hunter/Wealth Builder
POSITION_SIZE_USD = 500


def gather_signals(ticker: str) -> dict:
    """Cheap signals only — no NewsAPI, no Claude. Used for the pre-filter, so this
    can run against the whole candidate universe every scan cycle without worry."""
    return {
        "athena": analyze_stock(ticker),
        "technical": get_technical_summary(ticker),
        "tradingview_rating": get_tradingview_rating(ticker),
        "pullback_risk": check_pullback_risk(ticker),
        "smart_alerts": check_smart_alerts(ticker),
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
    headlines = [a.get("title", "") for a in recent_news]

    prompt = f"""Today's date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Evaluate {ticker} as a candidate SWING TRADE (holding period of days to a few weeks) using
ONLY the signals below — don't use outside knowledge about the company.

Athena fundamental confidence: {athena['confidence_score']}/100
Bull case: {athena['bull_case']}
Bear case: {athena['bear_case']}

Technical summary: {technical['summary']} (score {technical['score_100']}/100)

TradingView technical rating: {tv_rating or 'unavailable'}

Pullback/overextension risk: {pullback['risk_level'] if pullback else 'unavailable'} ({pullback['signals'] if pullback else []})

Smart alerts triggered: {alerts or 'none'}

Recent news headlines: {headlines or 'none found'}
Next/most recent earnings date: {earnings_date or 'unknown'}

Overall market sentiment today: {market_sentiment}

Assume entry near the current market price (not provided here — the caller fills in the
real fill price). Respond with ONLY valid JSON in exactly this shape, no other text:
{{"probability_score": <integer 0-100, overall confidence this is a good swing trade right now>,
  "risk_level": "LOW" | "MODERATE" | "HIGH",
  "target_pct": <float, suggested target as a % gain from entry, e.g. 8.0>,
  "stop_loss_pct": <float, suggested stop-loss as a % loss from entry, e.g. 4.0>,
  "expected_holding_time": "<short phrase, e.g. '3-10 trading days'>",
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
