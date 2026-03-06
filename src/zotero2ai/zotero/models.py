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

    @property
    def title(self) -> str:
        """Generate a friendly title for the note."""
        from zotero2ai.zotero.utils import generate_friendly_name

        return generate_friendly_name(self.content)

    def __repr__(self) -> str:
        return f"ZoteroNote(title='{self.title}', key='{self.key}')"
@dataclass(frozen=True)
class MemoryEntry:
    """Represents a self-contained, disambiguated memory entry (Atomic Entry)."""

    lossless_restatement: str
    keywords: list[str] = field(default_factory=list)
    timestamp: str | None = None
    location: str | None = None
    persons: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    topic: str | None = None

    def to_html(self) -> str:
        """Convert entry to HTML for Zotero storage."""
        html = f"<p><b>Restatement:</b> {self.lossless_restatement}</p>"
        if self.timestamp:
            html += f"<p><b>Time:</b> {self.timestamp}</p>"
        if self.location:
            html += f"<p><b>Location:</b> {self.location}</p>"
        if self.topic:
            html += f"<p><b>Topic:</b> {self.topic}</p>"
        if self.persons:
            html += f"<p><b>Persons:</b> {', '.join(self.persons)}</p>"
        if self.entities:
            html += f"<p><b>Entities:</b> {', '.join(self.entities)}</p>"
        return html
