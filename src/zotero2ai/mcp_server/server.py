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
    def list_collections() -> str:
        """List all Zotero collections with their full paths and keys."""
        try:
            with get_client() as client:
                collections = client.get_collections()
                if not collections:
                    return "No collections found."

                lines = [f"- {c['fullPath']} (key: {c['key']})" for c in collections]
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

                lines = [f"- {c['fullPath']} (key: {c['key']})" for c in collections]
                return "\n".join(lines)
        except Exception as e:
            return f"Error searching collections: {str(e)}"

    @mcp.tool()
    def search_papers(query: str) -> str:
        """Search for papers by title in the Zotero library."""
        try:
            with get_client() as client:
                items = client.search_items(query)
                if not items:
                    return f"No papers found matching '{query}'."

                lines = []
                for item in items:
                    creators = ", ".join(item["creators"])
                    lines.append(f"### {item['title']}\n- Key: {item['key']}\n- Type: {item['itemType']}\n- Creators: {creators}\n- Date: {item['date']}")

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
                    lines.append(f"### {item['title']}\n- Key: {item['key']}\n- Creators: {creators}")

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
    def create_or_extend_note(content: str, note_key: str | None = None, parent_item_key: str | None = None, collection_key: str | None = None, extend: bool = False) -> str:
        """Create a new note or extend an existing one.

        Args:
            content: The HTML/text content to add.
            note_key: If updating/extending, the key of the existing note.
            parent_item_key: Key of the item to attach a NEW note to.
            collection_key: Key of the collection for a NEW note.
            extend: If True and note_key is provided, appends content to the existing note.
        """
        try:
            with get_client() as client:
                if extend and note_key:
                    result = client.extend_note(note_key, content)
                    return f"Successfully extended note {note_key}."

                if note_key:
                    result = client.update_note(note_key, content=content)
                    return f"Successfully updated note {note_key}."

                # Fallback to active collection if creating new and no collection provided
                if not collection_key and not parent_item_key:
                    manager = ActiveCollectionManager()
                    collection_key = manager.get_active_collection_key()

                result = client.create_note(content=content, parent_item_key=parent_item_key, collections=[collection_key] if collection_key else None)
                new_key = result.get("key", "unknown")
                return f"Successfully created new note. Key: {new_key}"
        except Exception as e:
            return f"Error in create_or_extend_note: {str(e)}"

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

    return mcp
