"""MCP server implementation for zotero2ai."""

import logging

from mcp.server.fastmcp import FastMCP

from zotero2ai.config import (
    resolve_zotero_api_key,
    resolve_zotero_data_dir,
    resolve_zotero_user_id,
)
from zotero2ai.zotero.api import ZoteroWriter
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.db import ZoteroDB

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    mcp = FastMCP("zotero2ai")

    # Initialize DB connection on demand
    def get_db() -> ZoteroDB:
        zotero_dir = resolve_zotero_data_dir()
        db_path = zotero_dir / "zotero.sqlite"
        return ZoteroDB(db_path)

    @mcp.tool()
    def list_collections() -> str:
        """List all Zotero collections with their full paths."""
        try:
            with get_db() as db:
                collections = db.get_collections()
                if not collections:
                    return "No collections found."

                lines = [f"- {c.full_path} (key: {c.key})" for c in collections]
                return "\n".join(lines)
        except Exception as e:
            return f"Error listing collections: {str(e)}"

    @mcp.tool()
    def search_papers(query: str) -> str:
        """Search for papers by title in the Zotero library."""
        try:
            with get_db() as db:
                items = db.search_by_title(query)
                if not items:
                    return f"No papers found matching '{query}'."

                lines = []
                for item in items:
                    creators = ", ".join(item.creators)
                    lines.append(f"### {item.title}\n- Key: {item.key}\n- Type: {item.item_type}\n- Creators: {creators}\n- Date: {item.date}")

                return "\n\n".join(lines)
        except Exception as e:
            return f"Error searching papers: {str(e)}"

    @mcp.tool()
    def get_recent_papers(limit: int = 5) -> str:
        """Get the most recently added papers from Zotero."""
        try:
            with get_db() as db:
                items = db.get_recent_items(limit=limit)
                if not items:
                    return "No papers found."

                lines = []
                for item in items:
                    creators = ", ".join(item.creators)
                    lines.append(f"### {item.title}\n- Key: {item.key}\n- Added: {item.date_added}\n- Creators: {creators}")

                return "\n\n".join(lines)
        except Exception as e:
            return f"Error fetching recent papers: {str(e)}"

    @mcp.tool()
    def set_active_collection(key: str, full_path: str = "") -> str:
        """Select a collection as 'active' for future notes and searches.

        Args:
            key: The Zotero collection key (e.g., 'B4XKSUBJ').
            full_path: Optional human-readable path for display.
        """
        try:
            manager = ActiveCollectionManager()
            manager.set_active_collection(key, full_path)
            return f"Set active collection to: {full_path or key}"
        except Exception as e:
            return f"Error setting active collection: {str(e)}"

    @mcp.tool()
    def get_active_collection() -> str:
        """Get the currently selected active collection."""
        manager = ActiveCollectionManager()
        key = manager.get_active_collection_key()
        path = manager.get_active_collection_path()
        if not key:
            return "No active collection selected."
        return f"Active Collection: {path or 'N/A'} (Key: {key})"

    @mcp.tool()
    def create_note(content: str, collection_key: str | None = None, parent_item_key: str | None = None) -> str:
        """Create a new note in Zotero.

        If collection_key is not provided, it will use the active collection (if set).
        Requires ZOTERO_API_KEY and ZOTERO_USER_ID.
        """
        api_key = resolve_zotero_api_key()
        user_id = resolve_zotero_user_id()

        if not api_key or not user_id:
            return (
                "Error: Zotero API credentials not found. "
                "Please set ZOTERO_API_KEY and ZOTERO_USER_ID environment variables. "
                "See the README for instructions on obtaining these from zotero.org."
            )

        # Fallback to active collection if none provided
        if not collection_key:
            manager = ActiveCollectionManager()
            collection_key = manager.get_active_collection_key()

        try:
            writer = ZoteroWriter(library_id=user_id, api_key=api_key)
            result = writer.create_note(content=content, collection_key=collection_key, parent_item_key=parent_item_key)
            new_key = result.get("key", "unknown")
            loc = f"collection '{collection_key}'" if collection_key else "top-level"
            return f"Successfully created note in {loc}. Key: {new_key}"
        except Exception as e:
            return f"Error creating note: {str(e)}"

    return mcp
