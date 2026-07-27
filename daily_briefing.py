import yfinance as yf
from dashboard import INDICES, get_index_data, simplified_fear_greed, overall_sentiment
from smart_alerts import check_ticker, WATCHLIST
from news_analysis import get_news

USER_NAME = "Imani"  # Edit this anytime to personalize your briefing


def get_market_overview() -> tuple[str, str]:
    results = []
    for name, ticker in INDICES.items():
        result = get_index_data(name, ticker)
        if result:
            results.append(result)

    vix_result = next((r for r in results if r["name"] == "VIX"), None)
    fear_greed = simplified_fear_greed(vix_result["price"]) if vix_result else "Unavailable"
    sentiment = overall_sentiment(results)
    return fear_greed, sentiment


def summarize_alert(alert: str) -> str:
    """Turn a detailed alert string into a short highlight phrase."""
    if "Large price move: up" in alert:
        return "Strong momentum"
    elif "Large price move: down" in alert:
        return "Selling off"
    elif "Volume spike" in alert:
        return "High volume breakout"
    elif "RSI overbought" in alert:
        return "Approaching overbought territory"
    elif "RSI oversold" in alert:
        return "Approaching oversold territory"
    elif "crossed ABOVE" in alert:
        return "Bullish crossover"
    elif "crossed BELOW" in alert:
        return "Bearish crossover"
    else:
        return alert


def get_watchlist_highlights() -> list[tuple[str, str]]:
    """Return (ticker, short highlight) for every ticker that triggered at least one alert."""
    highlights = []
    for ticker in WATCHLIST:
        alerts = check_ticker(ticker)
        if alerts:
            highlights.append((ticker, summarize_alert(alerts[0])))
    return highlights


def get_top_news_story() -> str | None:
    """Grab one recent headline from across the watchlist to feature."""
    for ticker in WATCHLIST:
        articles = get_news(ticker, max_articles=1)
        if articles:
            title = articles[0].get("title", "")
            source = articles[0].get("source", {}).get("name", "Unknown source")
            return f"{title} ({source})"
    return None


def get_highest_risk_ticker() -> str | None:
    """Find the ticker with the largest absolute daily % move today."""
    biggest_ticker = None
    biggest_move = 0.0
    for ticker in WATCHLIST:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5d")
        if history.empty or len(history) < 2:
            continue
        closes = history["Close"]
        pct_change = abs((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100)
        if pct_change > biggest_move:
            biggest_move = pct_change
            biggest_ticker = ticker
    return biggest_ticker


def print_daily_briefing() -> None:
    print(f"Good morning, {USER_NAME}.\n")

    fear_greed, sentiment = get_market_overview()
    print(f"Market Sentiment:\n{sentiment}\n")
    print(f"Fear & Greed (simplified):\n{fear_greed}\n")

    print("Watchlist Highlights\n")
    highlights = get_watchlist_highlights()
    if highlights:
        for ticker, note in highlights:
            print(f"{ticker}:\n{note}\n")
    else:
        print("Nothing notable today.\n")

    print("Today's News\n")
    top_story = get_top_news_story()
    print(f"{top_story}\n" if top_story else "No recent headlines found.\n")

    print("Highest Risk\n")
    highest_risk = get_highest_risk_ticker()
    print(f"{highest_risk}\n" if highest_risk else "Not enough data to determine.\n")


if __name__ == "__main__":
    print_daily_briefing()