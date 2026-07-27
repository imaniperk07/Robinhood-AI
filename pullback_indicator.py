import yfinance as yf
from technical_analysis import calculate_rsi, calculate_bollinger_bands

WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD", "VOO", "AEHL", "OMH"]

RSI_OVERBOUGHT_THRESHOLD = 65
BOLLINGER_STRETCH_THRESHOLD = 0.8
CONSECUTIVE_UP_DAYS_THRESHOLD = 4


def check_rsi_turning_down(closes) -> tuple[bool, str]:
    rsi_series = calculate_rsi(closes)
    if len(rsi_series.dropna()) < 3:
        return False, ""

    latest_rsi = rsi_series.iloc[-1]
    previous_rsi = rsi_series.iloc[-2]

    if latest_rsi >= RSI_OVERBOUGHT_THRESHOLD and latest_rsi < previous_rsi:
        return True, f"RSI overbought at {latest_rsi:.1f} and turning down from {previous_rsi:.1f}"
    return False, ""


def check_bollinger_stretch(closes) -> tuple[bool, str]:
    upper, mid, lower = calculate_bollinger_bands(closes)
    latest_price = closes.iloc[-1]
    band_width = upper.iloc[-1] - lower.iloc[-1]

    if band_width <= 0:
        return False, ""

    position = (latest_price - lower.iloc[-1]) / band_width
    if position >= BOLLINGER_STRETCH_THRESHOLD:
        return True, f"Price stretched near upper Bollinger Band ({position * 100:.0f}% of the band)"
    return False, ""


def check_consecutive_up_days(closes) -> tuple[bool, str]:
    if len(closes) < CONSECUTIVE_UP_DAYS_THRESHOLD + 1:
        return False, ""

    recent_changes = closes.diff().iloc[-CONSECUTIVE_UP_DAYS_THRESHOLD:]
    if all(change > 0 for change in recent_changes):
        return True, f"Price has risen {CONSECUTIVE_UP_DAYS_THRESHOLD}+ days in a row without a pullback"
    return False, ""


def check_weakening_volume(history) -> tuple[bool, str]:
    if len(history) < 8:
        return False, ""

    closes = history["Close"]
    volumes = history["Volume"]

    recent_price_change = closes.iloc[-1] - closes.iloc[-4]
    recent_avg_volume = volumes.iloc[-3:].mean()
    prior_avg_volume = volumes.iloc[-6:-3].mean()

    if recent_price_change > 0 and recent_avg_volume < prior_avg_volume * 0.85:
        return True, "Price still climbing but volume is fading — weaker conviction behind the move"
    return False, ""


def check_pullback_risk(ticker: str) -> dict | None:
    stock = yf.Ticker(ticker)
    history = stock.history(period="3mo")

    if history.empty or len(history) < 20:
        return None

    closes = history["Close"]
    signals = []

    for check_fn in (check_rsi_turning_down, check_bollinger_stretch, check_consecutive_up_days):
        fired, message = check_fn(closes)
        if fired:
            signals.append(message)

    fired, message = check_weakening_volume(history)
    if fired:
        signals.append(message)

    if len(signals) >= 3:
        risk_level = "HIGH"
    elif len(signals) == 2:
        risk_level = "MODERATE"
    elif len(signals) == 1:
        risk_level = "LOW"
    else:
        risk_level = "NONE"

    return {
        "ticker": ticker,
        "risk_level": risk_level,
        "signal_count": len(signals),
        "signals": signals,
    }


def run_pullback_check() -> None:
    print("=" * 70)
    print("PULLBACK INDICATOR")
    print("=" * 70)
    print("(Pattern-based, not a prediction — shows how many warning signs are stacking up)\n")

    results = []
    for ticker in WATCHLIST:
        result = check_pullback_risk(ticker)
        if result:
            results.append(result)

    results.sort(key=lambda r: r["signal_count"], reverse=True)

    for r in results:
        if r["risk_level"] == "NONE":
            continue

        icon = {"HIGH": "🔴", "MODERATE": "🟡", "LOW": "🟢"}[r["risk_level"]]
        print(f"{icon} {r['ticker']} — {r['risk_level']} ({r['signal_count']}/4 signals)")
        for signal in r["signals"]:
            print(f"    - {signal}")
        print()

    quiet_tickers = [r["ticker"] for r in results if r["risk_level"] == "NONE"]
    if quiet_tickers:
        print(f"No pullback signals: {', '.join(quiet_tickers)}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_pullback_check()