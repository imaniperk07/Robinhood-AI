import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from daily_briefing import (
    USER_NAME, get_market_overview, get_watchlist_highlights,
    get_top_news_story, get_highest_risk_ticker,
)
from smart_alerts import check_ticker, WATCHLIST as ALERT_WATCHLIST
from pullback_indicator import check_pullback_risk
from watchlist import WATCHLIST, get_stock_data
from news_analysis import get_market_wide_news, rough_tag, flag_watchlist_mentions
from database import storage

load_dotenv()

WEBHOOKS = {
    "market_briefing": os.environ.get("DISCORD_WEBHOOK_MARKET_BRIEFING"),
    "alerts": os.environ.get("DISCORD_WEBHOOK_ALERTS"),
    "system_status": os.environ.get("DISCORD_WEBHOOK_SYSTEM_STATUS"),
    "news": os.environ.get("DISCORD_WEBHOOK_NEWS"),
    "watchlist": os.environ.get("DISCORD_WEBHOOK_WATCHLIST"),
}

DISCORD_CONTENT_LIMIT = 2000  # Discord's max message length


def send_to_discord(channel: str, message: str, username: str = "Atlas") -> bool:
    """POST a message to one of the configured Discord webhooks."""
    webhook_url = WEBHOOKS.get(channel)
    if not webhook_url:
        print(f"No webhook URL configured for '{channel}' — check your .env file.")
        return False

    if len(message) > DISCORD_CONTENT_LIMIT:
        message = message[:DISCORD_CONTENT_LIMIT - 20] + "\n...(truncated)"

    try:
        response = requests.post(webhook_url, json={"content": message, "username": username}, timeout=10)
    except requests.RequestException as e:
        print(f"Error posting to Discord ({channel}): {e}")
        return False

    if response.status_code not in (200, 204):
        print(f"Discord webhook error ({channel}): {response.status_code} - {response.text}")
        return False
    return True


def build_market_briefing_message() -> str:
    fear_greed, sentiment = get_market_overview()
    highlights = get_watchlist_highlights()
    top_story = get_top_news_story()
    highest_risk = get_highest_risk_ticker()

    lines = [f"**Good morning, {USER_NAME}.**", ""]
    lines.append(f"**Market Sentiment:** {sentiment}")
    lines.append(f"**Fear & Greed (simplified):** {fear_greed}")
    lines.append("")

    lines.append("**Watchlist Highlights**")
    if highlights:
        for ticker, note in highlights:
            lines.append(f"- `{ticker}` — {note}")
    else:
        lines.append("- Nothing notable today.")
    lines.append("")

    lines.append("**Today's News**")
    lines.append(top_story if top_story else "No recent headlines found.")
    lines.append("")

    lines.append("**Highest Risk**")
    lines.append(highest_risk if highest_risk else "Not enough data to determine.")

    return "\n".join(lines)


def post_market_briefing() -> bool:
    return send_to_discord("market_briefing", build_market_briefing_message())


def build_alerts_message() -> str | None:
    """Returns a formatted alerts message, or None if nothing triggered today."""
    sections = []

    for ticker in ALERT_WATCHLIST:
        alerts = check_ticker(ticker)
        if alerts:
            alert_lines = "\n".join(f"  ⚠️ {a}" for a in alerts)
            sections.append(f"**{ticker}**\n{alert_lines}")

    for ticker in ALERT_WATCHLIST:
        pullback = check_pullback_risk(ticker)
        if pullback and pullback["risk_level"] in ("MODERATE", "HIGH"):
            signal_lines = "\n".join(f"  - {s}" for s in pullback["signals"])
            sections.append(f"**{ticker} — Pullback Risk: {pullback['risk_level']}**\n{signal_lines}")

    if not sections:
        return None

    return "**Smart Alerts**\n\n" + "\n\n".join(sections)


def post_alerts() -> bool:
    message = build_alerts_message()
    if message is None:
        print("No alerts to post today.")
        return True
    return send_to_discord("alerts", message)


def build_news_message() -> str | None:
    articles = get_market_wide_news(max_articles=8)
    if not articles:
        return None

    lines = ["**Market News**", ""]
    for article in articles:
        title = article.get("title", "No title")
        source = article.get("source", {}).get("name", "Unknown source")
        tag = rough_tag(title)
        mentions = flag_watchlist_mentions(title)
        mention_str = f" ⚠️ ({', '.join(mentions)})" if mentions else ""
        lines.append(f"[{tag}] {title} — {source}{mention_str}")

    return "\n".join(lines)


