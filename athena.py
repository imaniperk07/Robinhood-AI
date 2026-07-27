import yfinance as yf


def get_fundamentals(ticker: str) -> dict | None:
    """Pull the raw fundamental data points Athena reasons about."""
    stock = yf.Ticker(ticker)
    try:
        info = stock.info
    except Exception:
        return None

    if not info or (info.get("currentPrice") is None and info.get("regularMarketPrice") is None):
        return None

    return {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "profit_margins": info.get("profitMargins"),
        "return_on_equity": info.get("returnOnEquity"),
        "debt_to_equity": info.get("debtToEquity"),
        "free_cashflow": info.get("freeCashflow"),
        "dividend_yield": info.get("dividendYield"),
        "target_mean_price": info.get("targetMeanPrice"),
        "recommendation_key": info.get("recommendationKey"),
    }


def score_valuation(f: dict) -> tuple[int, str]:
    pe = f["trailing_pe"]
    if pe is None:
        return 12, "P/E data unavailable — treating as neutral"
    if pe <= 0:
        return 8, f"Negative earnings (P/E {pe:.1f}) — hard to value on earnings alone"
    if pe < 15:
        return 25, f"P/E of {pe:.1f} is on the cheaper side historically"
    elif pe < 25:
        return 18, f"P/E of {pe:.1f} is in a fairly normal range"
    elif pe < 40:
        return 10, f"P/E of {pe:.1f} is on the expensive side — priced for strong future growth"
    else:
        return 4, f"P/E of {pe:.1f} is very high — a lot of optimism already priced in"


def score_growth(f: dict) -> tuple[int, str]:
    rev_growth = f["revenue_growth"]
    earn_growth = f["earnings_growth"]
    if rev_growth is None and earn_growth is None:
        return 12, "Growth data unavailable — treating as neutral"

    points = 0
    notes = []

    if rev_growth is not None:
        if rev_growth > 0.20:
            points += 13
            notes.append(f"strong revenue growth ({rev_growth * 100:.1f}%)")
        elif rev_growth > 0.05:
            points += 9
            notes.append(f"moderate revenue growth ({rev_growth * 100:.1f}%)")
        elif rev_growth > 0:
            points += 5
            notes.append(f"slow revenue growth ({rev_growth * 100:.1f}%)")
        else:
            points += 1
            notes.append(f"revenue is shrinking ({rev_growth * 100:.1f}%)")
    else:
        points += 6

    if earn_growth is not None:
        if earn_growth > 0.20:
            points += 12
            notes.append(f"strong earnings growth ({earn_growth * 100:.1f}%)")
        elif earn_growth > 0.05:
            points += 8
            notes.append(f"moderate earnings growth ({earn_growth * 100:.1f}%)")
        elif earn_growth > 0:
            points += 4
            notes.append(f"slow earnings growth ({earn_growth * 100:.1f}%)")
        else:
            points += 1
            notes.append(f"earnings are shrinking ({earn_growth * 100:.1f}%)")
    else:
        points += 6

    return points, ", ".join(notes).capitalize() if notes else "Growth data unavailable"


def score_profitability(f: dict) -> tuple[int, str]:
    margin = f["profit_margins"]
    roe = f["return_on_equity"]
    if margin is None and roe is None:
        return 12, "Profitability data unavailable — treating as neutral"

    points = 0
    notes = []

    if margin is not None:
        if margin > 0.20:
            points += 13
            notes.append(f"high profit margin ({margin * 100:.1f}%)")
        elif margin > 0.10:
            points += 9
            notes.append(f"healthy profit margin ({margin * 100:.1f}%)")
        elif margin > 0:
            points += 5
            notes.append(f"thin profit margin ({margin * 100:.1f}%)")
        else:
            points += 1
            notes.append("currently unprofitable")
    else:
        points += 6

    if roe is not None:
        if roe > 0.20:
            points += 12
            notes.append(f"strong return on equity ({roe * 100:.1f}%)")
        elif roe > 0.10:
            points += 8
            notes.append(f"decent return on equity ({roe * 100:.1f}%)")
        elif roe > 0:
            points += 4
            notes.append(f"low return on equity ({roe * 100:.1f}%)")
        else:
            points += 1
            notes.append("negative return on equity")
    else:
        points += 6

    return points, ", ".join(notes).capitalize() if notes else "Profitability data unavailable"


