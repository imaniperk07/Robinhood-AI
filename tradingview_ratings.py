from tradingview_ta import TA_Handler, Interval

# TA_Handler needs a specific exchange — try the common US ones in order since
# our watchlist/portfolio tickers don't carry exchange metadata anywhere else.
COMMON_EXCHANGES = ["NASDAQ", "NYSE", "AMEX"]


def get_rating(ticker: str) -> dict | None:
    """TradingView's aggregated technical-ratings summary for a ticker — read-only,
    no login required. Returns {"RECOMMENDATION": "BUY"|"SELL"|"NEUTRAL", "BUY": int,
    "SELL": int, "NEUTRAL": int} (oscillator + moving-average vote counts), or None if
    the ticker can't be resolved on any common exchange. This is a bonus signal, never
    a hard dependency — callers should treat None as "no rating available," not an error."""
    for exchange in COMMON_EXCHANGES:
        try:
            handler = TA_Handler(
                symbol=ticker, screener="america", exchange=exchange, interval=Interval.INTERVAL_1_DAY,
            )
            return handler.get_analysis().summary
        except Exception:
            continue
    return None


if __name__ == "__main__":
    for test_ticker in ["AAPL", "TSLA", "NOTAREALTICKER"]:
        print(test_ticker, "->", get_rating(test_ticker))