def post_news() -> bool:
    message = build_news_message()
    if message is None:
        print("No news to post today.")
        return True
    return send_to_discord("news", message)


def build_watchlist_message() -> str:
    lines = ["**Watchlist Snapshot**", ""]
    for ticker in WATCHLIST:
        data = get_stock_data(ticker)
        if not data:
            continue
        daily = f"{data['daily_pct']:+.2f}%" if data["daily_pct"] is not None else "N/A"
        weekly = f"{data['weekly_pct']:+.2f}%" if data["weekly_pct"] is not None else "N/A"
        monthly = f"{data['monthly_pct']:+.2f}%" if data["monthly_pct"] is not None else "N/A"
        lines.append(f"`{ticker}` ${data['price']:.2f} — Day {daily} | Week {weekly} | Month {monthly}")
    return "\n".join(lines)


def post_watchlist() -> bool:
    return send_to_discord("watchlist", build_watchlist_message())


def build_ai_cost_report_message() -> str:
    storage.init()
    usage = storage.get_usage_today()
    today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    lines = ["🤖 **AI System Report**", "", f"**Date:** {today_str}", ""]

    if not usage:
        lines.append("**AI Usage:** No AI requests recorded today.")
    else:
        lines.append("**AI Usage:**")
        lines.append("")
        for row in usage:
            lines.append(f"**{row['agent']}:**")
            lines.append(f"{row['requests']} requests")
            lines.append(f"{row['tokens'] / 1000:.1f}k tokens")
            lines.append(f"Estimated Cost: ${row['cost']:.2f}")
            lines.append("")

        total_requests = sum(r["requests"] for r in usage)
        total_tokens = sum(r["tokens"] for r in usage)
        total_cost = sum(r["cost"] for r in usage)
        most_used = max(usage, key=lambda r: r["requests"])
        most_expensive = max(usage, key=lambda r: r["cost"])

        lines.append("--------------------")
        lines.append("")
        lines.append("**Total:**")
        lines.append(f"{total_requests} requests")
        lines.append(f"{total_tokens / 1000:.1f}k tokens")
        lines.append("")
        lines.append(f"**Estimated Daily Cost:** ${total_cost:.2f}")
        lines.append("")
        lines.append(f"**Most Used:** {most_used['agent']}")
        lines.append(f"**Most Expensive:** {most_expensive['agent']}")

    lines.append("")
    lines.append("--------------------")
    lines.append("")
    lines.append("**System Status:**")
    lines.append("All AI services operational ✅")

    return "\n".join(lines)


def post_ai_cost_report() -> bool:
    return send_to_discord("system_status", build_ai_cost_report_message(), username="System")


def build_trade_opened_message(trade: dict) -> str:
    lines = [
        f"📈 **Paper Trade Opened: {trade['ticker']}**", "",
        f"**Entry:** ${trade['entry_price']:.2f}",
        f"**Target:** ${trade['target_price']:.2f}   **Stop:** ${trade['stop_loss']:.2f}",
        f"**Position Size:** ${trade['position_size_usd']:.2f} ({trade['shares']:.4f} shares)",
        f"**Trade Score:** {trade['trade_score']}/100   **Athena Confidence:** {trade['athena_confidence']}/100",
        f"**Risk Level:** {trade['risk_level']}",
        f"**Expected Holding Time:** {trade['expected_holding_time']}",
        "", f"**Reasoning:** {trade['reason_for_entry']}",
    ]
    return "\n".join(lines)


def post_trade_opened(trade: dict) -> bool:
    return send_to_discord("alerts", build_trade_opened_message(trade), username="Trading Engine")


def build_trade_closed_message(trade: dict) -> str:
    icon = {"Target Hit": "🎯", "Stop Loss": "🛑", "Expired": "⏳", "AI Exit": "🤖"}.get(trade["exit_reason"], "📉")
    result = "WIN" if trade["profit_loss_pct"] > 0 else "LOSS"
    lines = [
        f"{icon} **Paper Trade Closed: {trade['ticker']} — {trade['exit_reason']}**", "",
        f"**Result:** {result} ({trade['profit_loss_pct']:+.2f}%)",
        f"**Entry:** ${trade['entry_price']:.2f}   **Exit:** ${trade['current_price']:.2f}",
        f"**Days Held:** {trade.get('days_held', 'N/A')}",
    ]
    return "\n".join(lines)


