from typing import Awaitable, Callable

from sources.base_source import BaseSource, SourceItem


class RedditSource(BaseSource):
    """Placeholder — monitors selected subreddits for stock-related posts/comments and
    normalizes them into SourceItems. Not yet implemented."""

    name = "reddit"

    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        raise NotImplementedError("Reddit source not yet implemented — planned for a future milestone.")
