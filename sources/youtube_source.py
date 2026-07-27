from typing import Awaitable, Callable

from sources.base_source import BaseSource, SourceItem


class YouTubeSource(BaseSource):
    """Placeholder — watches selected stock creators for new video uploads and
    normalizes summaries into SourceItems. Not yet implemented."""

    name = "youtube"

    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        raise NotImplementedError("YouTube source not yet implemented — planned for a future milestone.")
