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
    CONFIDENCE_THRESHOLD, POSITION_SIZE_USD, MIN_REWARD_RISK_RATIO,
)
from day_trade_decision_engine import gather_day_signals, passes_day_prefilter, evaluate_day_trade
from discord_notifier import post_trade_opened, post_trade_closed
from alpaca_mirror import mirror_open_trade, mirror_close_trade, get_client as get_alpaca_client

MONITOR_INTERVAL_SECONDS = 5 * 60    # fast loop: pure price checks on open trades
SCAN_INTERVAL_SECONDS = 60 * 60      # slow loop: evaluate new swing candidates + thesis decay
DAY_SCAN_INTERVAL_SECONDS = 5 * 60   # day-trade loop: much faster, gated on real market hours
MAX_HOLDING_DAYS = 20                # hard expiry cap for a swing trade
THESIS_DECAY_ATHENA_FLOOR = 40       # if Athena confidence drops below this, thesis is suspect
MAX_CANDIDATES_PER_SCAN = 10         # hard cap on NewsAPI+Claude spend per cycle, regardless
                                      # of how many clear the (deliberately loose) pre-filter
MAX_DAY_CANDIDATES_PER_SCAN = 10     # same idea for the day-trade loop's Claude spend


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
            strength = signals["athena"]["confidence_score"] + signals["technical"]["score_100"]
            shortlist.append((strength, ticker, signals))

    print(f"  {len(shortlist)} candidate(s) passed the pre-filter.")

    # Cap NewsAPI+Claude spend per cycle regardless of how many clear the pre-filter —
    # take only the strongest few, ranked by combined Athena + technical score, so a
    # loose day for the market can't blow the free-tier news quota in one cycle.
    shortlist.sort(key=lambda row: row[0], reverse=True)
    shortlist = shortlist[:MAX_CANDIDATES_PER_SCAN]
    if shortlist:
        print(f"  Evaluating the top {len(shortlist)}: {', '.join(t for _, t, _ in shortlist)}")

    for _strength, ticker, signals in shortlist:
        print(f"  Evaluating {ticker}...")
        decision = evaluate_trade(ticker, signals, market_sentiment, portfolio_tickers)
        if not decision:
            print(f"    {ticker}: evaluation failed, skipping.")
            continue
        if decision["probability_score"] < CONFIDENCE_THRESHOLD:
            print(f"    {ticker}: score {decision['probability_score']} < threshold {CONFIDENCE_THRESHOLD}, skipping.")
            continue

        reward_risk_ratio = decision["target_pct"] / decision["stop_loss_pct"] if decision.get("stop_loss_pct") else 0
        if reward_risk_ratio < MIN_REWARD_RISK_RATIO:
            print(f"    {ticker}: reward:risk {reward_risk_ratio:.2f} < minimum {MIN_REWARD_RISK_RATIO}, skipping "
                  f"(target {decision['target_pct']}% / stop {decision['stop_loss_pct']}%).")
            continue

        entry_price = get_current_price(ticker)
        if entry_price is None:
            print(f"    {ticker}: couldn't get a current price, skipping.")
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
            "strategy_type": decision["strategy_type"], "primary_strategy": decision["primary_strategy"],
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
        try:
            mirror_open_trade(ticker, shares)
        except Exception as e:
            print(f"  Alpaca mirror failed: {e}")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Scan complete. Idling until the next cycle.")


def is_market_open() -> bool:
    """Real market-hours check via the Alpaca client already integrated for the mirror
    — the day-trade loop only means anything while the market is actually generating
    new intraday bars, and skipping outside those hours avoids wasted API calls on a
    5-minute cadence re-evaluating the same stale bar. Falls back to "always attempt"
    if Alpaca isn't configured (no keys), since there's no other real clock available."""
    client = get_alpaca_client()
    if client is None:
        return True
    try:
        return bool(client.get_clock().is_open)
    except Exception:
        return True


