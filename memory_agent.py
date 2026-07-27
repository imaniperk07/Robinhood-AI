import json
import os
from datetime import datetime

from trading_journal import load_journal, extract_common_words

MEMORY_FILE = "user_memory.json"

DEFAULT_MEMORY = {
    "risk_tolerance": "Not set",
    "investing_style": "Not set",
    "favorite_sectors": [],
    "favorite_companies": [],
    "long_term_goals": "",
    "notes": [],
}


def load_memory() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return dict(DEFAULT_MEMORY)
    with open(MEMORY_FILE, "r") as f:
        data = json.load(f)
    # Fill in any keys missing from an older file so new fields don't break on load.
    merged = dict(DEFAULT_MEMORY)
    merged.update(data)
    return merged


def save_memory(memory: dict) -> None:
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def update_profile(
    risk_tolerance: str | None = None,
    investing_style: str | None = None,
    favorite_sectors: list[str] | None = None,
    favorite_companies: list[str] | None = None,
    long_term_goals: str | None = None,
) -> dict:
    memory = load_memory()
    if risk_tolerance is not None:
        memory["risk_tolerance"] = risk_tolerance
    if investing_style is not None:
        memory["investing_style"] = investing_style
    if favorite_sectors is not None:
        memory["favorite_sectors"] = favorite_sectors
    if favorite_companies is not None:
        memory["favorite_companies"] = favorite_companies
    if long_term_goals is not None:
        memory["long_term_goals"] = long_term_goals
    save_memory(memory)
    return memory


def add_note(note: str) -> dict:
    """Save a free-form fact worth remembering — e.g. something the user told Jarvis in chat."""
    memory = load_memory()
    memory["notes"].append({"date": datetime.now().strftime("%Y-%m-%d"), "note": note})
    save_memory(memory)
    return memory


def clear_notes() -> dict:
    memory = load_memory()
    memory["notes"] = []
    save_memory(memory)
    return memory


def get_journal_insights() -> dict | None:
    """Derive strategy adherence and recurring themes from the trading journal, if any entries exist."""
    entries = load_journal()
    if not entries:
        return None

    followed_count = sum(1 for e in entries if e["followed_strategy"].startswith("y"))
    adherence_pct = followed_count / len(entries) * 100

    return {
        "entry_count": len(entries),
        "strategy_adherence_pct": round(adherence_pct, 1),
        "common_reasons": extract_common_words(entries, "reason"),
        "common_lessons": extract_common_words(entries, "lesson"),
    }


def get_memory_summary() -> str:
    """Human-readable summary — meant to be dropped into an AI prompt (e.g. Jarvis's system prompt)."""
    memory = load_memory()
    lines = []

    if memory["risk_tolerance"] != "Not set":
        lines.append(f"Risk tolerance: {memory['risk_tolerance']}")
    if memory["investing_style"] != "Not set":
        lines.append(f"Investing style: {memory['investing_style']}")
    if memory["favorite_sectors"]:
        lines.append(f"Favorite sectors: {', '.join(memory['favorite_sectors'])}")
    if memory["favorite_companies"]:
        lines.append(f"Favorite companies: {', '.join(memory['favorite_companies'])}")
    if memory["long_term_goals"]:
        lines.append(f"Long-term goals: {memory['long_term_goals']}")
    if memory["notes"]:
        recent_notes = [n["note"] for n in memory["notes"][-5:]]
        lines.append("Recent notes: " + "; ".join(recent_notes))

    insights = get_journal_insights()
    if insights:
        lines.append(
            f"Trading journal: {insights['entry_count']} entries, "
            f"{insights['strategy_adherence_pct']}% strategy adherence"
        )

    if not lines:
        return "No stored preferences yet — this is a new user, nothing to personalize on yet."
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_memory_summary())