def post_trade_closed(trade: dict) -> bool:
    return send_to_discord("alerts", build_trade_closed_message(trade), username="Trading Engine")


def build_paper_trading_daily_summary_message() -> str:
    open_trades = storage.get_open_paper_trades()
    closed_today = [
        t for t in storage.get_closed_paper_trades(limit=200)
        if t["date_closed"] and t["date_closed"].startswith(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ]

    lines = ["📊 **Paper Trading Daily Summary**", "", f"**Open Positions:** {len(open_trades)}"]
    if closed_today:
        wins = sum(1 for t in closed_today if t["profit_loss_pct"] > 0)
        total_pl = sum(t["profit_loss_pct"] for t in closed_today)
        lines.append(f"**Closed Today:** {len(closed_today)} ({wins} win / {len(closed_today) - wins} loss)")
        lines.append(f"**Today's Total P/L:** {total_pl:+.2f}%")
    else:
        lines.append("**Closed Today:** none")
    return "\n".join(lines)


def post_paper_trading_daily_summary() -> bool:
    return send_to_discord("alerts", build_paper_trading_daily_summary_message(), username="Trading Engine")


def build_paper_trading_weekly_summary_message() -> str:
    closed = storage.get_closed_paper_trades(limit=200)
    week_ago = datetime.now(timezone.utc).timestamp() - 7 * 86400
    closed_this_week = [
        t for t in closed
        if t["date_closed"] and datetime.fromisoformat(t["date_closed"]).timestamp() >= week_ago
    ]

    lines = ["📅 **Paper Trading Weekly Performance**", ""]
    if not closed_this_week:
        lines.append("No trades closed this week.")
        return "\n".join(lines)

    wins = [t for t in closed_this_week if t["profit_loss_pct"] > 0]
    win_rate = len(wins) / len(closed_this_week) * 100
    avg_gain = sum(t["profit_loss_pct"] for t in wins) / len(wins) if wins else 0.0
    losses = [t for t in closed_this_week if t["profit_loss_pct"] <= 0]
    avg_loss = sum(t["profit_loss_pct"] for t in losses) / len(losses) if losses else 0.0
    best = max(closed_this_week, key=lambda t: t["profit_loss_pct"])
    worst = min(closed_this_week, key=lambda t: t["profit_loss_pct"])

    lines.append(f"**Trades Closed:** {len(closed_this_week)}")
    lines.append(f"**Win Rate:** {win_rate:.1f}%")
    lines.append(f"**Avg Gain:** {avg_gain:+.2f}%   **Avg Loss:** {avg_loss:+.2f}%")
    lines.append(f"**Best Trade:** {best['ticker']} ({best['profit_loss_pct']:+.2f}%)")
    lines.append(f"**Worst Trade:** {worst['ticker']} ({worst['profit_loss_pct']:+.2f}%)")
    return "\n".join(lines)


def post_paper_trading_weekly_summary() -> bool:
    return send_to_discord("alerts", build_paper_trading_weekly_summary_message(), username="Trading Engine")


def post_system_status(success: bool, detail: str = "") -> bool:
    icon = "✅" if success else "❌"
    status = "completed successfully" if success else "failed"
    message = f"{icon} Daily Discord update {status}."
    if detail:
        message += f"\n{detail}"
    return send_to_discord("system_status", message, username="System")


def run_daily_discord_updates() -> None:
    errors = []

    try:
        post_market_briefing()
    except Exception as e:
        errors.append(f"Market briefing failed: {e}")

    try:
        post_alerts()
    except Exception as e:
        errors.append(f"Alerts failed: {e}")

    try:
        post_news()
    except Exception as e:
        errors.append(f"News failed: {e}")

    try:
        post_watchlist()
    except Exception as e:
        errors.append(f"Watchlist failed: {e}")

    try:
        post_ai_cost_report()
    except Exception as e:
        errors.append(f"AI cost report failed: {e}")

    try:
        post_paper_trading_daily_summary()
    except Exception as e:
        errors.append(f"Paper trading summary failed: {e}")

    if errors:
        post_system_status(success=False, detail="\n".join(errors))
    else:
        post_system_status(success=True)


if __name__ == "__main__":
    run_daily_discord_updates()
