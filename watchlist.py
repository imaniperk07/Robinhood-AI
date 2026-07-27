import yfinance as yf

# Edit this list anytime to add/remove stocks — no other code needs to change.
WATCHLIST = ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM", "KO", "DIS", "TSLA", "AMD"]


def format_market_cap(value: float | None) -> str:
    """Turn a raw market cap number into something readable, like $2.95T."""
    if value is None:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    elif value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    else:
        return f"${value:,.0f}"


def get_stock_data(ticker: str) -> dict | None:
    """Fetch price, % changes, volume, and market cap for one stock."""
    stock = yf.Ticker(ticker)

    # 2 months of daily data gives us enough history for daily/weekly/monthly comparisons.
    history = stock.history(period="2mo")
    if history.empty:
        print(f"Couldn't get price history for {ticker}.")
        return None

    closes = history["Close"]
    latest_price = closes.iloc[-1]
    latest_volume = history["Volume"].iloc[-1]

    # Daily change: compare to previous trading day.
    daily_pct = None
    if len(closes) >= 2:
        daily_pct = ((latest_price - closes.iloc[-2]) / closes.iloc[-2]) * 100

    # Weekly change: compare to ~5 trading days ago.
    weekly_pct = None
    if len(closes) >= 6:
        weekly_pct = ((latest_price - closes.iloc[-6]) / closes.iloc[-6]) * 100

    # Monthly change: compare to ~21 trading days ago.
    monthly_pct = None
    if len(closes) >= 22:
        monthly_pct = ((latest_price - closes.iloc[-22]) / closes.iloc[-22]) * 100

    # Market cap requires a separate, slower lookup.
    market_cap = None
    try:
        market_cap = stock.info.get("marketCap")
    except Exception:
        pass  # If this fails, we just show "N/A" — no crash.

    return {
        "ticker": ticker,
        "price": latest_price,
        "daily_pct": daily_pct,
        "weekly_pct": weekly_pct,
        "monthly_pct": monthly_pct,
        "volume": latest_volume,
        "market_cap": market_cap,
    }


def format_pct(value: float | None) -> str:
    if value is None:
        return "  N/A  "
    arrow = "▲" if value >= 0 else "▼"
    return f"{arrow} {value:+.2f}%"


def print_watchlist() -> None:
    print("=" * 80)
    print("                              WATCHLIST")
    print("=" * 80)
    header = f"{'Ticker':<8}{'Price':<12}{'Daily':<12}{'Weekly':<12}{'Monthly':<12}{'Volume':<14}{'Market Cap':<10}"
    print(header)
    print("-" * 80)

    for ticker in WATCHLIST:
        data = get_stock_data(ticker)
        if data is None:
            continue

        row = (
            f"{data['ticker']:<8}"
            f"${data['price']:<11.2f}"
            f"{format_pct(data['daily_pct']):<12}"
            f"{format_pct(data['weekly_pct']):<12}"
            f"{format_pct(data['monthly_pct']):<12}"
            f"{data['volume']:,.0f}".ljust(14)
            + f"{format_market_cap(data['market_cap']):<10}"
        )
        print(row)

    print("=" * 80)


if __name__ == "__main__":
    print_watchlist()