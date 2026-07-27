import json
import os

import anthropic
import yfinance as yf
from dotenv import load_dotenv

from technical_analysis import (
    calculate_sma, calculate_rsi, calculate_macd, calculate_bollinger_bands,
    calculate_support_resistance, interpret_trend, interpret_rsi,
    interpret_macd, interpret_bollinger,
)
from stock_ratings import score_trend, score_rsi, score_macd, score_bollinger, score_news
from news_analysis import get_news, rough_tag
from portfolio_assistant import build_portfolio, calculate_risk_score
from dashboard import INDICES, get_index_data, simplified_fear_greed, overall_sentiment
from watchlist import WATCHLIST, get_stock_data, format_market_cap
from memory_agent import get_memory_summary, add_note
from ai_cost_tracker import track_ai_usage

load_dotenv()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-5"

SYSTEM_PROMPT_BASE = """You are Jarvis, the conversational AI assistant for this investment research platform.

You help the user research stocks, understand their portfolio, and learn investing concepts using the
tools available to you. Always prefer calling a tool over guessing — your tools pull real, current data,
your training knowledge does not.

Rules:
- This is a research and education platform, not a trading bot. Never tell the user to buy or sell, and
  never guarantee profits.
- Always explain your reasoning in plain, beginner-friendly language.
- When you share a rating, score, or signal, explain both the opportunity and the risk side of it.
- If a tool returns an error or missing data, say so plainly instead of making something up.
- Keep responses focused and conversational — this is a chat, not a report.
"""


def build_system_prompt() -> str:
    memory_summary = get_memory_summary()
    return f"""{SYSTEM_PROMPT_BASE}
What you know about this user so far (from the Memory Agent):
{memory_summary}

Use this to personalize your answers where it's relevant — but don't force it in, and never let a
stated preference talk the user into a riskier position than they'd otherwise take.

If the user shares something worth remembering long-term (their risk tolerance, favorite sectors or
companies, investing goals, or a notable habit), use the remember_fact tool to save it — don't just
mention it in passing and let it disappear when the conversation ends.
"""


def get_technical_analysis(ticker: str) -> dict:
    """Full technical picture + 0-100 rating for one ticker."""
    stock = yf.Ticker(ticker)
    history = stock.history(period="6mo")
    if history.empty or len(history) < 50:
        return {"error": f"Not enough price history for {ticker}."}

    closes = history["Close"]
    latest_price = closes.iloc[-1]
    sma_20 = calculate_sma(closes, 20).iloc[-1]
    sma_50 = calculate_sma(closes, 50).iloc[-1]
    rsi = calculate_rsi(closes).iloc[-1]
    macd_line, signal_line = calculate_macd(closes)
    upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)
    support, resistance = calculate_support_resistance(history)

    trend_points, trend_note = score_trend(latest_price, sma_20, sma_50)
    rsi_points, rsi_note = score_rsi(rsi)
    macd_points, macd_note = score_macd(macd_line.iloc[-1], signal_line.iloc[-1])
    boll_points, boll_note = score_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1])
    news_points, news_note = score_news(ticker)

    return {
        "ticker": ticker,
        "price": round(float(latest_price), 2),
        "sma_20": round(float(sma_20), 2),
        "sma_50": round(float(sma_50), 2),
        "support": round(float(support), 2),
        "resistance": round(float(resistance), 2),
        "trend_explanation": interpret_trend(latest_price, sma_20, sma_50),
        "rsi_explanation": interpret_rsi(rsi),
        "macd_explanation": interpret_macd(macd_line.iloc[-1], signal_line.iloc[-1]),
        "bollinger_explanation": interpret_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1]),
        "overall_score": trend_points + rsi_points + macd_points + boll_points + news_points,
        "score_breakdown": {
            "trend": f"{trend_points}/25 - {trend_note}",
            "rsi": f"{rsi_points}/20 - {rsi_note}",
            "macd": f"{macd_points}/20 - {macd_note}",
            "bollinger": f"{boll_points}/15 - {boll_note}",
            "news_tone": f"{news_points}/20 - {news_note}",
        },
    }


def get_stock_news(ticker: str) -> dict:
    """Recent headlines for one ticker, tagged possibly positive/negative/neutral."""
    articles = get_news(ticker, max_articles=8)
    headlines = [
        {
            "title": a.get("title", "No title"),
            "source": a.get("source", {}).get("name", "Unknown"),
            "tone": rough_tag(a.get("title", "")),
        }
        for a in articles
    ]
    return {"ticker": ticker, "headlines": headlines}


def get_portfolio_summary() -> dict:
    """The user's real portfolio: value, gain/loss, holdings, sector allocation, risk score."""
    portfolio = build_portfolio()
    if not portfolio:
        return {"error": "No holdings data available. Check the SnapTrade connection."}

    total_value = sum(h["current_value"] for h in portfolio)
    total_cost = sum(h["cost_value"] for h in portfolio)
    total_daily_gain_loss = sum(h["daily_gain_loss"] for h in portfolio)
    total_gain_loss = total_value - total_cost
    total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost else 0

    sector_totals = {}
    for h in portfolio:
        sector_totals[h["sector"]] = sector_totals.get(h["sector"], 0) + h["current_value"]

    risk_score, risk_notes = calculate_risk_score(portfolio, sector_totals, total_value)

    return {
        "total_value": round(total_value, 2),
        "total_daily_gain_loss": round(total_daily_gain_loss, 2),
        "total_gain_loss": round(total_gain_loss, 2),
        "total_gain_loss_pct": round(total_gain_loss_pct, 2),
        "holdings": [
            {
                "ticker": h["ticker"],
                "shares": h["shares"],
                "current_price": round(h["current_price"], 2),
                "current_value": round(h["current_value"], 2),
                "total_gain_loss_pct": round(h["total_gain_loss_pct"], 2),
                "sector": h["sector"],
            }
            for h in portfolio
        ],
        "sector_allocation_pct": (
            {sector: round(value / total_value * 100, 1) for sector, value in sector_totals.items()}
            if total_value else {}
        ),
        "risk_score": risk_score,
        "risk_notes": risk_notes,
    }