def score_financial_health(f: dict) -> tuple[int, str]:
    debt_to_equity = f["debt_to_equity"]
    fcf = f["free_cashflow"]
    if debt_to_equity is None and fcf is None:
        return 12, "Balance sheet data unavailable — treating as neutral"

    points = 0
    notes = []

    if debt_to_equity is not None:
        if debt_to_equity < 50:
            points += 13
            notes.append(f"low debt relative to equity ({debt_to_equity:.0f}%)")
        elif debt_to_equity < 100:
            points += 9
            notes.append(f"moderate debt levels ({debt_to_equity:.0f}%)")
        elif debt_to_equity < 200:
            points += 5
            notes.append(f"elevated debt levels ({debt_to_equity:.0f}%)")
        else:
            points += 1
            notes.append(f"high debt levels ({debt_to_equity:.0f}%)")
    else:
        points += 6

    if fcf is not None:
        if fcf > 0:
            points += 12
            notes.append("positive free cash flow")
        else:
            points += 2
            notes.append("negative free cash flow")
    else:
        points += 6

    return points, ", ".join(notes).capitalize() if notes else "Balance sheet data unavailable"


def build_bull_case(f: dict) -> list[str]:
    points = []
    if f["revenue_growth"] is not None and f["revenue_growth"] > 0.15:
        points.append(f"Revenue is growing at {f['revenue_growth'] * 100:.1f}% year-over-year.")
    if f["earnings_growth"] is not None and f["earnings_growth"] > 0.15:
        points.append(f"Earnings are growing at {f['earnings_growth'] * 100:.1f}% year-over-year.")
    if f["profit_margins"] is not None and f["profit_margins"] > 0.15:
        points.append(f"Profit margins are healthy at {f['profit_margins'] * 100:.1f}%.")
    if f["return_on_equity"] is not None and f["return_on_equity"] > 0.15:
        points.append(f"Return on equity of {f['return_on_equity'] * 100:.1f}% suggests efficient use of capital.")
    if f["trailing_pe"] is not None and 0 < f["trailing_pe"] < 20:
        points.append(f"Trading at a relatively modest P/E of {f['trailing_pe']:.1f}.")
    if f["debt_to_equity"] is not None and f["debt_to_equity"] < 50:
        points.append("Balance sheet carries relatively little debt.")
    if f["dividend_yield"]:
        points.append(f"Pays a dividend yield of {f['dividend_yield']:.2f}%.")
    if not points:
        points.append("No standout strengths identified from current fundamentals.")
    return points


def build_bear_case(f: dict) -> list[str]:
    points = []
    if f["revenue_growth"] is not None and f["revenue_growth"] < 0:
        points.append(f"Revenue is shrinking ({f['revenue_growth'] * 100:.1f}%).")
    if f["earnings_growth"] is not None and f["earnings_growth"] < 0:
        points.append(f"Earnings are shrinking ({f['earnings_growth'] * 100:.1f}%).")
    if f["profit_margins"] is not None and f["profit_margins"] < 0:
        points.append("Currently unprofitable.")
    if f["trailing_pe"] is not None and f["trailing_pe"] > 40:
        points.append(f"Trading at a rich valuation — P/E of {f['trailing_pe']:.1f} prices in a lot of future growth.")
    if f["debt_to_equity"] is not None and f["debt_to_equity"] > 150:
        points.append(f"Carries significant debt relative to equity ({f['debt_to_equity']:.0f}%).")
    if f["free_cashflow"] is not None and f["free_cashflow"] < 0:
        points.append("Currently burning cash (negative free cash flow).")
    if not points:
        points.append("No major red flags identified from current fundamentals.")
    return points


def analyze_stock(ticker: str) -> dict | None:
    """Full Athena read on one ticker: confidence score, breakdown, bull case, bear case."""
    f = get_fundamentals(ticker)
    if f is None:
        return None

    val_points, val_note = score_valuation(f)
    growth_points, growth_note = score_growth(f)
    profit_points, profit_note = score_profitability(f)
    health_points, health_note = score_financial_health(f)
    total = val_points + growth_points + profit_points + health_points

    return {
        "fundamentals": f,
        "confidence_score": total,
        "score_breakdown": {
            "Valuation": f"{val_points}/25 — {val_note}",
            "Growth": f"{growth_points}/25 — {growth_note}",
            "Profitability": f"{profit_points}/25 — {profit_note}",
            "Financial Health": f"{health_points}/25 — {health_note}",
        },
        "bull_case": build_bull_case(f),
        "bear_case": build_bear_case(f),
    }


def print_analysis(ticker: str) -> None:
    result = analyze_stock(ticker)
    if not result:
        print(f"Couldn't find fundamental data for {ticker}.")
        return

    f = result["fundamentals"]
    print("=" * 70)
    print(f"{f['name']} ({ticker}) — Athena Fundamental Analysis")
    print("=" * 70)
    print(f"Confidence Score: {result['confidence_score']}/100")
    print(f"Sector: {f['sector']}   Industry: {f['industry']}")
    print("-" * 70)
    for label, note in result["score_breakdown"].items():
        print(f"{label}: {note}")
    print("-" * 70)
    print("Bull Case:")
    for point in result["bull_case"]:
        print(f"  + {point}")
    print("Bear Case:")
    for point in result["bear_case"]:
        print(f"  - {point}")
    print("=" * 70)
    print()


if __name__ == "__main__":
    import sys
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print_analysis(ticker_arg)
