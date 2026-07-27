import json
import os
from datetime import datetime
from collections import Counter

JOURNAL_FILE = "trading_journal.json"

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "is", "it", "i", "was", "were", "this", "that", "my", "at", "be",
    "as", "so", "with", "because", "would", "will", "had", "have", "has",
    "not", "too", "just", "think", "thought", "felt", "feel",
}


def load_journal() -> list[dict]:
    if not os.path.exists(JOURNAL_FILE):
        return []
    with open(JOURNAL_FILE, "r") as f:
        return json.load(f)


def save_journal(entries: list[dict]) -> None:
    with open(JOURNAL_FILE, "w") as f:
        json.dump(entries, f, indent=2)


def add_entry() -> None:
    print("\n--- New Journal Entry ---")
    ticker = input("Ticker (e.g. AAPL): ").strip().upper()
    action = input("Action (buy/sell): ").strip().lower()
    price = input("Price per share: $").strip()
    shares = input("Number of shares: ").strip()
    reason = input("Why did you make this trade? ").strip()
    followed_strategy = input("Did you follow your own strategy/plan? (yes/no): ").strip().lower()
    lesson = input("What did you learn (or expect to learn)? ").strip()

    entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ticker": ticker,
        "action": action,
        "price": price,
        "shares": shares,
        "reason": reason,
        "followed_strategy": followed_strategy,
        "lesson": lesson,
    }

    entries = load_journal()
    entries.append(entry)
    save_journal(entries)
    print(f"\nEntry saved for {ticker}.\n")


def print_entry(entry: dict) -> None:
    print("-" * 60)
    print(f"{entry['date']}  |  {entry['ticker']}  |  {entry['action'].upper()}")
    print(f"Price: ${entry['price']}   Shares: {entry['shares']}")
    print(f"Reason: {entry['reason']}")
    print(f"Followed strategy: {entry['followed_strategy']}")
    print(f"Lesson: {entry['lesson']}")


def extract_common_words(entries: list[dict], field: str, top_n: int = 5) -> list[tuple[str, int]]:
    all_words = []
    for entry in entries:
        text = entry.get(field, "").lower()
        words = [w.strip(".,!?") for w in text.split()]
        words = [w for w in words if w and w not in STOPWORDS and len(w) > 2]
        all_words.extend(words)
    return Counter(all_words).most_common(top_n)


def review_journal() -> None:
    entries = load_journal()
    if not entries:
        print("\nYour journal is empty — add an entry first.\n")
        return

    print(f"\n{'=' * 60}")
    print(f"TRADING JOURNAL — {len(entries)} entries")
    print(f"{'=' * 60}\n")

    for entry in reversed(entries):
        print_entry(entry)
    print("-" * 60)

    followed_count = sum(1 for e in entries if e["followed_strategy"].startswith("y"))
    not_followed_count = len(entries) - followed_count
    print(f"\nStrategy adherence: followed {followed_count}/{len(entries)} times "
          f"({followed_count / len(entries) * 100:.0f}%)")

    print("\nRecurring themes in your REASONS:")
    for word, count in extract_common_words(entries, "reason"):
        print(f"  '{word}' — appeared {count}x")

    print("\nRecurring themes in your LESSONS:")
    for word, count in extract_common_words(entries, "lesson"):
        print(f"  '{word}' — appeared {count}x")

    print(f"\n{'=' * 60}\n")


def main_menu() -> None:
    while True:
        print("\n1) Add a new journal entry")
        print("2) Review my journal")
        print("3) Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            add_entry()
        elif choice == "2":
            review_journal()
        elif choice == "3":
            print("Goodbye.")
            break
        else:
            print("Please enter 1, 2, or 3.")


if __name__ == "__main__":
    main_menu()