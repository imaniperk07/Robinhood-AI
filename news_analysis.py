import os
import requests
from dotenv import load_dotenv

load_dotenv()
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")

WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD", "VOO", "AEHL", "OMH"]

# Full company names help catch product-launch headlines that don't mention the ticker.
COMPANY_NAMES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "JPM": "JPMorgan",
    "JNJ": "Johnson & Johnson",
    "XOM": "Exxon",
    "KO": "Coca-Cola",
    "DIS": "Disney",
    "TSLA": "Tesla",
    "AMD": "AMD",
    "VOO": "Vanguard S&P 500",
    "AEHL": "Antelope Enterprise",
    "OMH": "Ohmyhome",
}

LAUNCH_KEYWORDS = ["unveils", "announces", "launches", "reveals", "debuts", "introduces", "new product", "new model"]

POSITIVE_WORDS = ["surge", "soar", "beat", "record", "growth", "upgrade", "rally", "strong", "gain", "profit"]
NEGATIVE_WORDS = ["plunge", "drop", "miss", "downgrade", "lawsuit", "recall", "slump", "cut", "loss", "investigation"]


def get_news(ticker: str, max_articles: int = 5) -> list[dict]:
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": ticker,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "apiKey": NEWSAPI_KEY,
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error fetching news for {ticker}: {response.status_code} - {response.text}")
        return []
    return response.json().get("articles", [])


def get_product_news(ticker: str, max_articles: int = 5) -> list[dict]:
    """Search specifically for product-launch style news using the company's full name."""
    company_name = COMPANY_NAMES.get(ticker, ticker)
    query = f'"{company_name}" AND (' + " OR ".join(LAUNCH_KEYWORDS) + ")"

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": max_articles,
        "apiKey": NEWSAPI_KEY,
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error fetching product news for {ticker}: {response.status_code} - {response.text}")
        return []
    return response.json().get("articles", [])


def get_market_wide_news(max_articles: int = 10) -> list[dict]:
    """Pull general business headlines that could affect the broader market."""
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "category": "business",
        "language": "en",
        "pageSize": max_articles,
        "apiKey": NEWSAPI_KEY,
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Error fetching market news: {response.status_code} - {response.text}")
        return []
    return response.json().get("articles", [])


def flag_watchlist_mentions(headline: str) -> list[str]:
    """Check if a general headline mentions any of your watchlist companies."""
    lowered = headline.lower()
    mentioned = []
    for ticker, name in COMPANY_NAMES.items():
        if name.lower() in lowered or ticker.lower() in lowered:
            mentioned.append(ticker)
    return mentioned


def rough_tag(headline: str) -> str:
    lowered = headline.lower()
    has_positive = any(word in lowered for word in POSITIVE_WORDS)
    has_negative = any(word in lowered for word in NEGATIVE_WORDS)
    if has_positive and not has_negative:
        return "Possibly Positive"
    elif has_negative and not has_positive:
        return "Possibly Negative"
    else:
        return "Neutral / Unclear"


def print_news_for_ticker(ticker: str) -> None:
    print("=" * 70)
    print(f"{ticker} — Recent Headlines")
    print("=" * 70)
    articles = get_news(ticker)
    if not articles:
        print("No articles found.")
    else:
        for article in articles:
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown source")
            tag = rough_tag(title)
            print(f"[{tag}] {title}")
            print(f"   Source: {source}")
    print()


def print_product_news_for_ticker(ticker: str) -> None:
    print("=" * 70)
    print(f"{ticker} — Product / Launch News")
    print("=" * 70)
    articles = get_product_news(ticker)
    if not articles:
        print("No product-launch news found recently.")
    else:
        for article in articles:
            title = article.get("title", "No title")
            source = article.get("source", {}).get("name", "Unknown source")
            print(f"📦 {title}")
            print(f"   Source: {source}")
    print()


def print_market_wide_news() -> None:
    print("=" * 70)
    print("Market-Wide News (Watch for Your Holdings)")
    print("=" * 70)
    articles = get_market_wide_news()
    if not articles:
        print("No market-wide news found.")
        print()
        return

    for article in articles:
        title = article.get("title", "No title")
        source = article.get("source", {}).get("name", "Unknown source")
        tag = rough_tag(title)
        mentions = flag_watchlist_mentions(title)

        mention_note = f"  ⚠️ Mentions: {', '.join(mentions)}" if mentions else ""
        print(f"[{tag}] {title}{mention_note}")
        print(f"   Source: {source}")
    print()


def run_news_analysis() -> None:
    for ticker in WATCHLIST:
        print_news_for_ticker(ticker)

    print("\n" + "#" * 70)
    print("PRODUCT / LAUNCH NEWS")
    print("#" * 70 + "\n")
    for ticker in WATCHLIST:
        print_product_news_for_ticker(ticker)

    print("\n" + "#" * 70)
    print("MARKET-WIDE NEWS")
    print("#" * 70 + "\n")
    print_market_wide_news()


if __name__ == "__main__":
    run_news_analysis()