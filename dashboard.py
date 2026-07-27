import yfinance as yf

# The tickers Yahoo Finance uses for major indices
INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "Dow Jones": "^DJI",
    "VIX": "^VIX",
}


def get_index_data(name: str, ticker: str) -> dict | None:
    """Fetch the latest price and daily % change for one index."""
    data = yf.Ticker(ticker).history(period="5d")
    if data.empty or len(data) < 2:
        print(f"Couldn't get data for {name} ({ticker}).")
        return None

    latest_close = data["Close"].iloc[-1]
    previous_close = data["Close"].iloc[-2]
    percent_change = ((latest_close - previous_close) / previous_close) * 100

    return {
        "name": name,
        "price": latest_close,
        "change_pct": percent_change,
    }


def simplified_fear_greed(vix_price: float) -> str:
    """
    A simplified, VIX-based stand-in for the real Fear & Greed Index.
    This is NOT the official CNN index — just a rough, transparent proxy.
    """
    if vix_price < 15:
        return "Extreme Greed (very low volatility)"
    elif vix_price < 20:
        return "Greed"
    elif vix_price < 25:
        return "Neutral"
    elif vix_price < 30:
        return "Fear"
    else:
        return "Extreme Fear (high volatility)"


def overall_sentiment(index_results: list[dict]) -> str:
    """Give a plain-English read on overall market direction today."""
    # Exclude VIX itself from the "how many are up" count — it's a volatility
    # measure, not a market direction measure.
    directional = [r for r in index_results if r["name"] != "VIX"]
    up_count = sum(1 for r in directional if r["change_pct"] > 0)

    if up_count == len(directional):
        return "Bullish — all major indices are up today."
    elif up_count == 0:
        return "Bearish — all major indices are down today."
    else:
        return "Mixed — indices are moving in different directions today."


def print_dashboard() -> None:
    print("=" * 40)
    print("       MARKET DASHBOARD")
    print("=" * 40)

    results = []
    for name, ticker in INDICES.items():
        result = get_index_data(name, ticker)
        if result:
            results.append(result)
            arrow = "▲" if result["change_pct"] >= 0 else "▼"
            print(f"{result['name']:<10} ${result['price']:.2f}   {arrow} {result['change_pct']:+.2f}%")

    print("-" * 40)

    vix_result = next((r for r in results if r["name"] == "VIX"), None)
    if vix_result:
        print(f"Simplified Fear/Greed Gauge: {simplified_fear_greed(vix_result['price'])}")

    print(f"Overall Sentiment: {overall_sentiment(results)}")
    print("=" * 40)


if __name__ == "__main__":
    print_dashboard()