from datetime import datetime, timezone

import yfinance as yf

from athena import get_fundamentals
from watchlist import format_market_cap, WATCHLIST
from technical_analysis import (
    calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_support_resistance, interpret_trend, interpret_rsi, interpret_macd,
)
from stock_ratings import score_trend, score_rsi, score_macd, score_bollinger, score_news
from dashboard import INDICES, get_index_data, overall_sentiment
from fact_checker import gather_facts, analyze_message, analyze_general_claim
from news_analysis import get_market_wide_news
from portfolio_assistant import build_portfolio
from sources.base_source import SourceItem

MARKET_TICKER = "MARKET"  # sentinel ticker for reports with no specific stock mentioned


def get_technical_summary(ticker: str, include_news_score: bool = True) -> dict:
    """1y of history (not the usual 6mo) so a 200-day SMA is possible.
    include_news_score=False skips score_news()'s NewsAPI call entirely, using the
    same neutral-default point value score_news itself falls back to when it finds
    no articles — keeps score_100 on the same 0-100 scale without spending a request.
    Callers that need to stay NewsAPI-free for their own rate-limit reasons (e.g. a
    pre-filter run across dozens of candidates) should pass False."""
    stock = yf.Ticker(ticker)
    history = stock.history(period="1y")
    if history.empty or len(history) < 50:
        return {"summary": "Not enough price history for technical analysis.", "score_100": 12, "daily_change_pct": None}

    closes = history["Close"]
    latest_price = closes.iloc[-1]
    daily_change_pct = ((latest_price - closes.iloc[-2]) / closes.iloc[-2] * 100) if len(closes) >= 2 else None

    sma_20 = calculate_sma(closes, 20).iloc[-1]
    sma_50 = calculate_sma(closes, 50).iloc[-1]
    sma_200 = calculate_sma(closes, 200).iloc[-1] if len(closes) >= 200 else None
    rsi = calculate_rsi(closes).iloc[-1]
    macd_line, signal_line = calculate_macd(closes)
    upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)
    support, resistance = calculate_support_resistance(history)

    trend_points, trend_note = score_trend(latest_price, sma_20, sma_50)
    rsi_points, rsi_note = score_rsi(rsi)
    macd_points, macd_note = score_macd(macd_line.iloc[-1], signal_line.iloc[-1])
    boll_points, boll_note = score_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1])
    if include_news_score:
        news_points, news_note = score_news(ticker)
    else:
        news_points, news_note = 10, "News score skipped (no NewsAPI call for this caller)"
    score_100 = trend_points + rsi_points + macd_points + boll_points + news_points

    sma_200_str = f"${sma_200:.2f}" if sma_200 is not None else "N/A (not enough history yet)"
    summary = (
        f"{interpret_trend(latest_price, sma_20, sma_50)} 200-day SMA: {sma_200_str}. "
        f"{interpret_rsi(rsi)} {interpret_macd(macd_line.iloc[-1], signal_line.iloc[-1])} "
        f"Support ${support:.2f} / Resistance ${resistance:.2f}."
    )

    return {
        "summary": summary,
        "score_100": score_100,
        "daily_change_pct": round(float(daily_change_pct), 2) if daily_change_pct is not None else None,
    }


def calculate_confidence_score(technical_news_score_100: int, fact_check_verdict: str, market_sentiment: str) -> tuple[int, str]:
    """1-10 scale. Never a buy/sell signal — just how much weight the evidence supports."""
    base = round(technical_news_score_100 / 100 * 6)
    verdict_bonus = {"Confirmed": 3, "Partially Confirmed": 1, "Not Supported": -2}.get(fact_check_verdict, 0)

    sentiment_label = market_sentiment.split("—")[0].strip() if market_sentiment else "Unknown"
    if "Bullish" in sentiment_label:
        market_bonus = 1
    elif "Bearish" in sentiment_label:
        market_bonus = -1
    else:
        market_bonus = 0

    score = max(1, min(10, base + verdict_bonus + market_bonus))
    reasoning = (
        f"Technical/news score {technical_news_score_100}/100 (contributes {base}/6 base points); "
        f"fact-check verdict '{fact_check_verdict}' ({verdict_bonus:+d}); "
        f"market conditions '{sentiment_label}' ({market_bonus:+d})."
    )
    return score, reasoning


