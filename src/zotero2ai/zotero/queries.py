"""Utilities for querying Zotero metadata."""

import sqlite3


def get_field_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """Map field names to their IDs in the Zotero database."""
    cursor = conn.cursor()
    cursor.execute("SELECT fieldName, fieldID FROM fields")
    return {row["fieldName"]: row["fieldID"] for row in cursor.fetchall()}


def get_item_type_ids(conn: sqlite3.Connection) -> dict[int, str]:
    """Map item type IDs to their names."""
    cursor = conn.cursor()
    cursor.execute("SELECT itemTypeID, typeName FROM itemTypes")
    return {row["itemTypeID"]: row["typeName"] for row in cursor.fetchall()}
