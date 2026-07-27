import asyncio

from sources.base_source import SourceItem
from sources.discord_source import DiscordSource
from ticker_extractor import extract_tickers
from report_generator import build_report, format_report_text
from database import init_db, save_source_item, save_analysis

# Add more sources here as they're implemented — nothing else in this file changes.
ACTIVE_SOURCES = [DiscordSource()]


async def handle_item(item: SourceItem) -> None:
    tickers = extract_tickers(item.content)
    if not tickers:
        return

    item_id = save_source_item(item)
    for ticker in tickers:
        try:
            report = build_report(ticker, item)
            save_analysis(item_id, report)
            print(format_report_text(report))
        except Exception as e:
            print(f"Failed to analyze {ticker} from {item.source} item: {e}")


async def run() -> None:
    init_db()
    print(f"Watching {len(ACTIVE_SOURCES)} source(s): {[s.name for s in ACTIVE_SOURCES]}")
    await asyncio.gather(*(source.run(handle_item) for source in ACTIVE_SOURCES))


if __name__ == "__main__":
    asyncio.run(run())
