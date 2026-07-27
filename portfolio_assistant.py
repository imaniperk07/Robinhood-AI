import subprocess
import re
import yfinance as yf


def strip_ansi(text: str) -> str:
    """Remove terminal color codes so we can parse the plain text table."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def parse_money(value: str) -> float:
    return float(value.replace("$", "").replace(",", ""))


def get_snaptrade_positions() -> list[dict]:
    """Runs the SnapTrade CLI in the background and parses your real positions."""
    try:
        result = subprocess.run(
            ["snaptrade", "positions", "--all"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        print("Couldn't find the 'snaptrade' command. Is the CLI installed? (npm install -g @snaptrade/snaptrade-cli)")
        return []

    if result.returncode != 0:
        print("Error running snaptrade CLI:", result.stderr)
        return []

    output = strip_ansi(result.stdout)
    lines = output.split("\n")

    positions = []
    for line in lines:
        line = line.strip()
        if not line.startswith("│"):
            continue

        cells = [cell.strip() for cell in line.split("│")]
        cells = [c for c in cells if c != ""]

        if len(cells) != 6:
            continue
        if cells[0] == "Symbol":
            continue  # skip header row

        symbol, quantity, market_price, cost_basis, market_value, pnl = cells

        positions.append({
            "ticker": symbol,
            "shares": float(quantity),
            "cli_price": parse_money(market_price),
            "cost_basis": parse_money(cost_basis),
            "cli_market_value": parse_money(market_value),
            "cli_pnl": parse_money(pnl),
        })

    return positions


def get_holding_data(ticker: str, shares: float, cost_basis: float) -> dict | None:
    stock = yf.Ticker(ticker)
    history = stock.history(period="5d")
    if history.empty or len(history) < 2:
        return None

    current_price = history["Close"].iloc[-1]
    previous_close = history["Close"].iloc[-2]
    daily_gain_loss = (current_price - previous_close) * shares

    current_value = current_price * shares
    cost_value = cost_basis * shares
    total_gain_loss = current_value - cost_value
    total_gain_loss_pct = (total_gain_loss / cost_value * 100) if cost_value else 0

    info = {}
    try:
        info = stock.info
    except Exception:
        pass

    return {
        "ticker": ticker,
        "shares": shares,
        "current_price": current_price,
        "current_value": current_value,
        "cost_value": cost_value,
        "daily_gain_loss": daily_gain_loss,
        "total_gain_loss": total_gain_loss,
        "total_gain_loss_pct": total_gain_loss_pct,
        "sector": info.get("sector", "Unknown"),
        "beta": info.get("beta"),
    }


def build_portfolio() -> list[dict]:
    """Pulls your REAL holdings from Robinhood via the SnapTrade CLI — no manual entry."""
    real_positions = get_snaptrade_positions()
    if not real_positions:
        print("Couldn't retrieve positions from SnapTrade CLI.")
        return []

    results = []
    for position in real_positions:
        data = get_holding_data(position["ticker"], position["shares"], position["cost_basis"])
        if data:
            results.append(data)
        else:
            print(f"Couldn't get market data for {position['ticker']} — skipping.")
    return results


def print_summary(portfolio: list[dict]) -> None:
    total_value = sum(h["current_value"] for h in portfolio)
    total_cost = sum(h["cost_value"] for h in portfolio)
    total_daily_gain_loss = sum(h["daily_gain_loss"] for h in portfolio)
    total_gain_loss = total_value - total_cost
    total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost else 0

    print("=" * 70)
    print("PORTFOLIO SUMMARY (live from Robinhood via SnapTrade)")
    print("=" * 70)
    print(f"Total Value: ${total_value:,.2f}")
    print(f"Total Cost Basis: ${total_cost:,.2f}")
    daily_arrow = "▲" if total_daily_gain_loss >= 0 else "▼"
    print(f"Today's Gain/Loss: {daily_arrow} ${total_daily_gain_loss:,.2f}")
    total_arrow = "▲" if total_gain_loss >= 0 else "▼"
    print(f"Total Gain/Loss: {total_arrow} ${total_gain_loss:,.2f} ({total_gain_loss_pct:+.2f}%)")
    print()


def print_holdings_table(portfolio: list[dict]) -> None:
    print("-" * 70)
    print(f"{'Ticker':<8}{'Shares':<12}{'Price':<10}{'Value':<12}{'Gain/Loss':<18}{'Sector':<15}")
    print("-" * 70)
    for h in portfolio:
        gain_str = f"{h['total_gain_loss']:+,.2f} ({h['total_gain_loss_pct']:+.1f}%)"
        print(f"{h['ticker']:<8}{h['shares']:<12.6f}${h['current_price']:<9.2f}${h['current_value']:<11,.2f}{gain_str:<18}{h['sector']:<15}")
    print()


def print_sector_allocation(portfolio: list[dict]) -> tuple[dict, float]:
    total_value = sum(h["current_value"] for h in portfolio)
    sector_totals: dict[str, float] = {}
    for h in portfolio:
        sector_totals[h["sector"]] = sector_totals.get(h["sector"], 0) + h["current_value"]

    print("-" * 70)
    print("SECTOR ALLOCATION")
    print("-" * 70)
    for sector, value in sorted(sector_totals.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total_value * 100) if total_value else 0
        print(f"{sector:<20} {pct:5.1f}%   (${value:,.2f})")
    print()

    return sector_totals, total_value


def print_best_worst(portfolio: list[dict]) -> None:
    sorted_by_pct = sorted(portfolio, key=lambda h: h["total_gain_loss_pct"], reverse=True)
    best = sorted_by_pct[0]
    worst = sorted_by_pct[-1]

    print("-" * 70)
    print("BEST / WORST PERFORMERS")
    print("-" * 70)
    print(f"Best:  {best['ticker']}  {best['total_gain_loss_pct']:+.2f}%")
    print(f"Worst: {worst['ticker']}  {worst['total_gain_loss_pct']:+.2f}%")
    print()


def calculate_risk_score(portfolio: list[dict], sector_totals: dict, total_value: float) -> tuple[int, list[str]]:
    notes = []

    largest_holding_value = max(h["current_value"] for h in portfolio)
    concentration_pct = (largest_holding_value / total_value * 100) if total_value else 0
    if concentration_pct >= 50:
        concentration_points = 40
    elif concentration_pct >= 35:
        concentration_points = 28
    elif concentration_pct >= 20:
        concentration_points = 15
    else:
        concentration_points = 5
    notes.append(f"Concentration: largest holding is {concentration_pct:.1f}% of portfolio ({concentration_points}/40 risk pts)")

    num_sectors = len(sector_totals)
    if num_sectors <= 1:
        sector_points = 30
    elif num_sectors <= 2:
        sector_points = 22
    elif num_sectors <= 4:
        sector_points = 12
    else:
        sector_points = 5
    notes.append(f"Diversification: holdings span {num_sectors} sector(s) ({sector_points}/30 risk pts)")

    betas = [h["beta"] for h in portfolio if h["beta"] is not None]
    avg_beta = sum(betas) / len(betas) if betas else 1.0
    if avg_beta >= 1.5:
        beta_points = 30
    elif avg_beta >= 1.2:
        beta_points = 20
    elif avg_beta >= 0.9:
        beta_points = 10
    else:
        beta_points = 5
    notes.append(f"Volatility: average beta is {avg_beta:.2f} ({beta_points}/30 risk pts)")

    return concentration_points + sector_points + beta_points, notes


def print_risk_score(portfolio: list[dict], sector_totals: dict, total_value: float) -> None:
    risk_score, notes = calculate_risk_score(portfolio, sector_totals, total_value)
    print("-" * 70)
    print(f"PORTFOLIO RISK SCORE: {risk_score} / 100  (higher = more risk)")
    print("-" * 70)
    for note in notes:
        print(f"- {note}")
    print()


def run_portfolio_assistant() -> None:
    portfolio = build_portfolio()
    if not portfolio:
        print("No holdings data available.")
        return

    print_summary(portfolio)
    print_holdings_table(portfolio)
    sector_totals, total_value = print_sector_allocation(portfolio)
    print_best_worst(portfolio)
    print_risk_score(portfolio, sector_totals, total_value)


if __name__ == "__main__":
    run_portfolio_assistant()