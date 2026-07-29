import asyncio
from datetime import datetime, timezone

import yfinance as yf

from database import storage
from watchlist import WATCHLIST
from portfolio_assistant import get_snaptrade_positions
from opportunity_hunter import UNIVERSE
from wealth_builder import WEALTH_UNIVERSE
from trade_decision_engine import (
    gather_signals, passes_prefilter, evaluate_trade, get_market_sentiment,
    CONFIDENCE_THRESHOLD, POSITION_SIZE_USD,
)
from discord_notifier import post_trade_opened, post_trade_closed

MONITOR_INTERVAL_SECONDS = 5 * 60    # fast loop: pure price checks on open trades
SCAN_INTERVAL_SECONDS = 60 * 60      # slow loop: evaluate new candidates + thesis decay
MAX_HOLDING_DAYS = 20                # hard expiry cap for a swing trade
THESIS_DECAY_ATHENA_FLOOR = 40       # if Athena confidence drops below this, thesis is suspect


def get_candidate_tickers() -> list[str]:
    """Watchlist + current portfolio holdings + Opportunity Hunter's universe (minus
    Penny/Speculative — too noisy to validate a strategy against) + Wealth Builder's
    quality stock list. ETFs are excluded — better suited to buy-and-hold than swing trades."""
    tickers = set(WATCHLIST)
    try:
        tickers |= {h["ticker"] for h in get_snaptrade_positions()}
    except Exception:
        pass
    for theme, theme_tickers in UNIVERSE.items():
        if theme == "Penny / Speculative":
            continue
        tickers |= set(theme_tickers)
    tickers |= set(WEALTH_UNIVERSE.get("Quality & Dividend Stocks", []))
    return sorted(tickers)


def get_current_price(ticker: str) -> float | None:
    history = yf.Ticker(ticker).history(period="1d")
    if history.empty:
        return None
    return float(history["Close"].iloc[-1])


async def scan_for_new_trades() -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] Scanning for new trades...")
    open_trades = storage.get_open_paper_trades()
    open_tickers = {t["ticker"] for t in open_trades}

    try:
        portfolio_tickers = [h["ticker"] for h in get_snaptrade_positions()]
    except Exception:
        portfolio_tickers = []

    market_sentiment = get_market_sentiment()
    shortlist = []

    for ticker in get_candidate_tickers():
        if ticker in open_tickers:
            continue
        signals = gather_signals(ticker)
        if passes_prefilter(signals):
            shortlist.append((ticker, signals))

    print(f"  {len(shortlist)} candidate(s) passed the pre-filter.")

    for ticker, signals in shortlist:
        decision = evaluate_trade(ticker, signals, market_sentiment, portfolio_tickers)
        if not decision or decision["probability_score"] < CONFIDENCE_THRESHOLD:
            continue

        entry_price = get_current_price(ticker)
        if entry_price is None:
            continue

        target_price = entry_price * (1 + decision["target_pct"] / 100)
        stop_loss = entry_price * (1 - decision["stop_loss_pct"] / 100)
        shares = POSITION_SIZE_USD / entry_price
        now = datetime.now(timezone.utc).isoformat()

        trade = {
            "ticker": ticker, "entry_price": entry_price, "target_price": target_price,
            "stop_loss": stop_loss, "position_size_usd": POSITION_SIZE_USD, "shares": shares,
            "trade_score": decision["probability_score"], "athena_confidence": decision["athena_confidence"],
            "risk_level": decision["risk_level"], "reason_for_entry": decision["reason_for_entry"],
            "expected_holding_time": decision["expected_holding_time"], "date_opened": now,
            "status": "Open", "current_price": entry_price, "profit_loss_pct": 0.0,
            "highest_gain_pct": 0.0, "largest_drawdown_pct": 0.0, "days_held": 0,
        }
        trade_id = storage.save_paper_trade(trade)
        storage.save_trade_journal_entry({
            "trade_id": trade_id, "original_thesis": decision["reason_for_entry"],
            "news_summary": decision["news_summary"], "technical_analysis": decision["technical_analysis"],
            "confidence_score": decision["probability_score"],
            "reason_entry_approved": f"Trade score {decision['probability_score']} >= threshold {CONFIDENCE_THRESHOLD}",
        })
        trade["id"] = trade_id
        print(f"  OPENED {ticker} @ ${entry_price:.2f} (score {decision['probability_score']})")
        try:
            post_trade_opened(trade)
        except Exception as e:
            print(f"  Notification failed: {e}")


