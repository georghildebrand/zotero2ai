"""Read-only SQLite access to Zotero database."""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from zotero2ai.zotero.models import Collection, ZoteroItem

logger = logging.getLogger(__name__)


class ZoteroDB:
    """Handles read-only connections to the Zotero SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "ZoteroDB":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def connect(self) -> None:
        """Connect to the database in read-only mode."""
        if not self._conn:
            # Connect using URI for read-only mode
            db_uri = f"file:{self.db_path}?mode=ro"
            self._conn = sqlite3.connect(db_uri, uri=True)
            self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Get the active database connection, ensuring it is connected."""
        if not self._conn:
            self.connect()
        if not self._conn:
            raise RuntimeError("Failed to connect to Zotero database")
        return self._conn

    def get_collections(self) -> list[Collection]:
        """Fetch all collections and build their full paths."""
        cursor = self.connection.cursor()

        # Fetch all collections
        query = """
            SELECT c.collectionID, c.key, c.collectionName, c.parentCollectionID, c.libraryID
            FROM collections c
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        # First pass: map of ID -> Collection object (partial)
        col_map = {}
        id_to_key = {}
        for row in rows:
            col_id = row["collectionID"]
            key = row["key"]
            name = row["collectionName"]
            parent_id = row["parentCollectionID"]
            lib_id = row["libraryID"]

            id_to_key[col_id] = key
            col_map[col_id] = {"key": key, "name": name, "parent_id": parent_id, "library_id": lib_id}

        # Recursive helper to build path
        def get_path(col_id: int) -> str:
            col = col_map[col_id]
            parent_id = col["parent_id"]
            if parent_id is None or parent_id not in col_map:
                return str(col["name"])
            return f"{get_path(parent_id)} / {col['name']}"

        result = []
        for col_id, info in col_map.items():
            parent_key = id_to_key.get(info["parent_id"])
            full_path = get_path(col_id)

            result.append(Collection(key=info["key"], name=info["name"], parent_key=parent_key, library_id=info["library_id"], full_path=full_path))

        return sorted(result, key=lambda x: x.full_path)

    def get_item_count(self) -> int:
        """Get total number of items."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM items WHERE itemID NOT IN (SELECT itemID FROM deletedItems)")
        return int(cursor.fetchone()[0])

    def _get_item_metadata_dict(self, item_id: int) -> dict[str, str]:
        """Fetch all field/value pairs for a specific item ID."""
        cursor = self.connection.cursor()
        query = """
            SELECT f.fieldName, idv.value
            FROM itemData id
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE id.itemID = ?
        """
        cursor.execute(query, (item_id,))
        return {row["fieldName"]: row["value"] for row in cursor.fetchall()}

    def _get_item_creators(self, item_id: int) -> list[str]:
        """Fetch creators for an item."""
        cursor = self.connection.cursor()
        query = """
            SELECT c.lastName, c.firstName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
        """
        cursor.execute(query, (item_id,))
        creators = []
        for row in cursor.fetchall():
            name = f"{row['lastName']}, {row['firstName']}" if row["firstName"] else row["lastName"]
            creators.append(name)
        return creators

    def _get_item_tags(self, item_id: int) -> list[str]:
        """Fetch tags for an item."""
        cursor = self.connection.cursor()
        query = """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON it.tagID = t.tagID
            WHERE it.itemID = ?
        """
        cursor.execute(query, (item_id,))
        return [row["name"] for row in cursor.fetchall()]

    def _get_item_collections(self, item_id: int) -> list[str]:
        """Fetch collections (keys) for an item."""
        cursor = self.connection.cursor()
        query = """
            SELECT c.key
            FROM collectionItems ci
            JOIN collections c ON ci.collectionID = c.collectionID
            WHERE ci.itemID = ?
        """
        cursor.execute(query, (item_id,))
        return [row["key"] for row in cursor.fetchall()]

    def get_recent_items(self, limit: int = 5) -> list[ZoteroItem]:
        """Fetch N most recently added items."""
        cursor = self.connection.cursor()
        query = """
            SELECT i.itemID, i.key, it.typeName, i.libraryID, i.dateAdded, i.dateModified
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
            AND it.typeName NOT IN ('attachment', 'note')
            ORDER BY i.dateAdded DESC
            LIMIT ?
        """
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()

        items = []
        for row in rows:
            item_id = row["itemID"]
            meta = self._get_item_metadata_dict(item_id)

            # Parse dates
            from datetime import datetime

            def parse_date(date_str: str) -> datetime | None:
                if not date_str:
                    return None
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return None

            items.append(
                ZoteroItem(
                    key=row["key"],
                    item_type=row["typeName"],
                    library_id=row["libraryID"],
                    title=meta.get("title", ""),
                    abstract=meta.get("abstractNote", ""),
                    date=meta.get("date", ""),
                    creators=self._get_item_creators(item_id),
                    tags=self._get_item_tags(item_id),
                    collections=self._get_item_collections(item_id),
                    date_added=parse_date(row["dateAdded"]),
                    date_modified=parse_date(row["dateModified"]),
                )
            )

        return items

    def search_by_title(self, query_str: str, limit: int = 10) -> list[ZoteroItem]:
        """Search items by title using a simple SQL LIKE."""
        cursor = self.connection.cursor()

        # 1. Find fieldID for 'title'
        cursor.execute("SELECT fieldID FROM fields WHERE fieldName = 'title'")
        title_field_id_row = cursor.fetchone()
        if not title_field_id_row:
            return []
        title_field_id = title_field_id_row[0]

        # 2. Search items where 'title' matches query
        # We join items, itemData, and itemDataValues
        query = """
            SELECT i.itemID, i.key, it.typeName, i.libraryID, i.dateAdded, i.dateModified
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            JOIN itemData id ON i.itemID = id.itemID
            JOIN itemDataValues idv ON id.valueID = idv.valueID
            WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
            AND id.fieldID = ?
            AND idv.value LIKE ?
            AND it.typeName NOT IN ('attachment', 'note')
            LIMIT ?
        """
        cursor.execute(query, (title_field_id, f"%{query_str}%", limit))
        rows = cursor.fetchall()

        items = []
        for row in rows:
            item_id = row["itemID"]
            meta = self._get_item_metadata_dict(item_id)

            from datetime import datetime

            def parse_date(date_str: str) -> datetime | None:
                if not date_str:
                    return None
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except ValueError:
                    return None

            items.append(
                ZoteroItem(
                    key=row["key"],
                    item_type=row["typeName"],
                    library_id=row["libraryID"],
                    title=meta.get("title", ""),
                    abstract=meta.get("abstractNote", ""),
                    date=meta.get("date", ""),
                    creators=self._get_item_creators(item_id),
                    tags=self._get_item_tags(item_id),
                    collections=self._get_item_collections(item_id),
                    date_added=parse_date(row["dateAdded"]),
                    date_modified=parse_date(row["dateModified"]),
                )
            )

        return items
