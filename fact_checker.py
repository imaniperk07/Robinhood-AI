import json
from datetime import datetime, timezone

import yfinance as yf

from news_analysis import get_news, get_product_news
from jarvis import client, MODEL
from ai_cost_tracker import track_ai_usage


def get_earnings_date(ticker: str) -> str | None:
    """Next/most recent earnings date as YYYY-MM-DD, or None if unavailable."""
    try:
        info = yf.Ticker(ticker).info
    except Exception:
        return None

    timestamp = info.get("earningsTimestamp")
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def gather_facts(ticker: str) -> dict:
    """Deterministic, data-driven facts about a ticker — no LLM involved."""
    earnings_date = get_earnings_date(ticker)

    try:
        recent_news = get_news(ticker, max_articles=5)
    except Exception:
        recent_news = []

    try:
        product_news = get_product_news(ticker, max_articles=3)
    except Exception:
        product_news = []

    return {
        "earnings_date": earnings_date,
        "recent_news": recent_news,
        "product_news": product_news,
    }


def analyze_message(content: str, ticker: str, facts: dict, today: str) -> dict:
    """One Claude call: sentiment + reasoning + fact-check verdict, as JSON.
    This is fuzzy natural-language judgment (does the claim actually match the facts?)
    — the kind of thing a hand-rolled heuristic would do badly."""
    headlines = [a.get("title", "") for a in facts.get("recent_news", [])]
    product_headlines = [a.get("title", "") for a in facts.get("product_news", [])]

    prompt = f"""Today's date: {today}
A message about {ticker}: "{content}"

Known facts:
- Next/most recent earnings date: {facts.get('earnings_date') or 'unknown'}
- Recent news headlines: {headlines or 'none found'}
- Recent product/launch news headlines: {product_headlines or 'none found'}

Judge this message using ONLY the facts above — don't use outside knowledge about the
company. Respond with ONLY valid JSON in exactly this shape, no other text:
{{"sentiment": "Bullish" | "Bearish" | "Neutral",
  "sentiment_reasoning": "<one sentence: why the person seems to think this>",
  "fact_check_verdict": "Confirmed" | "Partially Confirmed" | "Not Supported",
  "fact_check_explanation": "<one sentence citing a fact above, or noting no verifiable claim was made>"}}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        track_ai_usage(
            agent="Fact Checker",
            model=MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            feature="fact_check",
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return json.loads(text)
    except Exception as e:
        return {
            "sentiment": "Neutral",
            "sentiment_reasoning": f"Could not analyze message: {e}",
            "fact_check_verdict": "Not Supported",
            "fact_check_explanation": "Could not verify — analysis failed.",
        }


if __name__ == "__main__":
    ticker_arg = "AAPL"
    message_arg = "Apple should rally because earnings are next week."
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    facts_result = gather_facts(ticker_arg)
    print("Facts:", facts_result["earnings_date"], f"({len(facts_result['recent_news'])} news articles)")

    analysis_result = analyze_message(message_arg, ticker_arg, facts_result, today_str)
    print(json.dumps(analysis_result, indent=2))
