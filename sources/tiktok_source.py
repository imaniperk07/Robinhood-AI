from typing import Awaitable, Callable

from sources.base_source import BaseSource, SourceItem


class TikTokSource(BaseSource):
    """Placeholder — watches selected stock creators for new uploads, summarizes via
    NotebookLM, and normalizes into SourceItems. Not yet implemented."""

    name = "tiktok"

    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        raise NotImplementedError("TikTok source not yet implemented — planned for a future milestone.")
