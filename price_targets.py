import json
import os
import yfinance as yf

TARGETS_FILE = "price_targets.json"
APPROACHING_THRESHOLD_PCT = 2.0  # Flag as "approaching" within this % of the target

ORDER_TYPE_LABELS = {
    "buy_stop": "Buy Stop",
    "buy_limit": "Buy Limit",
    "sell_stop": "Sell Stop (Stop Loss)",
    "sell_limit": "Sell Limit (Profit Target)",
}


def load_targets() -> list[dict]:
    if not os.path.exists(TARGETS_FILE):
        return []
    with open(TARGETS_FILE, "r") as f:
        return json.load(f)


def save_targets(targets: list[dict]) -> None:
    with open(TARGETS_FILE, "w") as f:
        json.dump(targets, f, indent=2)


def add_target() -> None:
    print("\n--- New Price Target ---")
    ticker = input("Ticker (e.g. AAPL): ").strip().upper()

    print("Order type: 1) Buy Stop  2) Buy Limit  3) Sell Stop  4) Sell Limit")
    choice = input("Choose 1-4: ").strip()
    order_map = {"1": "buy_stop", "2": "buy_limit", "3": "sell_stop", "4": "sell_limit"}
    order_type = order_map.get(choice)
    if not order_type:
        print("Invalid choice — target not saved.")
        return

    try:
        target_price = float(input("Target price: $").strip())
    except ValueError:
        print("Invalid price — target not saved.")
        return

    note = input("Note (optional, why this target?): ").strip()

    target = {
        "ticker": ticker,
        "order_type": order_type,
        "target_price": target_price,
        "note": note,
    }

    targets = load_targets()
    targets.append(target)
    save_targets(targets)
    print(f"\nSaved: {ORDER_TYPE_LABELS[order_type]} on {ticker} at ${target_price:.2f}\n")


def get_current_price(ticker: str) -> float | None:
    stock = yf.Ticker(ticker)
    history = stock.history(period="1d")
    if history.empty:
        return None
    return history["Close"].iloc[-1]


def evaluate_target(target: dict, current_price: float) -> tuple[str, str]:
    """Returns (status, message) for a given target vs the current price."""
    target_price = target["target_price"]
    order_type = target["order_type"]
    pct_away = ((current_price - target_price) / target_price) * 100

    if order_type == "buy_stop":
        if current_price >= target_price:
            return "HIT", f"Price (${current_price:.2f}) has reached your buy stop — consider placing your buy order now."
        elif -APPROACHING_THRESHOLD_PCT <= pct_away < 0:
            return "APPROACHING", f"Price (${current_price:.2f}) is {abs(pct_away):.1f}% below your buy stop target."
    elif order_type == "buy_limit":
        if current_price <= target_price:
            return "HIT", f"Price (${current_price:.2f}) has dropped to your buy limit — consider placing your buy order now."
        elif 0 < pct_away <= APPROACHING_THRESHOLD_PCT:
            return "APPROACHING", f"Price (${current_price:.2f}) is {pct_away:.1f}% above your buy limit target."
    elif order_type == "sell_stop":
        if current_price <= target_price:
            return "HIT", f"Price (${current_price:.2f}) has dropped to your sell stop — consider placing your sell order now."
        elif 0 < pct_away <= APPROACHING_THRESHOLD_PCT:
            return "APPROACHING", f"Price (${current_price:.2f}) is {pct_away:.1f}% above your sell stop target."
    elif order_type == "sell_limit":
        if current_price >= target_price:
            return "HIT", f"Price (${current_price:.2f}) has reached your sell limit — consider placing your sell order now."
        elif -APPROACHING_THRESHOLD_PCT <= pct_away < 0:
            return "APPROACHING", f"Price (${current_price:.2f}) is {abs(pct_away):.1f}% below your sell limit target."

    return "WAITING", f"Price (${current_price:.2f}) is not yet close to your target of ${target_price:.2f}."


def check_targets() -> None:
    targets = load_targets()
    if not targets:
        print("\nNo price targets set yet. Add one first.\n")
        return

    print(f"\n{'=' * 70}")
    print("PRICE TARGET CHECK")
    print(f"{'=' * 70}\n")

    for target in targets:
        current_price = get_current_price(target["ticker"])
        if current_price is None:
            print(f"{target['ticker']}: Couldn't fetch current price.\n")
            continue

        status, message = evaluate_target(target, current_price)
        label = ORDER_TYPE_LABELS[target["order_type"]]

        if status == "HIT":
            icon = "🎯"
        elif status == "APPROACHING":
            icon = "👀"
        else:
            icon = "—"

        print(f"{icon} {target['ticker']} — {label} @ ${target['target_price']:.2f}")
        print(f"   {message}")
        if target["note"]:
            print(f"   Note: {target['note']}")
        print()

    print(f"{'=' * 70}\n")


def remove_target() -> None:
    targets = load_targets()
    if not targets:
        print("\nNo targets to remove.\n")
        return

    for i, t in enumerate(targets, start=1):
        print(f"{i}) {t['ticker']} — {ORDER_TYPE_LABELS[t['order_type']]} @ ${t['target_price']:.2f}")

    choice = input("Enter the number to remove (or press Enter to cancel): ").strip()
    if not choice:
        return
    try:
        index = int(choice) - 1
        removed = targets.pop(index)
        save_targets(targets)
        print(f"Removed: {removed['ticker']} target.\n")
    except (ValueError, IndexError):
        print("Invalid selection.\n")


def main_menu() -> None:
    while True:
        print("\n1) Add a new price target")
        print("2) Check my targets now")
        print("3) Remove a target")
        print("4) Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            add_target()
        elif choice == "2":
            check_targets()
        elif choice == "3":
            remove_target()
        elif choice == "4":
            print("Goodbye.")
            break
        else:
            print("Please enter 1, 2, 3, or 4.")


if __name__ == "__main__":
    main_menu()