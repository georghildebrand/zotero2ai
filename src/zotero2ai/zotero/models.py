"""Data models for Zotero items and collections."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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


@dataclass
class MemoryItem:
    """Represents a Zotero Agent Memory Item (Phase 1)."""

    mem_id: str  # mem.<project>.<timestamp>.<counter>
    mem_class: str  # unit | concept | project | system
    role: str  # question | observation | hypothesis | result | synthesis
    project: str  # lowercase slug
    title: str  # [MEM][<class>][<project>] <short label>
    content: str  # human-readable text below metadata
    state: str = "active"  # active | superseded | archived
    version: int = 1
    source: str = "agent"  # user | agent | paper | conversation | manual
    confidence: str = "medium"  # low | medium | high
    created_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    collections: list[str] = field(default_factory=list)
    source_item_key: str | None = None  # Original Zotero paper/attachment key
    source_uri: str | None = None  # Original URL or conversation link
    relations: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def generate_tags(self) -> list[str]:
        """Derive Zotero tags from metadata axes."""
        derived = [
            f"mem:class:{self.mem_class}",
            f"mem:role:{self.role}",
            f"mem:project:{self.project}",
            f"mem:state:{self.state}",
            f"mem:source:{self.source}",
        ]
        # Include domains if they are in the tags list already or could be added
        for tag in self.tags:
            if isinstance(tag, str) and tag.startswith("mem:domain:"):
                derived.append(tag)
        return list(set(derived))

    def to_metadata_block(self) -> str:
        """Create a YAML metadata block for the beginning of the child note."""
        import yaml  # type: ignore[import-untyped]

        metadata = {
            "mem_id": self.mem_id,
            "class": self.mem_class,
            "role": self.role,
            "project": self.project,
            "state": self.state,
            "version": self.version,
            "created_by": "agent" if self.source == "agent" else self.source,
            "source": self.source,
            "source_item_key": self.source_item_key,
            "source_uri": self.source_uri,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "collections": self.collections,
            "relations": self.relations,
        }
        # Use a safe YAML dumper that's readable
        from typing import cast

        yaml_str = cast(str, yaml.dump(metadata, default_flow_style=False, sort_keys=False))
        return yaml_str

    def to_note_html(self) -> str:
        """Render metadata block + content as a Zotero-safe note body (HTML)."""
        metadata_block = self.to_metadata_block()
        # Use <pre> for metadata block to preserve formatting/monospacing
        # And <br> for newlines in content
        human_content = self.content.replace("\n", "<br/>")

        return f"<pre>{metadata_block}</pre><hr/><p>{human_content}</p>"

    @staticmethod
    def generate_mem_id(project: str, counter: int = 1) -> str:
        """Generate a unique mem_id. mem.<project>.<timestamp>.<counter>"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        return f"mem.{project}.{timestamp}.{counter:03d}"

    @classmethod
    def from_zotero_data(cls, item_data: dict[str, Any], note_content: str | None = None) -> "MemoryItem | None":
        """Reconstruct a MemoryItem from a Zotero API item dict + optional note content.

        Returns None if the item is not a valid memory node (no metadata block found).
        """
        import re

        import yaml

        title = item_data.get("title", "")
        tags = item_data.get("tags", [])

        # Extract metadata from note content (look for <pre>...</pre> block)
        metadata: dict[str, Any] = {}
        content_text = ""
        if note_content:
            pre_match = re.search(r"<pre>(.*?)</pre>", note_content, re.DOTALL)
            if pre_match:
                try:
                    parsed = yaml.safe_load(pre_match.group(1))
                    if isinstance(parsed, dict):
                        metadata = parsed
                except Exception:
                    pass
            # Extract content after <hr/> or <hr>
            hr_match = re.split(r"<hr\s*/?>", note_content, maxsplit=1)
            if len(hr_match) > 1:
                # Strip HTML tags for plain text
                content_text = re.sub(r"<[^>]+>", "", hr_match[1]).strip()

        # If no metadata block, try to derive from tags
        mem_class = metadata.get("class", "")
        role = metadata.get("role", "")
        project = metadata.get("project", "")
        state = metadata.get("state", "active")

        if not mem_class:
            for t in tags:
                tag_name = t.get("tag", "") if isinstance(t, dict) else t
                if isinstance(tag_name, str) and tag_name.startswith("mem:class:"):
                    mem_class = tag_name.split(":")[-1]
                    break
        if not role:
            for t in tags:
                tag_name = t.get("tag", "") if isinstance(t, dict) else t
                if isinstance(tag_name, str) and tag_name.startswith("mem:role:"):
                    role = tag_name.split(":")[-1]
                    break
        # Ensure state matches actual Zotero tags (source of truth after synthesize/supersede)
        for t in tags:
            tag_name = t.get("tag", "") if isinstance(t, dict) else t
            if isinstance(tag_name, str) and tag_name.startswith("mem:state:"):
                state = tag_name.split(":")[-1]
                break
        if not project:
            for t in tags:
                tag_name = t.get("tag", "") if isinstance(t, dict) else t
                if isinstance(tag_name, str) and tag_name.startswith("mem:project:"):
                    project = tag_name.split(":")[-1]
                    break

        # Must have at least class to be a valid memory item
        if not mem_class:
            return None

        # Clean tags to list of strings
        clean_tags = []
        for t in tags:
            tag_name = t.get("tag", "") if isinstance(t, dict) else str(t)
            clean_tags.append(tag_name)

        return cls(
            mem_id=metadata.get("mem_id", f"mem.{project}.unknown"),
            mem_class=mem_class,
            role=role or "observation",
            project=project or "unknown",
            title=title,
            content=content_text or title,
            state=state,
            version=metadata.get("version", 1),
            source=metadata.get("source", "unknown"),
            source_item_key=metadata.get("source_item_key"),
            source_uri=metadata.get("source_uri"),
            confidence=metadata.get("confidence", "medium"),
            created_at=metadata.get("created_at", item_data.get("dateAdded", "")),
            updated_at=metadata.get("updated_at", item_data.get("dateModified", "")),
            tags=clean_tags,
        )
