from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable


@dataclass
class SourceItem:
    """A normalized piece of content from any source. Athena's analysis pipeline only
    ever works with these — it never knows or cares which platform an item came from
    beyond what's recorded in `source`."""
    source: str
    author: str
    content: str
    url: str | None
    timestamp: str  # ISO 8601
    metadata: dict = field(default_factory=dict)


class BaseSource(ABC):
    """Common interface every content source implements."""

    name: str = "base"

    @abstractmethod
    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        """Start listening or polling. Call `on_item(item)` for every new piece of content."""
        raise NotImplementedError


def build_manual_item(source: str, author: str, content: str, url: str | None = None) -> SourceItem:
    """Construct a SourceItem from manually-entered content — e.g. a TikTok caption or
    transcript pasted in by the user — for sources that don't have live monitoring
    (a `run()` implementation) yet."""
    return SourceItem(
        source=source,
        author=author or "Unknown",
        content=content,
        url=url,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"entry_method": "manual"},
    )