async def scan_for_day_trades() -> None:
    if not is_market_open():
        print(f"[{datetime.now(timezone.utc).isoformat()}] Market closed, skipping day-trade scan.")
        return

    print(f"[{datetime.now(timezone.utc).isoformat()}] Scanning for day trades...")
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
        signals = gather_day_signals(ticker)
        if passes_day_prefilter(signals):
            shortlist.append((ticker, signals))

    print(f"  {len(shortlist)} candidate(s) passed the day-trade pre-filter.")
    shortlist = shortlist[:MAX_DAY_CANDIDATES_PER_SCAN]
    if shortlist:
        print(f"  Evaluating: {', '.join(t for t, _ in shortlist)}")

    for ticker, signals in shortlist:
        print(f"  Evaluating {ticker}...")
        decision = evaluate_day_trade(ticker, signals, market_sentiment, portfolio_tickers)
        if not decision:
            print(f"    {ticker}: evaluation failed, skipping.")
            continue
        if decision["probability_score"] < CONFIDENCE_THRESHOLD:
            print(f"    {ticker}: score {decision['probability_score']} < threshold {CONFIDENCE_THRESHOLD}, skipping.")
            continue

        reward_risk_ratio = decision["target_pct"] / decision["stop_loss_pct"] if decision.get("stop_loss_pct") else 0
        if reward_risk_ratio < MIN_REWARD_RISK_RATIO:
            print(f"    {ticker}: reward:risk {reward_risk_ratio:.2f} < minimum {MIN_REWARD_RISK_RATIO}, skipping "
                  f"(target {decision['target_pct']}% / stop {decision['stop_loss_pct']}%).")
            continue

        entry_price = get_current_price(ticker)
        if entry_price is None:
            print(f"    {ticker}: couldn't get a current price, skipping.")
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
            "strategy_type": decision["strategy_type"], "primary_strategy": decision["primary_strategy"],
        }
        trade_id = storage.save_paper_trade(trade)
        storage.save_trade_journal_entry({
            "trade_id": trade_id, "original_thesis": decision["reason_for_entry"],
            "news_summary": decision["news_summary"], "technical_analysis": decision["technical_analysis"],
            "confidence_score": decision["probability_score"],
            "reason_entry_approved": f"Trade score {decision['probability_score']} >= threshold {CONFIDENCE_THRESHOLD}",
        })
        trade["id"] = trade_id
        print(f"  OPENED {ticker} @ ${entry_price:.2f} (score {decision['probability_score']}, {decision['primary_strategy']})")
        try:
            post_trade_opened(trade)
        except Exception as e:
            print(f"  Notification failed: {e}")
        try:
            mirror_open_trade(ticker, shares)
        except Exception as e:
            print(f"  Alpaca mirror failed: {e}")

    print(f"[{datetime.now(timezone.utc).isoformat()}] Day-trade scan complete.")


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
    try:
        mirror_close_trade(trade["ticker"])
    except Exception as e:
        print(f"  Alpaca mirror failed: {e}")


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
        elif trade.get("strategy_type") == "Day" and not is_market_open():
            # Day trades are meant to close out the same session — don't let one ride
            # overnight/across days waiting for a target/stop that was sized for minutes-
            # to-hours, not a multi-day hold.
            _close_trade(trade, updates, "Expired", f"End of session, target/stop not hit ({pl_pct:+.2f}%).")
        elif days_held >= MAX_HOLDING_DAYS:
            _close_trade(trade, updates, "Expired", f"Hit the {MAX_HOLDING_DAYS}-day holding cap without target/stop.")
        else:
            storage.update_paper_trade(trade["id"], updates)


async def check_thesis_decay() -> None:
    """Slow-loop check: has the setup meaningfully weakened since entry? Reuses only
    the cheap signals (no fresh Claude call per open position — that would multiply
    cost with every open trade) to decide whether to exit early as "AI Exit". Swing
    trades only — this is fundamentally-driven decay logic (Athena confidence), which
    doesn't apply to Day trades; those already get closed out at end of session regardless."""
    for trade in storage.get_open_paper_trades():
        if trade.get("strategy_type") == "Day":
            continue
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
    last_day_scan: datetime | None = None
    while True:
        await monitor_open_trades()
        now = datetime.now(timezone.utc)
        if last_scan is None or (now - last_scan).total_seconds() >= SCAN_INTERVAL_SECONDS:
            await scan_for_new_trades()
            await check_thesis_decay()
            last_scan = now
        if last_day_scan is None or (now - last_day_scan).total_seconds() >= DAY_SCAN_INTERVAL_SECONDS:
            await scan_for_day_trades()
            last_day_scan = now
        open_count = len(storage.get_open_paper_trades())
        print(f"[{datetime.now(timezone.utc).isoformat()}] Heartbeat — {open_count} open trade(s). Next check in {MONITOR_INTERVAL_SECONDS // 60} min.")
        await asyncio.sleep(MONITOR_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run())