def _close_trade(trade: dict, updates: dict, exit_reason: str, lessons: str) -> None:
    updates["status"] = "Closed"
    updates["exit_reason"] = exit_reason
    updates["date_closed"] = datetime.now(timezone.utc).isoformat()
    storage.update_paper_trade(trade["id"], updates)

    pl_pct = updates.get("profit_loss_pct", trade.get("profit_loss_pct", 0.0))
    storage.update_trade_journal_entry(trade["id"], {
        "reason_exit_occurred": f"{exit_reason} ({pl_pct:+.2f}%)",
        "lessons_learned": lessons,
        "final_outcome": "WIN" if pl_pct > 0 else "LOSS",
    })
    trade.update(updates)
    print(f"  CLOSED {trade['ticker']} — {exit_reason} ({pl_pct:+.2f}%)")
    try:
        post_trade_closed(trade)
    except Exception as e:
        print(f"  Notification failed: {e}")


async def monitor_open_trades() -> None:
    """Fast, cheap loop — pure yfinance price checks, no NewsAPI/Claude."""
    for trade in storage.get_open_paper_trades():
        current_price = get_current_price(trade["ticker"])
        if current_price is None:
            continue

        entry_price = trade["entry_price"]
        pl_pct = (current_price - entry_price) / entry_price * 100
        highest_gain = max(trade["highest_gain_pct"] or 0.0, pl_pct)
        largest_drawdown = min(trade["largest_drawdown_pct"] or 0.0, pl_pct)
        days_held = (datetime.now(timezone.utc) - datetime.fromisoformat(trade["date_opened"])).days

        updates = {
            "current_price": current_price, "profit_loss_pct": pl_pct,
            "highest_gain_pct": highest_gain, "largest_drawdown_pct": largest_drawdown,
            "days_held": days_held,
        }

        if current_price >= trade["target_price"]:
            _close_trade(trade, updates, "Target Hit", f"Held {days_held}d, peak gain {highest_gain:+.2f}%.")
        elif current_price <= trade["stop_loss"]:
            _close_trade(trade, updates, "Stop Loss", f"Held {days_held}d, max drawdown {largest_drawdown:+.2f}%.")
        elif days_held >= MAX_HOLDING_DAYS:
            _close_trade(trade, updates, "Expired", f"Hit the {MAX_HOLDING_DAYS}-day holding cap without target/stop.")
        else:
            storage.update_paper_trade(trade["id"], updates)


async def check_thesis_decay() -> None:
    """Slow-loop check: has the setup meaningfully weakened since entry? Reuses only
    the cheap signals (no fresh Claude call per open position — that would multiply
    cost with every open trade) to decide whether to exit early as "AI Exit"."""
    for trade in storage.get_open_paper_trades():
        signals = gather_signals(trade["ticker"])
        athena = signals.get("athena")
        pullback = signals.get("pullback_risk")

        decayed = (
            (athena and athena["confidence_score"] < THESIS_DECAY_ATHENA_FLOOR)
            or (pullback and pullback["risk_level"] == "HIGH")
        )
        if not decayed:
            continue

        current_price = get_current_price(trade["ticker"])
        if current_price is None:
            continue
        pl_pct = (current_price - trade["entry_price"]) / trade["entry_price"] * 100
        reason = (
            f"Athena confidence fell to {athena['confidence_score']}" if athena and athena["confidence_score"] < THESIS_DECAY_ATHENA_FLOOR
            else "Pullback risk turned HIGH"
        )
        _close_trade(
            trade, {"current_price": current_price, "profit_loss_pct": pl_pct}, "AI Exit",
            f"Original thesis weakened ({reason}) — exited early rather than waiting for stop loss.",
        )


async def run() -> None:
    storage.init()
    print("Trading engine started.")
    last_scan: datetime | None = None
    while True:
        await monitor_open_trades()
        now = datetime.now(timezone.utc)
        if last_scan is None or (now - last_scan).total_seconds() >= SCAN_INTERVAL_SECONDS:
            await scan_for_new_trades()
            await check_thesis_decay()
            last_scan = now
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
