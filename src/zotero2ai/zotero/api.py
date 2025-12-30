"""Zotero Web API client for writing data."""

import logging
from typing import Any, cast

from pyzotero import zotero  # type: ignore

logger = logging.getLogger(__name__)


class ZoteroWriter:
    """Handles writing to Zotero via the Web API."""

    def __init__(self, library_id: str, api_key: str, library_type: str = "user"):
        self.library_id = library_id
        self.api_key = api_key
        self.library_type = library_type
        self._zot: zotero.Zotero | None = None

    @property
    def zot(self) -> zotero.Zotero:
        """Get the pyzotero instance."""
        if not self._zot:
            self._zot = zotero.Zotero(self.library_id, self.library_type, self.api_key)
        return self._zot

    def create_note(self, content: str, collection_key: str | None = None, parent_item_key: str | None = None) -> dict[str, Any]:
        """Create a new note in Zotero.

        Args:
            content: The text content of the note (Markdown or HTML).
            collection_key: Optional key of the collection to add the note to.
            parent_item_key: Optional key of the item to attach the note to.

        Returns:
            dict: The created note object from the API.
        """
        note_template = self.zot.item_template("note")
        note_template["note"] = content

        if collection_key:
            note_template["collections"] = [collection_key]

        if parent_item_key:
            note_template["parentItem"] = parent_item_key

        resp = self.zot.create_items([note_template])

        # Check for success in the response
        if "success" in resp and resp["success"]:
            new_key = resp["success"]["0"]
            logger.info(f"Successfully created note with key: {new_key}")
            # Fetch the full object to return
            return cast(dict[str, Any], self.zot.item(new_key))
        else:
            error_msg = f"Failed to create note: {resp.get('failed', 'Unknown error')}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
