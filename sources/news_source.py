from typing import Awaitable, Callable

from sources.base_source import BaseSource, SourceItem


class NewsSource(BaseSource):
    """Placeholder — would poll news_analysis.get_market_wide_news() and normalize
    articles into SourceItems. Not yet implemented for V1, though it would need the
    least new work of any planned source since the underlying NewsAPI fetching already
    exists in news_analysis.py."""

    name = "news"

    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        raise NotImplementedError("News source not yet implemented — planned for a future milestone.")
