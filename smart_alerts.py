import yfinance as yf
from technical_analysis import calculate_sma, calculate_rsi

WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD", "VOO", "AEHL", "OMH"]

# Adjustable thresholds — tune these once you see how sensitive they feel.
LARGE_MOVE_THRESHOLD_PCT = 3.0
VOLUME_SPIKE_MULTIPLIER = 2.0
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30


def check_large_move(closes) -> str | None:
    if len(closes) < 2:
        return None
    latest = closes.iloc[-1]
    previous = closes.iloc[-2]
    pct_change = ((latest - previous) / previous) * 100
    if abs(pct_change) >= LARGE_MOVE_THRESHOLD_PCT:
        direction = "up" if pct_change > 0 else "down"
        return f"Large price move: {direction} {pct_change:+.2f}% today"
    return None


def check_volume_spike(history) -> str | None:
    if len(history) < 21:
        return None
    volumes = history["Volume"]
    today_volume = volumes.iloc[-1]
    avg_volume_20d = volumes.iloc[-21:-1].mean()
    if avg_volume_20d > 0 and today_volume >= avg_volume_20d * VOLUME_SPIKE_MULTIPLIER:
        multiple = today_volume / avg_volume_20d
        return f"Volume spike: {multiple:.1f}x the 20-day average volume"
    return None


def check_rsi_extreme(closes) -> str | None:
    rsi_series = calculate_rsi(closes)
    if rsi_series.empty:
        return None
    latest_rsi = rsi_series.iloc[-1]
    if latest_rsi >= RSI_OVERBOUGHT:
        return f"RSI overbought: {latest_rsi:.1f} (≥ {RSI_OVERBOUGHT})"
    elif latest_rsi <= RSI_OVERSOLD:
        return f"RSI oversold: {latest_rsi:.1f} (≤ {RSI_OVERSOLD})"
    return None


def check_ma_crossover(closes) -> str | None:
    sma_50 = calculate_sma(closes, 50)
    if len(sma_50.dropna()) < 2 or len(closes) < 2:
        return None

    price_today = closes.iloc[-1]
    price_yesterday = closes.iloc[-2]
    sma_today = sma_50.iloc[-1]
    sma_yesterday = sma_50.iloc[-2]

    crossed_above = price_yesterday <= sma_yesterday and price_today > sma_today
    crossed_below = price_yesterday >= sma_yesterday and price_today < sma_today

    if crossed_above:
        return "Moving average crossover: price just crossed ABOVE its 50-day SMA (often read as bullish)"
    elif crossed_below:
        return "Moving average crossover: price just crossed BELOW its 50-day SMA (often read as bearish)"
    return None


def check_ticker(ticker: str) -> list[str]:
    stock = yf.Ticker(ticker)
    history = stock.history(period="3mo")
    if history.empty or len(history) < 25:
        return []

    closes = history["Close"]
    alerts = []

    for check in (check_large_move, check_rsi_extreme, check_ma_crossover):
        result = check(closes)
        if result:
            alerts.append(result)

    volume_result = check_volume_spike(history)
    if volume_result:
        alerts.append(volume_result)

    return alerts


def run_smart_alerts() -> None:
    print("=" * 70)
    print("SMART ALERTS")
    print("=" * 70)

    any_alerts = False
    for ticker in WATCHLIST:
        alerts = check_ticker(ticker)
        if alerts:
            any_alerts = True
            print(f"\n{ticker}:")
            for alert in alerts:
                print(f"  ⚠️  {alert}")

    if not any_alerts:
        print("\nNo alerts triggered today — nothing crossed a threshold.")

    print()
    print("=" * 70)


if __name__ == "__main__":
    run_smart_alerts()