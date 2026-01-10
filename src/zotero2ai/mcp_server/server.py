import logging

from mcp.server.fastmcp import FastMCP

from zotero2ai.config import resolve_zotero_bridge_port, resolve_zotero_mcp_token
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.utils import generate_friendly_name

logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""
    mcp = FastMCP("zotero2ai")

    def get_client() -> PluginClient:
        token = resolve_zotero_mcp_token()
        if not token:
            raise ValueError("Zotero MCP token not found. Please ensure the Zotero Bridge Plugin is installed and ZOTERO_MCP_TOKEN environment variable is set.")
        
        port = resolve_zotero_bridge_port()
        base_url = f"http://127.0.0.1:{port}"
        return PluginClient(base_url=base_url, auth_token=token)

    @mcp.tool()
    def list_collections(parent_collection_key: str | None = None) -> str:
        """List Zotero collections.

        Args:
            parent_collection_key: Use "root" for top-level collections, or a specific key for its children. If omitted, lists all.
        """
        try:
            with get_client() as client:
                collections = client.get_collections(parent_key=parent_collection_key)
                if not collections:
                    return "No collections found."

                lines = []
                for c in collections:
                    child_count = c.get("childCount", 0)
                    info = f"- {c['fullPath']} (key: {c['key']})"
                    if child_count > 0:
                        info += f" [{child_count} subcollections]"
                    lines.append(info)
                return "\n".join(lines)
        except Exception as e:
            return f"Error listing collections: {str(e)}"

    @mcp.tool()
    def search_collections(query: str) -> str:
        """Search for Zotero collections by name (fuzzy)."""
        try:
            with get_client() as client:
                collections = client.search_collections(query)
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
    def search_papers(query: str | None = None, tag: str | None = None, limit: int = 10) -> str:
        """Search for papers by title or tag in the Zotero library.
        
        Args:
            query: Optional search query for titles.
            tag: Optional tag to filter by.
            limit: Maximum number of results.
        """
        try:
            with get_client() as client:
                items = client.search_items(query=query, tag=tag, limit=limit)
                if not items:
                    msg = "No papers found"
                    if query: msg += f" matching '{query}'"
                    if tag: msg += f" with tag '{tag}'"
                    return msg + "."

                lines = []
                for item in items:
                    creators = ", ".join(item["creators"])
                    item_info = f"### {item['title']}\n- Key: {item['key']}\n- Type: {item['itemType']}\n- Creators: {creators}\n- Date: {item['date']}"
                    
                    if item.get("url"):
                        item_info += f"\n- URL: {item['url']}"

                    # Add search tags info if they match
                    if item.get("tags"):
                        item_info += f"\n- Tags: {', '.join(item['tags'])}"

                    # Add attachment file paths if available
                    attachments = item.get("attachments", [])
                    if attachments:
                        item_info += "\n- Attachments:"
                        for att in attachments:
                            item_info += f"\n  - {att['title']} ({att['contentType']})"
                            if att.get("path"):
                                item_info += f"\n    Path: `{att['path']}`"
                            if att.get("url"):
                                item_info += f"\n    URL: {att['url']}"
                    
                    lines.append(item_info)

                return "\n\n".join(lines)
        except Exception as e:
            return f"Error searching papers: {str(e)}"

    @mcp.tool()
    def get_recent_papers(limit: int = 5) -> str:
        """Get the most recently added papers from Zotero."""
        try:
            with get_client() as client:
                items = client.get_recent_items(limit=limit)
                if not items:
                    return "No papers found."

                lines = []
                for item in items:
                    creators = ", ".join(item["creators"])
                    item_info = f"### {item['title']}\n- Key: {item['key']}\n- Creators: {creators}"
                    
                    if item.get("url"):
                        item_info += f"\n- URL: {item['url']}"

                    # Add attachment file paths if available
                    attachments = item.get("attachments", [])
                    if attachments:
                        item_info += "\n- Attachments:"
                        for att in attachments:
                            item_info += f"\n  - {att['title']} ({att['contentType']})"
                            if att.get("path"):
                                item_info += f"\n    Path: `{att['path']}`"
                            if att.get("url"):
                                item_info += f"\n    URL: {att['url']}"
                    
                    lines.append(item_info)

                return "\n\n".join(lines)
        except Exception as e:
            return f"Error fetching recent papers: {str(e)}"

    @mcp.tool()
    def list_notes(collection_key: str | None = None, parent_item_key: str | None = None) -> str:
        """List notes from Zotero. Use collection_key or parent_item_key to filter.

        If neither is provided and an active collection is set, it uses that.
        """
        try:
            if not collection_key and not parent_item_key:
                manager = ActiveCollectionManager()
                collection_key = manager.get_active_collection_key()

            if not collection_key and not parent_item_key:
                return "Error: Provide a collection_key, parent_item_key, or set an active collection first."

            with get_client() as client:
                notes = client.get_notes(collection_key=collection_key, parent_item_key=parent_item_key)
                if not notes:
                    return "No notes found for the given criteria."

                lines = []
                for note in notes:
                    friendly_name = generate_friendly_name(note.get("note", ""))
                    lines.append(f"- {friendly_name} ({note['key']})")

                return "Available Notes:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing notes: {str(e)}"

    @mcp.tool()
    def read_note(key: str) -> str:
        """Read the full content of a Zotero note by its key."""
        try:
            with get_client() as client:
                note = client.get_note(key)
                if not note:
                    return f"Note with key {key} not found."

                # Format friendly output
                content = note.get("note", "No content.")
                # Basic strip of some HTML tags for cleaner AI reading if needed,
                # but often the AI prefers the structure. Let's keep it as is or do minimal cleaning.
                return f"## Note {key}\n\n{content}"
        except Exception as e:
            return f"Error reading note: {str(e)}"

    @mcp.tool()
    def create_or_extend_note(content: str, note_key: str | None = None, parent_item_key: str | None = None, collection_key: str | None = None, extend: bool = False, tags: list[str] | None = None, related: list[str] | None = None) -> str:
        """Create a new note or extend an existing one.

        Args:
            content: The HTML/text content to add.
            note_key: If updating/extending, the key of the existing note.
            parent_item_key: Key of the item to attach a NEW note to.
            collection_key: Key of the collection for a NEW note.
            extend: If True and note_key is provided, appends content to the existing note.
            tags: Optional list of tags to add to the note.
            related: Optional list of related item keys.
        """
        try:
            with get_client() as client:
                if extend and note_key:
                    # Extend doesn't support tags in the logic below, let's fix that or ignore tags on extend
                    # Actually, we can update tags while extending
                    result = client.extend_note(note_key, content)
                    if tags:
                        client.update_note(note_key, tags=tags)
                    if related:
                        client.update_note(note_key, related=related)
                    return f"Successfully extended note {note_key}."

                if note_key:
                    result = client.update_note(note_key, content=content, tags=tags, related=related)
                    return f"Successfully updated note {note_key}."

                # Fallback to active collection if creating new and no collection provided
                if not collection_key and not parent_item_key:
                    manager = ActiveCollectionManager()
                    collection_key = manager.get_active_collection_key()

                result = client.create_note(content=content, parent_item_key=parent_item_key, collections=[collection_key] if collection_key else None, tags=tags)
                new_key = result.get("key", "unknown")

                if related and new_key != "unknown":
                    client.update_note(new_key, related=related)
                
                return f"Successfully created new note. Key: {new_key}"
        except Exception as e:
            return f"Error in create_or_extend_note: {str(e)}"

    @mcp.tool()
    def get_item_attachments(item_key: str) -> str:
        """Get all attachments and their file paths for a specific Zotero item.
        
        Args:
            item_key: The key of the Zotero item to get attachments for.
        
        Returns:
            A formatted list of attachments with their file paths, or an error message.
        """
        try:
            with get_client() as client:
                items = client.search_items(item_key)
                if not items:
                    return f"Item with key {item_key} not found."
                
                item = items[0]
                attachments = item.get("attachments", [])
                
                if not attachments:
                    return f"No attachments found for item '{item.get('title', item_key)}'."
                
                lines = [f"## Attachments for: {item.get('title', item_key)}"]
                if item.get("url"):
                     lines.append(f"- **Item URL**: {item['url']}")

                for att in attachments:
                    lines.append(f"\n### {att['title']}")
                    lines.append(f"- Type: {att['contentType']}")
                    lines.append(f"- Key: {att['key']}")
                    if att.get("path"):
                        lines.append(f"- **File Path**: `{att['path']}`")
                    if att.get("url"):
                        lines.append(f"- **URL**: {att['url']}")
                
                return "\n".join(lines)
        except Exception as e:
            return f"Error getting attachments: {str(e)}"

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
                
                # Count total attachments
                total_attachments = sum(len(item.get("attachments", [])) for item in items)
                
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
                    if attachments:
                        lines.append(f"- **Attachments ({len(attachments)}):**")
                        for att in attachments:
                            lines.append(f"  - {att['title']} ({att['contentType']})")
                            if att.get("path"):
                                lines.append(f"    Path: `{att['path']}`")
                            if att.get("url"):
                                lines.append(f"    URL: {att['url']}")
                    else:
                        lines.append("- No attachments")
                
                return "\n".join(lines)
        except Exception as e:
            return f"Error getting collection attachments: {str(e)}"

    @mcp.tool()
    def set_active_collection(key: str, full_path: str = "") -> str:
        """Select a collection as 'active' for future notes and searches."""
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
    def list_tags() -> str:
        """List all tags available in the Zotero library."""
        try:
            with get_client() as client:
                tags = client.get_tags()
                if not tags:
                    return "No tags found."
                return "Available Tags:\n- " + "\n- ".join(tags)
        except Exception as e:
            return f"Error listing tags: {str(e)}"

    @mcp.tool()
    def rename_tag(old_name: str, new_name: str) -> str:
        """Rename a tag library-wide (refactor tags).
        
        Args:
            old_name: The current tag name to be replaced.
            new_name: The new tag name.
        """
        try:
            with get_client() as client:
                client.rename_tag(old_name, new_name)
                return f"Successfully renamed tag from '{old_name}' to '{newName}'."
        except Exception as e:
            return f"Error renaming tag: {str(e)}"

    return mcp
