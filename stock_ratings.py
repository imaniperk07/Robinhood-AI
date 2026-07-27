import yfinance as yf

from technical_analysis import (
    calculate_sma,
    calculate_rsi,
    calculate_macd,
    calculate_bollinger_bands,
)
from news_analysis import get_news, rough_tag

WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD"]


def score_trend(price: float, sma_20: float, sma_50: float) -> tuple[int, str]:
    if price > sma_20 > sma_50:
        return 25, "Uptrend (price above both moving averages)"
    elif price < sma_20 < sma_50:
        return 0, "Downtrend (price below both moving averages)"
    else:
        return 12, "Mixed trend"


def score_rsi(rsi: float) -> tuple[int, str]:
    if 40 <= rsi <= 60:
        return 20, f"RSI {rsi:.1f} — healthy neutral zone"
    elif 30 <= rsi < 40 or 60 < rsi <= 70:
        return 12, f"RSI {rsi:.1f} — leaning toward an extreme"
    else:
        return 5, f"RSI {rsi:.1f} — overbought/oversold territory"


def score_macd(macd_value: float, signal_value: float) -> tuple[int, str]:
    if macd_value > signal_value:
        return 20, "MACD above signal line (bullish momentum)"
    else:
        return 0, "MACD below signal line (bearish momentum)"


def score_bollinger(price: float, upper: float, lower: float) -> tuple[int, str]:
    band_width = upper - lower
    position = (price - lower) / band_width if band_width > 0 else 0.5
    if 0.35 <= position <= 0.65:
        return 15, "Price sitting comfortably within its normal range"
    elif position > 0.8 or position < 0.2:
        return 5, "Price stretched near the edge of its recent range"
    else:
        return 10, "Price moderately away from center of its recent range"


def score_news(ticker: str) -> tuple[int, str]:
    articles = get_news(ticker, max_articles=5)
    if not articles:
        return 10, "No recent news found (neutral default)"

    positive_count = 0
    negative_count = 0
    for article in articles:
        tag = rough_tag(article.get("title", ""))
        if tag == "Possibly Positive":
            positive_count += 1
        elif tag == "Possibly Negative":
            negative_count += 1

    if positive_count > negative_count:
        return 20, f"More positive-leaning headlines ({positive_count} vs {negative_count})"
    elif negative_count > positive_count:
        return 0, f"More negative-leaning headlines ({negative_count} vs {positive_count})"
    else:
        return 10, "Roughly equal positive/negative headlines"


def rate_stock(ticker: str) -> None:
    stock = yf.Ticker(ticker)
    history = stock.history(period="6mo")
    if history.empty or len(history) < 50:
        print(f"Not enough data to rate {ticker}.")
        return

    closes = history["Close"]
    latest_price = closes.iloc[-1]
    sma_20 = calculate_sma(closes, 20).iloc[-1]
    sma_50 = calculate_sma(closes, 50).iloc[-1]
    rsi = calculate_rsi(closes).iloc[-1]
    macd_line, signal_line = calculate_macd(closes)
    upper_band, mid_band, lower_band = calculate_bollinger_bands(closes)

    trend_points, trend_note = score_trend(latest_price, sma_20, sma_50)
    rsi_points, rsi_note = score_rsi(rsi)
    macd_points, macd_note = score_macd(macd_line.iloc[-1], signal_line.iloc[-1])
    boll_points, boll_note = score_bollinger(latest_price, upper_band.iloc[-1], lower_band.iloc[-1])
    news_points, news_note = score_news(ticker)

    total = trend_points + rsi_points + macd_points + boll_points + news_points

    print("=" * 70)
    print(f"{ticker} — Overall Score: {total} / 100")
    print("=" * 70)
    print(f"Trend:      {trend_points:>3}/25   — {trend_note}")
    print(f"RSI:        {rsi_points:>3}/20   — {rsi_note}")
    print(f"MACD:       {macd_points:>3}/20   — {macd_note}")
    print(f"Bollinger:  {boll_points:>3}/15   — {boll_note}")
    print(f"News tone:  {news_points:>3}/20   — {news_note}")
    print("=" * 70)
    print()


def run_stock_ratings() -> None:
    for ticker in WATCHLIST:
        rate_stock(ticker)


if __name__ == "__main__":
    run_stock_ratings()