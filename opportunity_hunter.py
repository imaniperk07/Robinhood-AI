import yfinance as yf

from smart_alerts import check_large_move, check_volume_spike, check_ma_crossover
from athena import analyze_stock

# A curated universe grouped by theme — not a live screener, just a hand-picked
# starting set per category. Edit these lists anytime to add/remove tickers.
UNIVERSE = {
    "AI & Software": ["MSFT", "GOOGL", "META", "PLTR", "CRM", "NOW", "SNOW", "ORCL"],
    "Semiconductors": ["NVDA", "AMD", "AVGO", "TSM", "QCOM", "MU", "INTC", "ASML"],
    "Healthcare": ["UNH", "LLY", "ABBV", "JNJ", "PFE", "ISRG", "VRTX", "REGN"],
    "Small-Cap Growth": ["SOFI", "RBLX", "UPST", "AFRM", "IONQ", "ASTS", "RIVN", "SMCI"],
    "Value / Dividend": ["KO", "PG", "XOM", "CVX", "T", "VZ", "MO", "IBM"],
    "Penny / Speculative": ["SNDL", "NOK", "PLUG", "FCEL", "GEVO", "CLOV", "BBIG"],
}

PENNY_STOCK_THRESHOLD = 5.0


def scan_theme(theme: str) -> list[dict]:
    """Scan every ticker in one theme: price, technical signals, and Athena's confidence score."""
    tickers = UNIVERSE.get(theme, [])
    results = []

    for ticker in tickers:
        stock = yf.Ticker(ticker)
        history = stock.history(period="3mo")
        if history.empty or len(history) < 25:
            continue

        closes = history["Close"]
        price = closes.iloc[-1]
        daily_pct = ((price - closes.iloc[-2]) / closes.iloc[-2] * 100) if len(closes) >= 2 else None

        signals = []
        for check_fn in (check_large_move, check_ma_crossover):
            signal = check_fn(closes)
            if signal:
                signals.append(signal)
        volume_signal = check_volume_spike(history)
        if volume_signal:
            signals.append(volume_signal)

        athena_result = analyze_stock(ticker)
        confidence_score = athena_result["confidence_score"] if athena_result else None

        results.append({
            "ticker": ticker,
            "price": round(float(price), 2),
            "daily_pct": round(float(daily_pct), 2) if daily_pct is not None else None,
            "signals": signals,
            "confidence_score": confidence_score,
            "is_penny_stock": price < PENNY_STOCK_THRESHOLD,
        })

    results.sort(key=lambda r: (r["confidence_score"] or 0), reverse=True)
    return results


def print_scan(theme: str) -> None:
    results = scan_theme(theme)
    if not results:
        print(f"No data available for theme '{theme}'.")
        return

    print("=" * 70)
    print(f"OPPORTUNITY HUNTER — {theme}")
    print("=" * 70)
    for r in results:
        score_str = f"{r['confidence_score']}/100" if r["confidence_score"] is not None else "N/A"
        penny_flag = " [SPECULATIVE — penny stock]" if r["is_penny_stock"] else ""
        pct_str = f"{r['daily_pct']:+.2f}%" if r["daily_pct"] is not None else "N/A"
        print(f"\n{r['ticker']}{penny_flag} — ${r['price']:.2f} ({pct_str}) — Score: {score_str}")
        if r["signals"]:
            for s in r["signals"]:
                print(f"  ⚡ {s}")
        else:
            print("  No active technical signals right now.")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import sys
    theme_arg = sys.argv[1] if len(sys.argv) > 1 else list(UNIVERSE.keys())[0]
    print_scan(theme_arg)