def build_report(ticker: str, item: SourceItem) -> dict:
    """The whole Athena pipeline for one ticker mentioned in one SourceItem."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fundamentals = get_fundamentals(ticker)
    facts = gather_facts(ticker)
    analysis = analyze_message(item.content, ticker, facts, today)
    technical = get_technical_summary(ticker)

    market_snapshot = [r for r in (get_index_data(name, idx) for name, idx in INDICES.items()) if r]
    market_sentiment = overall_sentiment(market_snapshot) if market_snapshot else "Unknown"

    confidence_score, confidence_reasoning = calculate_confidence_score(
        technical["score_100"], analysis.get("fact_check_verdict", "Not Supported"), market_sentiment
    )

    return {
        "ticker": ticker,
        "company": fundamentals["name"] if fundamentals else ticker,
        "price": fundamentals["price"] if fundamentals else None,
        "market_cap": format_market_cap(fundamentals["market_cap"]) if fundamentals and fundamentals.get("market_cap") else None,
        "daily_change_pct": technical["daily_change_pct"],
        "source": item.source,
        "source_claim": item.content,
        "sentiment": analysis.get("sentiment", "Neutral"),
        "sentiment_reasoning": analysis.get("sentiment_reasoning", ""),
        "fact_check_verdict": analysis.get("fact_check_verdict", "Not Supported"),
        "fact_check_explanation": analysis.get("fact_check_explanation", ""),
        "recent_news": facts.get("recent_news", []),
        "technical_summary": technical["summary"],
        "confidence_score": confidence_score,
        "reasoning": confidence_reasoning,
    }


def build_general_impact_report(item: SourceItem) -> dict:
    """For content with no specific ticker mentioned (e.g. a general 'this affects a lot
    of stocks' claim) — fact-checks the claim itself and flags which of the user's
    watchlist + portfolio tickers it's likely to actually affect."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        portfolio_tickers = [h["ticker"] for h in build_portfolio()]
    except Exception:
        portfolio_tickers = []
    tickers_to_check = sorted(set(WATCHLIST) | set(portfolio_tickers))

    try:
        market_news = get_market_wide_news(max_articles=8)
    except Exception:
        market_news = []

    analysis = analyze_general_claim(item.content, tickers_to_check, market_news, today)
    impacted = analysis.get("impacted_tickers", [])

    return {
        "ticker": MARKET_TICKER,
        "company": f"Potentially affects {len(impacted)} ticker(s)" if impacted else "No specific holdings affected",
        "price": None,
        "market_cap": None,
        "daily_change_pct": None,
        "source": item.source,
        "source_claim": item.content,
        "sentiment": analysis.get("sentiment", "Neutral"),
        "sentiment_reasoning": analysis.get("sentiment_reasoning", ""),
        "fact_check_verdict": analysis.get("fact_check_verdict", "Not Supported"),
        "fact_check_explanation": analysis.get("fact_check_explanation", ""),
        "recent_news": market_news[:5],
        "technical_summary": analysis.get("impact_summary", ""),
        "confidence_score": analysis.get("confidence_score", 1),
        "reasoning": (
            f"Impacted tickers from your watchlist/portfolio: {', '.join(impacted)}."
            if impacted else
            "No tickers from your watchlist or portfolio were identified as affected."
        ),
    }


def format_report_text(report: dict) -> str:
    news_lines = "\n".join(f"  - {a.get('title', '')}" for a in report.get("recent_news", [])) or "  (none found)"
    return f"""{'=' * 70}
Ticker: {report['ticker']}
Company: {report['company']}

Source: {report['source']}
Source Claim: {report['source_claim']}

Sentiment: {report['sentiment']} — {report['sentiment_reasoning']}

Fact Check: {report['fact_check_verdict']} — {report['fact_check_explanation']}

Recent News:
{news_lines}

Technical Analysis: {report['technical_summary']}

Confidence Score: {report['confidence_score']}/10

Reasoning: {report['reasoning']}
{'=' * 70}
"""


if __name__ == "__main__":
    test_item = SourceItem(
        source="test", author="imani", content="Apple should rally because earnings are next week.",
        url=None, timestamp=datetime.now(timezone.utc).isoformat(),
    )
    report_result = build_report("AAPL", test_item)
    print(format_report_text(report_result))
