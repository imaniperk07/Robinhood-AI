import yfinance as yf

from watchlist import format_market_cap

# Curated universe: quality dividend-paying stocks + popular ETFs/index funds.
# Not a live screener — a hand-picked v1 starting set. Edit these lists anytime.
WEALTH_UNIVERSE: dict[str, list[str]] = {
    "Quality & Dividend Stocks": [
        "AAPL", "MSFT", "JNJ", "PG", "KO", "COST", "V", "HD", "ABBV", "MA",
        "JPM", "PEP", "WMT", "MCD", "UNH", "TXN", "LOW", "CAT", "CVX", "XOM",
    ],
    "ETFs & Index Funds": [
        "VOO", "VTI", "QQQ", "SCHD", "VYM", "VIG", "BND",
        "SPY", "DIA", "IWM", "VUG", "VNQ", "DGRO",
    ],
}


def get_fundamentals(ticker: str) -> dict | None:
    """Pull the raw data Wealth Builder reasons about. Shape depends on stock vs. fund."""
    stock = yf.Ticker(ticker)
    try:
        info = stock.info
    except Exception:
        return None

    if not info:
        return None
    price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice")
    if price is None:
        return None

    is_fund = info.get("quoteType") in ("ETF", "MUTUALFUND")

    base = {
        "ticker": ticker,
        "name": info.get("shortName", ticker),
        "asset_type": "Fund" if is_fund else "Stock",
        "price": price,
        "dividend_yield": info.get("dividendYield"),
    }

    if is_fund:
        base.update({
            "category": info.get("category", "Unknown"),
            "fund_family": info.get("fundFamily", "Unknown"),
            "total_assets": info.get("totalAssets"),
            "expense_ratio": info.get("netExpenseRatio"),
            "three_year_return": info.get("threeYearAverageReturn"),
            "five_year_return": info.get("fiveYearAverageReturn"),
            "beta_3y": info.get("beta3Year"),
        })
    else:
        base.update({
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "market_cap": info.get("marketCap"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "profit_margins": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cashflow": info.get("freeCashflow"),
        })

    return base


# ---------------------------------------------------------------------------
# Stock scoring (4 categories x 25 pts)
# ---------------------------------------------------------------------------

def score_stock_growth(f: dict) -> tuple[int, str]:
    rev = f.get("revenue_growth")
    earn = f.get("earnings_growth")
    if rev is None and earn is None:
        return 12, "Growth data unavailable — treating as neutral"

    points = 0
    notes = []
    if rev is not None:
        if rev > 0.15:
            points += 13
            notes.append(f"strong revenue growth ({rev * 100:.1f}%)")
        elif rev > 0.05:
            points += 9
            notes.append(f"steady revenue growth ({rev * 100:.1f}%)")
        elif rev > 0:
            points += 5
            notes.append(f"slow revenue growth ({rev * 100:.1f}%)")
        else:
            points += 1
            notes.append(f"revenue is shrinking ({rev * 100:.1f}%)")
    else:
        points += 6

    if earn is not None:
        if earn > 0.15:
            points += 12
            notes.append(f"strong earnings growth ({earn * 100:.1f}%)")
        elif earn > 0.05:
            points += 8
            notes.append(f"steady earnings growth ({earn * 100:.1f}%)")
        elif earn > 0:
            points += 4
            notes.append(f"slow earnings growth ({earn * 100:.1f}%)")
        else:
            points += 1
            notes.append(f"earnings are shrinking ({earn * 100:.1f}%)")
    else:
        points += 6

    return points, ", ".join(notes).capitalize() if notes else "Growth data unavailable"


def score_stock_profitability(f: dict) -> tuple[int, str]:
    margin = f.get("profit_margins")
    roe = f.get("return_on_equity")
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


def score_stock_cash_and_income(f: dict) -> tuple[int, str]:
    fcf = f.get("free_cashflow")
    yield_pct = f.get("dividend_yield")

    points = 0
    notes = []
    if fcf is not None:
        if fcf > 0:
            points += 13
            notes.append("positive free cash flow")
        else:
            points += 2
            notes.append("negative free cash flow")
    else:
        points += 6

    if yield_pct is not None and yield_pct >= 3:
        points += 12
        notes.append(f"strong dividend income ({yield_pct:.2f}%)")
    elif yield_pct is not None and yield_pct >= 1:
        points += 8
        notes.append(f"modest dividend income ({yield_pct:.2f}%)")
    elif yield_pct is not None and yield_pct > 0:
        points += 4
        notes.append(f"light dividend ({yield_pct:.2f}%)")
    else:
        points += 4
        notes.append("no dividend — relies purely on price growth")

    return points, ", ".join(notes).capitalize()


def score_stock_financial_strength(f: dict) -> tuple[int, str]:
    debt_to_equity = f.get("debt_to_equity")
    market_cap = f.get("market_cap")

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
            points += 2
            notes.append(f"high debt levels ({debt_to_equity:.0f}%)")
    else:
        points += 6

    if market_cap is not None:
        if market_cap >= 200_000_000_000:
            points += 12
            notes.append("mega-cap scale, often a sign of industry leadership")
        elif market_cap >= 10_000_000_000:
            points += 8
            notes.append("large-cap scale")
        elif market_cap >= 2_000_000_000:
            points += 4
            notes.append("mid-cap scale")
        else:
            points += 2
            notes.append("small-cap scale, typically more volatile")
    else:
        points += 6

    return points, ", ".join(notes).capitalize()


def build_moat_note(f: dict) -> str:
    margin = f.get("profit_margins")
    roe = f.get("return_on_equity")
    market_cap = f.get("market_cap")

    signals = []
    if margin is not None and margin > 0.20:
        signals.append("high profit margins")
    if roe is not None and roe > 0.20:
        signals.append("strong returns on capital")
    if market_cap is not None and market_cap > 200_000_000_000:
        signals.append("scale as one of the largest companies in its industry")

    if signals:
        return (
            "Inferred from the numbers, not a confirmed moat rating — but " + ", ".join(signals) +
            " are the kind of traits often associated with a durable competitive advantage."
        )
    return (
        "Nothing in the current numbers stands out as a clear competitive advantage — margins and "
        "returns on capital are closer to average for the market."
    )


def build_stock_opportunities(f: dict) -> list[str]:
    points = []
    if f.get("revenue_growth") is not None and f["revenue_growth"] > 0.10:
        points.append(f"Revenue has been growing at {f['revenue_growth'] * 100:.1f}% a year.")
    if f.get("dividend_yield"):
        points.append(f"Pays a dividend yield of {f['dividend_yield']:.2f}%, a source of income while you hold.")
    if f.get("free_cashflow") is not None and f["free_cashflow"] > 0:
        points.append("Generates positive free cash flow, funding growth and dividends without relying on debt.")
    if f.get("debt_to_equity") is not None and f["debt_to_equity"] < 50:
        points.append("Carries relatively little debt, giving it flexibility in a downturn.")
    if not points:
        points.append("No standout long-term strengths identified from current fundamentals.")
    return points


def build_stock_risks(f: dict) -> list[str]:
    points = []
    if f.get("revenue_growth") is not None and f["revenue_growth"] < 0.03:
        points.append("Revenue growth has slowed to a crawl — worth watching for a long-term compounding thesis.")
    if f.get("debt_to_equity") is not None and f["debt_to_equity"] > 150:
        points.append(f"Debt levels are elevated ({f['debt_to_equity']:.0f}% of equity).")
    if f.get("free_cashflow") is not None and f["free_cashflow"] < 0:
        points.append("Currently burning cash — worth understanding why before committing new money.")
    if not f.get("dividend_yield"):
        points.append("Pays no dividend — returns depend entirely on price appreciation.")
    if not points:
        points.append("No major long-term red flags identified from current fundamentals.")
    return points


# ---------------------------------------------------------------------------
# Fund scoring (4 categories x 25 pts)
# ---------------------------------------------------------------------------

def score_fund_track_record(f: dict) -> tuple[int, str]:
    three_yr = f.get("three_year_return")
    five_yr = f.get("five_year_return")
    if three_yr is None and five_yr is None:
        return 12, "Return history unavailable — treating as neutral"

    returns = [r for r in (three_yr, five_yr) if r is not None]
    avg_return = sum(returns) / len(returns)

    if avg_return > 0.15:
        points, label = 25, "strong"
    elif avg_return > 0.08:
        points, label = 18, "solid"
    elif avg_return > 0:
        points, label = 10, "modest"
    else:
        points, label = 3, "negative"

    three_str = f"{three_yr * 100:.1f}%" if three_yr is not None else "N/A"
    five_str = f"{five_yr * 100:.1f}%" if five_yr is not None else "N/A"
    return points, f"{label.capitalize()} track record — 3yr avg {three_str}, 5yr avg {five_str}"


def score_fund_cost_and_scale(f: dict) -> tuple[int, str]:
    expense_ratio = f.get("expense_ratio")
    total_assets = f.get("total_assets")

    points = 0
    notes = []
    if expense_ratio is not None:
        if expense_ratio <= 0.10:
            points += 13
            notes.append(f"very low expense ratio ({expense_ratio:.2f}%)")
        elif expense_ratio <= 0.30:
            points += 9
            notes.append(f"low expense ratio ({expense_ratio:.2f}%)")
        elif expense_ratio <= 0.60:
            points += 5
            notes.append(f"moderate expense ratio ({expense_ratio:.2f}%)")
        else:
            points += 2
            notes.append(f"high expense ratio ({expense_ratio:.2f}%)")
    else:
        points += 6

    if total_assets is not None:
        if total_assets >= 10_000_000_000:
            points += 12
            notes.append("large, well-established fund")
        elif total_assets >= 1_000_000_000:
            points += 8
            notes.append("established fund")
        elif total_assets >= 100_000_000:
            points += 4
            notes.append("smaller fund")
        else:
            points += 2
            notes.append("very small fund — worth checking liquidity")
    else:
        points += 6

    return points, ", ".join(notes).capitalize()


def score_fund_income(f: dict) -> tuple[int, str]:
    yield_pct = f.get("dividend_yield")
    if yield_pct is None:
        return 12, "Dividend data unavailable — treating as neutral"

    if yield_pct >= 3:
        return 25, f"Strong income fund ({yield_pct:.2f}% yield)"
    elif yield_pct >= 1.5:
        return 18, f"Moderate income ({yield_pct:.2f}% yield)"
    elif yield_pct >= 0.5:
        return 10, f"Light income ({yield_pct:.2f}% yield)"
    else:
        return 5, f"Primarily growth-oriented — little income ({yield_pct:.2f}% yield)"


def score_fund_stability(f: dict) -> tuple[int, str]:
    beta = f.get("beta_3y")
    if beta is None:
        return 12, "Volatility data unavailable — treating as neutral"

    if beta < 0.7:
        return 25, f"Low volatility relative to the market (beta {beta:.2f})"
    elif beta < 1.0:
        return 18, f"Slightly less volatile than the market (beta {beta:.2f})"
    elif beta < 1.3:
        return 10, f"Roughly in line with or a bit above market volatility (beta {beta:.2f})"
    else:
        return 5, f"More volatile than the broad market (beta {beta:.2f})"


def build_fund_thesis_note(f: dict) -> str:
    category = f.get("category") or "an unspecified"
    fund_family = f.get("fund_family") or "an unspecified provider"
    total_assets = f.get("total_assets")
    assets_str = format_market_cap(total_assets) if total_assets else "an undisclosed amount"
    return (
        f"A competitive-advantage framing doesn't really apply to a fund — what matters instead is what "
        f"it holds and how it's run. This is a {category} fund from {fund_family}, managing {assets_str} "
        f"in assets, giving broad diversification in a single position rather than betting on one "
        f"company's moat."
    )


def build_fund_opportunities(f: dict) -> list[str]:
    points = []
    if f.get("three_year_return") is not None and f["three_year_return"] > 0.10:
        points.append(f"3-year average annual return of {f['three_year_return'] * 100:.1f}%.")
    if f.get("expense_ratio") is not None and f["expense_ratio"] <= 0.10:
        points.append(f"Very low expense ratio ({f['expense_ratio']:.2f}%) — costs eat less into long-term returns.")
    if f.get("dividend_yield"):
        points.append(f"Pays a dividend yield of {f['dividend_yield']:.2f}%.")
    if f.get("beta_3y") is not None and f["beta_3y"] < 0.8:
        points.append("Historically less volatile than the broad market.")
    if not points:
        points.append("No standout strengths identified from current fund data.")
    return points


def build_fund_risks(f: dict) -> list[str]:
    points = []
    if f.get("expense_ratio") is not None and f["expense_ratio"] > 0.50:
        points.append(f"Expense ratio of {f['expense_ratio']:.2f}% is on the higher side — costs compound over decades.")
    if f.get("beta_3y") is not None and f["beta_3y"] > 1.2:
        points.append("Historically more volatile than the broad market.")
    if f.get("three_year_return") is not None and f["three_year_return"] < 0:
        points.append("3-year average annual return has been negative.")
    if not points:
        points.append("No major concerns identified from current fund data.")
    return points


# ---------------------------------------------------------------------------
# Unified entry points
# ---------------------------------------------------------------------------

def analyze_pick(ticker: str) -> dict | None:
    """Full Wealth Builder read on one ticker — a stock or a fund, scored on its own terms."""
    f = get_fundamentals(ticker)
    if f is None:
        return None

    if f["asset_type"] == "Fund":
        s1 = score_fund_track_record(f)
        s2 = score_fund_cost_and_scale(f)
        s3 = score_fund_income(f)
        s4 = score_fund_stability(f)
        breakdown = {
            "Track Record": f"{s1[0]}/25 — {s1[1]}",
            "Cost & Scale": f"{s2[0]}/25 — {s2[1]}",
            "Income": f"{s3[0]}/25 — {s3[1]}",
            "Stability": f"{s4[0]}/25 — {s4[1]}",
        }
        opportunities = build_fund_opportunities(f)
        risks = build_fund_risks(f)
        thesis_note = build_fund_thesis_note(f)
    else:
        s1 = score_stock_growth(f)
        s2 = score_stock_profitability(f)
        s3 = score_stock_cash_and_income(f)
        s4 = score_stock_financial_strength(f)
        breakdown = {
            "Growth": f"{s1[0]}/25 — {s1[1]}",
            "Profitability": f"{s2[0]}/25 — {s2[1]}",
            "Cash & Income": f"{s3[0]}/25 — {s3[1]}",
            "Financial Strength": f"{s4[0]}/25 — {s4[1]}",
        }
        opportunities = build_stock_opportunities(f)
        risks = build_stock_risks(f)
        thesis_note = build_moat_note(f)

    return {
        "fundamentals": f,
        "quality_score": s1[0] + s2[0] + s3[0] + s4[0],
        "score_breakdown": breakdown,
        "opportunities": opportunities,
        "risks": risks,
        "thesis_note": thesis_note,
    }


def scan_universe(category: str) -> list[dict]:
    """Run analyze_pick across every ticker in one WEALTH_UNIVERSE category, best score first."""
    results = []
    for ticker in WEALTH_UNIVERSE.get(category, []):
        result = analyze_pick(ticker)
        if result:
            results.append(result)
    results.sort(key=lambda r: r["quality_score"], reverse=True)
    return results


def print_analysis(ticker: str) -> None:
    result = analyze_pick(ticker)
    if not result:
        print(f"Couldn't find data for {ticker}.")
        return

    f = result["fundamentals"]
    print("=" * 70)
    print(f"{f['name']} ({ticker}) — Wealth Builder — {f['asset_type']}")
    print("=" * 70)
    print(f"Quality Score: {result['quality_score']}/100")
    print("-" * 70)
    for label, note in result["score_breakdown"].items():
        print(f"{label}: {note}")
    print("-" * 70)
    print(result["thesis_note"])
    print("-" * 70)
    print("Opportunities:")
    for point in result["opportunities"]:
        print(f"  + {point}")
    print("Risks:")
    for point in result["risks"]:
        print(f"  - {point}")
    print("=" * 70)
    print()


def print_scan(category: str) -> None:
    results = scan_universe(category)
    if not results:
        print(f"No data available for category '{category}'.")
        return

    print("=" * 70)
    print(f"WEALTH BUILDER — {category}")
    print("=" * 70)
    for r in results:
        f = r["fundamentals"]
        print(f"\n{f['ticker']} ({f['asset_type']}) — Score: {r['quality_score']}/100")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import sys
    arg = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    if arg in WEALTH_UNIVERSE:
        print_scan(arg)
    else:
        print_analysis(arg)
