import yfinance as yf
import pandas as pd
import numpy as np
import talib

WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD"]


def calculate_sma(closes: pd.Series, window: int) -> pd.Series:
    return closes.rolling(window=window).mean()


def calculate_ema(closes: pd.Series, span: int) -> pd.Series:
    return closes.ewm(span=span, adjust=False).mean()


def calculate_rsi(closes: pd.Series, window: int = 14) -> pd.Series:
    delta = closes.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.rolling(window=window).mean()
    avg_loss = losses.rolling(window=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(closes: pd.Series) -> tuple[pd.Series, pd.Series]:
    ema_12 = calculate_ema(closes, 12)
    ema_26 = calculate_ema(closes, 26)
    macd_line = ema_12 - ema_26
    signal_line = calculate_ema(macd_line, 9)
    return macd_line, signal_line


def calculate_bollinger_bands(closes: pd.Series, window: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    sma = calculate_sma(closes, window)
    std = closes.rolling(window=window).std()
    upper_band = sma + (2 * std)
    lower_band = sma - (2 * std)
    return upper_band, sma, lower_band


def calculate_support_resistance(history: pd.DataFrame, window: int = 20) -> tuple[float, float]:
    recent = history.tail(window)
    support = recent["Low"].min()
    resistance = recent["High"].max()
    return support, resistance


def detect_candlestick_patterns(history: pd.DataFrame) -> list[dict]:
    """Runs every TA-Lib candlestick pattern function against the most recent candle.
    Returns only patterns that actually fired, as [{"name": "Engulfing", "signal": "Bullish"}, ...] —
    a pattern firing doesn't mean the trade is good on its own, just that it's present;
    callers should weigh it against trend context and support/resistance location."""
    o, h, l, c = history["Open"], history["High"], history["Low"], history["Close"]
    detected = []
    for func_name in (f for f in dir(talib) if f.startswith("CDL")):
        result = getattr(talib, func_name)(o, h, l, c)
        latest = result.iloc[-1]
        if latest != 0:
            detected.append({"name": func_name.replace("CDL", ""), "signal": "Bullish" if latest > 0 else "Bearish"})
    return detected


def interpret_rsi(rsi_value: float) -> str:
    if rsi_value >= 70:
        return f"RSI is {rsi_value:.1f} — approaching overbought territory. This means the stock has risen quickly and could be due for a pause or pullback (not a guarantee)."
    elif rsi_value <= 30:
        return f"RSI is {rsi_value:.1f} — approaching oversold territory. This means the stock has sold off quickly and could be due for a bounce (not a guarantee)."
    else:
        return f"RSI is {rsi_value:.1f} — neutral territory, no strong overbought/oversold signal right now."


def interpret_macd(macd_value: float, signal_value: float) -> str:
    if macd_value > signal_value:
        return "MACD line is above the signal line — often read as bullish momentum."
    else:
        return "MACD line is below the signal line — often read as bearish momentum."


def interpret_trend(price: float, sma_20: float, sma_50: float) -> str:
    if price > sma_20 > sma_50:
        return "Price is above both its 20-day and 50-day averages — a common sign of an uptrend."
    elif price < sma_20 < sma_50:
        return "Price is below both its 20-day and 50-day averages — a common sign of a downtrend."
    else:
        return "Price is mixed relative to its short and long-term averages — no clear trend direction."


def interpret_bollinger(price: float, upper: float, lower: float) -> str:
    band_width = upper - lower
    position = (price - lower) / band_width if band_width > 0 else 0.5
    if position >= 0.8:
        return "Price is near the upper Bollinger Band — stretched relative to its recent volatility."
    elif position <= 0.2:
        return "Price is near the lower Bollinger Band — stretched to the downside relative to recent volatility."
    else:
        return "Price is within its normal recent volatility range."


def analyze_stock(ticker: str) -> None:
    stock = yf.Ticker(ticker)
    history = stock.history(period="6mo")

    if history.empty or len(history) < 50:
        print(f"Not enough data to analyze {ticker}.")
        return

    closes = history["Close"]
    latest_price = closes.iloc[-1]

    sma_20 = calculate_sma(closes, 20).iloc[-1]
    sma_50 = calculate_sma(closes, 50).iloc[-1]
    rsi = calculate_rsi(closes).iloc[-1]
    macd_line, signal_line = calculate_macd(closes)
    upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)
    support, resistance = calculate_support_resistance(history)

    print("=" * 70)
    print(f"{ticker} — Technical Analysis")
    print("=" * 70)
    print(f"Current Price: ${latest_price:.2f}")
    print(f"20-day SMA: ${sma_20:.2f}   |   50-day SMA: ${sma_50:.2f}")
    print(f"Support: ${support:.2f}   |   Resistance: ${resistance:.2f}")
    print("-" * 70)
    print(interpret_trend(latest_price, sma_20, sma_50))
    print(interpret_rsi(rsi))
    print(interpret_macd(macd_line.iloc[-1], signal_line.iloc[-1]))
    print(interpret_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1]))
    print("=" * 70)
    print()


def run_technical_analysis() -> None:
    for ticker in WATCHLIST:
        analyze_stock(ticker)


if __name__ == "__main__":
    run_technical_analysis()