def get_market_overview() -> dict:
    """Today's index prices/changes, simplified Fear & Greed, and overall sentiment."""
    raw_results = []
    for name, ticker in INDICES.items():
        result = get_index_data(name, ticker)
        if result:
            raw_results.append(result)

    vix_result = next((r for r in raw_results if r["name"] == "VIX"), None)
    fear_greed = simplified_fear_greed(vix_result["price"]) if vix_result else "Unavailable"
    sentiment = overall_sentiment(raw_results)

    indices = [
        {"name": r["name"], "price": round(float(r["price"]), 2), "change_pct": round(float(r["change_pct"]), 2)}
        for r in raw_results
    ]
    return {"indices": indices, "fear_greed": fear_greed, "sentiment": sentiment}


def get_watchlist_snapshot() -> dict:
    """Price and daily/weekly/monthly % change for every ticker on the watchlist."""
    snapshot = []
    for ticker in WATCHLIST:
        data = get_stock_data(ticker)
        if not data:
            continue
        snapshot.append({
            "ticker": data["ticker"],
            "price": round(float(data["price"]), 2),
            "daily_pct": round(float(data["daily_pct"]), 2) if data["daily_pct"] is not None else None,
            "weekly_pct": round(float(data["weekly_pct"]), 2) if data["weekly_pct"] is not None else None,
            "monthly_pct": round(float(data["monthly_pct"]), 2) if data["monthly_pct"] is not None else None,
            "market_cap": format_market_cap(data["market_cap"]),
        })
    return {"watchlist": snapshot}


TOOLS = [
    {
        "name": "get_technical_analysis",
        "description": "Get technical analysis and a 0-100 rating for one stock ticker: price, moving "
                        "averages, RSI, MACD, Bollinger Bands, support/resistance, and beginner-friendly "
                        "explanations of each.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Get recent news headlines for one stock ticker, each tagged as possibly positive, "
                        "negative, or neutral.",
        "input_schema": {
            "type": "object",
            "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}},
            "required": ["ticker"],
        },
    },
    {
        "name": "get_portfolio_summary",
        "description": "Get the user's real portfolio: total value, gain/loss, holdings, sector "
                        "allocation, and a risk score. Pulled live from Robinhood via SnapTrade.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_market_overview",
        "description": "Get today's overall market snapshot: major index prices/changes, a simplified "
                        "Fear & Greed reading, and overall sentiment.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_watchlist_snapshot",
        "description": "Get price and daily/weekly/monthly % change for every stock on the user's "
                        "watchlist.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "remember_fact",
        "description": "Save a fact worth remembering about the user long-term — their risk tolerance, "
                        "investing style, favorite sectors/companies, goals, or a notable habit or "
                        "preference they mentioned. Use this whenever the user shares something like this "
                        "in conversation so it carries over to future chats.",
        "input_schema": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": "A short, clear statement of the fact to remember, e.g. "
                                    "'Prefers long-term holds over day trading' or "
                                    "'Risk tolerance is conservative — avoid volatile picks.'",
                }
            },
            "required": ["note"],
        },
    },
]


def remember_fact(note: str) -> dict:
    add_note(note)
    return {"saved": True, "note": note}


TOOL_FUNCTIONS = {
    "get_technical_analysis": get_technical_analysis,
    "get_stock_news": get_stock_news,
    "get_portfolio_summary": get_portfolio_summary,
    "get_market_overview": get_market_overview,
    "get_watchlist_snapshot": get_watchlist_snapshot,
    "remember_fact": remember_fact,
}


def ask_jarvis(
    user_message: str,
    history: list[dict],
    system_prompt: str | None = None,
    agent: str = "Jarvis",
) -> tuple[str, list[dict]]:
    """Send a message to Jarvis, running any tools it needs, and return (reply_text, updated_history).

    Also reused by other chat-style personas (like Mentor) that want the same tools and tool-calling
    loop but a different system prompt — pass one in via `system_prompt` to override Jarvis's own, and
    `agent` so AI cost tracking attributes usage to the right persona."""
    messages = history + [{"role": "user", "content": user_message}]
    active_system_prompt = system_prompt if system_prompt is not None else build_system_prompt()

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=active_system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        track_ai_usage(
            agent=agent,
            model=MODEL,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            feature="chat",
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            reply_text = "".join(block.text for block in response.content if block.type == "text")
            return reply_text, messages

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            func = TOOL_FUNCTIONS.get(block.name)
            if func is None:
                result = {"error": f"Unknown tool: {block.name}"}
            else:
                try:
                    result = func(**block.input)
                except Exception as e:
                    result = {"error": str(e)}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})
