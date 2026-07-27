import re

import yfinance as yf

DOLLAR_PATTERN = re.compile(r"\$([A-Za-z]{1,5})\b")
# Bare (non-$-prefixed) symbols are only matched in strict uppercase. Tried relaxing this
# to catch casual lowercase mentions (e.g. "nbis looking good") but it backfired badly in
# testing — ordinary words like "are" (Alexandria Real Estate), "out" (Outfront Media),
# "you" (Clear Secure), and "team" (Atlassian) are themselves real, currently-traded
# tickers, so case-insensitive matching floods on completely ordinary sentences. A
# hand-maintained stopword list can't keep up with how many common English words
# coincidentally collide with real 3-5 letter symbols. "$TICKER" is the reliable way to
# guarantee detection regardless of case.
BARE_PATTERN = re.compile(r"\b[A-Z]{1,5}\b")

# Common English words / chat shorthand that collide with real ticker symbols. A
# deliberate tradeoff: a few genuine tickers (e.g. "ALL" = Allstate, "GO" = Grindrod
# Shipping, "A" = Agilent) get missed when typed bare. Prefixing with "$" (e.g. "$ALL")
# always bypasses this filter.
STOPWORDS = {
    "I", "A", "ALL", "FOR", "ON", "GO", "IT", "IS", "BE", "DO", "SO", "TO", "OF", "IN",
    "AT", "AN", "OR", "IF", "MY", "ME", "WE", "US", "UP", "NO", "OK", "CEO", "CFO",
    "IPO", "ATH", "USA", "EOD", "DD", "YOLO", "FOMO", "LOL", "IMO", "IMHO", "ASAP",
    "FYI", "ETF", "GDP", "SEC", "FED", "NYSE", "TLDR", "RN", "GG",
}

_validity_cache: dict[str, bool] = {}


def is_valid_ticker(symbol: str) -> bool:
    """Live yfinance check, cached in-memory for the life of the process."""
    if symbol in _validity_cache:
        return _validity_cache[symbol]

    valid = False
    try:
        info = yf.Ticker(symbol).fast_info
        valid = info is not None and info.get("lastPrice") is not None
    except Exception:
        valid = False

    _validity_cache[symbol] = valid
    return valid


def extract_tickers(text: str) -> list[str]:
    """Returns validated, de-duplicated tickers in order of first appearance."""
    found: list[str] = []

    for m in DOLLAR_PATTERN.finditer(text):
        sym = m.group(1).upper()
        if sym not in found and is_valid_ticker(sym):
            found.append(sym)

    for m in BARE_PATTERN.finditer(text):
        sym = m.group(0)
        if sym in STOPWORDS or sym in found:
            continue
        if is_valid_ticker(sym):
            found.append(sym)

    return found


if __name__ == "__main__":
    test_messages = [
        "$AAPL earnings next week, feeling bullish",
        "TSLA and RKLB both look strong, ALL of these charts are up",
        "just chilling, GO team, nothing to see here",
        "NVDA breaking out, PLTR too",
        "someone put something about nbis and ibkr",
        "gm everyone, hope you slept ok",
    ]
    for msg in test_messages:
        print(msg, "->", extract_tickers(msg))
