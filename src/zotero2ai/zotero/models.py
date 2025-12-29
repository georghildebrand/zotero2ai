"""Data models for Zotero items and collections."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Collection:
    """Represents a Zotero collection."""

    key: str
    name: str
    parent_key: str | None = None
    library_id: int = 1
    full_path: str = ""

    def __repr__(self) -> str:
        return f"Collection(name='{self.name}', path='{self.full_path}', key='{self.key}')"


@dataclass(frozen=True)
class ZoteroItem:
    """Represents a Zotero item (paper, book, etc.)."""

    key: str
    item_type: str
    library_id: int = 1
    title: str = ""
    abstract: str = ""
    date: str = ""
    creators: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    date_added: datetime | None = None
    date_modified: datetime | None = None

    def __repr__(self) -> str:
        creator_str = ", ".join(self.creators[:2]) + ("..." if len(self.creators) > 2 else "")
        return f"ZoteroItem(title='{self.title}', creators='{creator_str}', key='{self.key}')"


@dataclass(frozen=True)
class ZoteroNote:
    """Represents a note attached to an item."""

    key: str
    parent_key: str
    content: str  # HTML or plain text
    date_added: datetime | None = None
    date_modified: datetime | None = None

    def __repr__(self) -> str:
        snippet = (self.content[:50] + "...") if len(self.content) > 50 else self.content
        return f"ZoteroNote(parent='{self.parent_key}', snippet='{snippet}')"
