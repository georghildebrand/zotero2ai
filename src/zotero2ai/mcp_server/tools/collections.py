import json
import logging
from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.collections import ActiveCollectionManager

logger = logging.getLogger(__name__)

def register_collection_tools(mcp: FastMCP):
    @mcp.tool()
    def list_collections(library_id: int | None = None, parent_key: str | None = None, limit: int = 100, start: int = 0) -> str:
        """
        List Zotero collections with pagination support.

        Args:
            library_id: Optional library ID to filter by
            parent_key: Optional parent collection key ('root' for top-level)
            limit: Maximum number of collections to return (default: 100)
            start: Starting offset for pagination (default: 0)

        Returns:
            JSON with collections array and pagination metadata
        """
        try:
            with get_client() as client:
                response = client.get_collections_paginated(parent_key=parent_key, library_id=library_id, limit=limit, start=start)

                pagination = response.get("pagination", {})
                if pagination.get("hasMore"):
                    logger.info(f"Collection list truncated. Total: {pagination.get('total')}, fetched: {len(response.get('data', []))}")

                return json.dumps(response, indent=2)
        except Exception as e:
            return f"Error listing collections: {str(e)}"

    @mcp.tool()
    def search_collections(query: str, limit: int = 10) -> str:
        """Search for Zotero collections by name (fuzzy).
        
        Args:
            query: Search query string
            limit: Maximum number of results to return (default: 10)
        """
        try:
            with get_client() as client:
                collections = client.search_collections(query, limit=limit)
                if not collections:
                    return f"No collections found matching '{query}'."

                lines = []
                for c in collections:
                    child_count = c.get("childCount", 0)
                    item_info = f"- {c['fullPath']} (key: {c['key']})"
                    if child_count > 0:
                        item_info += f" [{child_count} subcollections]"
                    lines.append(item_info)
                return "\n".join(lines)
        except Exception as e:
            return f"Error searching collections: {str(e)}"

    @mcp.tool()
    def set_active_collection(key: str, full_path: str = "") -> str:
        """Set a default collection for new notes and listing.
        
        Args:
            key: The Zotero collection key.
            full_path: Optional human-readable path for the collection.
        """
        try:
            with get_client() as client:
                manager = ActiveCollectionManager(client)
                manager.set_active_collection(key, full_path)
                return f"Successfully set active collection to: {full_path or key}"
        except Exception as e:
            return f"Error setting active collection: {str(e)}"

    @mcp.tool()
    def get_active_collection() -> str:
        """Get the currently selected active collection."""
        try:
            with get_client() as client:
                manager = ActiveCollectionManager(client)
                key = manager.get_active_collection_key()
                path = manager.get_active_collection_path()
                if not key:
                    return "No active collection selected."
                return f"Active Collection: {path or 'N/A'} (Key: {key})"
        except Exception as e:
            return f"Error getting active collection: {str(e)}"

    @mcp.tool()
    def get_collection_tree(depth: int = 99) -> str:
        """Get the full collection hierarchy as a nested tree JSON."""
        try:
            with get_client() as client:
                tree = client.get_collection_tree(depth=depth)
                return json.dumps(tree, indent=2)
        except Exception as e:
            return f"Error getting collection tree: {str(e)}"

    @mcp.tool()
    def get_collection_attachments(collection_key: str, limit: int = 100) -> str:
        """Get all attachments and their file paths for all items in a Zotero collection (batch mode).

        Args:
            collection_key: The key of the Zotero collection.
            limit: Maximum number of items to process (default: 100, max: 500).

        Returns:
            A formatted list of all items with their attachments and file paths.
        """
        try:
            with get_client() as client:
                items = client.get_collection_items(collection_key, limit=limit)

                if not items:
                    return f"No items found in collection {collection_key}."

                count = 0
                for item in items:
                    count += len(item.get("attachments", []))
                    if item.get("itemType") == "attachment":
                        count += 1
                total_attachments = count

                lines = [f"## Collection Items ({len(items)} items, {total_attachments} attachments)"]

                for item in items:
                    lines.append(f"\n### {item.get('title', 'Untitled')}")
                    lines.append(f"- Key: {item['key']}")
                    lines.append(f"- Type: {item.get('itemType', 'unknown')}")

                    if item.get("url"):
                        lines.append(f"- URL: {item['url']}")

                    creators = ", ".join(item.get("creators", []))
                    if creators:
                        lines.append(f"- Creators: {creators}")

                    attachments = item.get("attachments", [])
                    if item.get("itemType") == "attachment":
                        lines.append("- **This item is the attachment file itself:**")
                        lines.append(f"  - Content Type: {item.get('contentType', 'unknown')}")
                        if item.get("path"):
                            lines.append(f"    Path: `{item['path']}`")
                    
                    if attachments:
                        lines.append(f"- **Attachments ({len(attachments)}):**")
                        for att in attachments:
                            lines.append(f"  - {att['title']} ({att['contentType']})")
                            if att.get("path"):
                                lines.append(f"    Path: `{att['path']}`")
                            if att.get("url"):
                                lines.append(f"    URL: {att['url']}")
                    elif item.get("itemType") != "attachment":
                        lines.append("- No attachments")

                return "\n".join(lines)
        except Exception as e:
            return f"Error getting collection attachments: {str(e)}"
