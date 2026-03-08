import json
import logging

from mcp.server.fastmcp import FastMCP

from zotero2ai.config import resolve_zotero_bridge_port, resolve_zotero_mcp_token
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem
from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.utils import clean_html, generate_friendly_name

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
        import json

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
    def search_papers(query: str | None = None, tag: str | None = None, collection_key: str | None = None, limit: int = 10) -> str:
        """Search for papers by title or tag in the Zotero library.

        Args:
            query: Optional search query for titles.
            tag: Optional tag to filter by.
            collection_key: Optional collection key to search within.
            limit: Maximum number of results.
        """
        try:
            with get_client() as client:
                items = client.search_items(query=query, tag=tag, collection_key=collection_key, limit=limit)
                if not items:
                    msg = "No papers found"
                    if query:
                        msg += f" matching '{query}'"
                    if tag:
                        msg += f" with tag '{tag}'"
                    if collection_key:
                        msg += f" in collection '{collection_key}'"
                    return msg + "."

                lines = []
                for item in items:
                    # Check for error in formatted item
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}\n- Details: {item.get('details', 'No details available')}")
                        continue

                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_type = item.get("itemType", "unknown")
                    item_date = item.get("date", "Unknown")
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Type: {item_type}\n- Creators: {creators}\n- Date: {item_date}"

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
                    # Check for error in formatted item
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}")
                        continue

                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Creators: {creators}"

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
    def list_notes(collection_key: str | None = None, parent_item_key: str | None = None) -> str:
        """List notes from Zotero.

        If neither collection_key nor parent_item_key is provided, falls back to the active collection
        (if one is set via settings).
        """
        try:
            with get_client() as client:
                manager = ActiveCollectionManager(client)

                if not collection_key and not parent_item_key:
                    collection_key = manager.get_active_collection_key()

                if not collection_key and not parent_item_key:
                    return "Error: Provide a collection_key, parent_item_key, or set an active collection first."

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
    def list_notes_recursive(
        collection_key: str,
        date_from: str | None = None,
        date_to: str | None = None,
        include_content: bool = False,
        query: str | None = None,
        max_items: int = 200,
        cursor: int = 0,
    ) -> str:
        """Bulk-read: traverse a collection subtree and return all notes in one call.

        Replaces the pattern of calling list_collections + list_notes for each
        subcollection. Ideal for ingesting a date-filtered slice of notes from
        deep hierarchies (e.g. 'all meeting notes from the last 6 months').

        Args:
            collection_key: Collection to start from. Use 'root' for the entire library.
            date_from: ISO 8601 date – only return notes modified after this date.
            date_to: ISO 8601 date – only return notes modified before this date.
            include_content: If True, each note includes content_html and content_plain.
                             Warning: significantly slower for large result sets.
            query: Optional substring to filter note titles.
            max_items: Max notes per page (default: 200, max recommended: 500).
            cursor: Pagination offset. Use next_cursor from a previous call.

        Returns:
            JSON with 'items', 'total', and 'next_cursor' (null if no more results).
            Each item contains: note_key, title, created, modified, collection_key,
            collection_path, parent_item_key, and optionally content_html / content_plain.
        """
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.list_notes_recursive(
                    collection_key=collection_key,
                    date_from=date_from,
                    date_to=date_to,
                    include_content=include_content,
                    query=query,
                    max_items=max_items,
                    cursor=cursor,
                )
                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error in list_notes_recursive: {str(e)}"

    @mcp.tool()
    def create_or_extend_note(
        content: str,
        note_key: str | None = None,
        parent_item_key: str | None = None,
        collection_key: str | None = None,
        extend: bool = False,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> str:
        """Create a new note or extend an existing one.

        Semantics:
        - note_key + extend=True  → append content to the existing note (tags updated if provided)
        - note_key + extend=False → replace/upsert the entire note content
        - no note_key             → create new note:
            - parent_item_key: attaches note as child of that item
            - collection_key: places note directly in that collection
            - neither: uses the currently active collection (fallback)

        MANDATORY RELATIONSHIPS: Whenever you create a memory unit (memory_create_item) that
        refers to this note, you MUST include the memory item's key in the 'related' parameter
        to establish a bidirectional Zotero link. This ensures the agent memory is searchable
        while documentation remains navigable.
        """
        try:
            with get_client() as client:
                # ── Case 1: Extend (append) existing note ──────────────────
                if extend and note_key:
                    client.extend_note(note_key, content)
                    # Apply optional tag/related updates in one call after extend
                    if tags or related:
                        client.update_note(note_key, tags=tags or None, related=related or None)
                    return f"Successfully extended note {note_key}."

                # ── Case 2: Replace/upsert existing note ───────────────────
                if note_key:
                    client.update_note(
                        note_key,
                        content=content,
                        tags=tags if tags else None,
                        related=related if related else None,
                    )
                    return f"Successfully updated note {note_key}."

                # ── Case 3: Create new note ────────────────────────────────
                # Resolve target: parent_item_key > collection_key > active collection
                target_collection: str | None = collection_key
                if not target_collection and not parent_item_key:
                    manager = ActiveCollectionManager(client)
                    target_collection = manager.get_active_collection_key()
                    if not target_collection:
                        return (
                            "Error: cannot create note – provide parent_item_key, collection_key, "
                            "or set an active collection first via set_active_collection."
                        )

                result = client.create_note(
                    content=content,
                    parent_item_key=parent_item_key,
                    collections=[target_collection] if target_collection else None,
                    tags=tags if tags else None,
                )
                new_key = result.get("key", "")

                if not new_key:
                    return f"Error: note creation returned no key. Raw response: {result}"

                # Set related links after creation (separate call required by Zotero API)
                if related:
                    try:
                        client.update_note(new_key, related=related)
                    except Exception as rel_err:
                        return (
                            f"Note created (key: {new_key}) but failed to set related links: {rel_err}. "
                            "You can retry with memory_link_items."
                        )

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
                # Use get_item for reliable key-based lookup
                item = client.get_item(item_key)
                if not item:
                    return f"Item with key {item_key} not found. Ensure the key is correct and the item is in your library."

                # If formatting failed
                if "error" in item:
                    return f"Error details for item {item_key}: {item['error']} - {item.get('details', 'No further details')}"

                # If the item is already an attachment
                if item.get("itemType") == "attachment":
                    lines = [f"## Attachment Info: {item.get('title', item_key)}"]
                    lines.append(f"- Key: {item['key']}")
                    lines.append(f"- Type: {item.get('contentType', 'unknown')}")
                    if item.get("path"):
                        lines.append(f"- **File Path**: `{item['path']}`")
                    if item.get("url"):
                        lines.append(f"- **URL**: {item['url']}")
                    return "\n".join(lines)

                attachments = item.get("attachments", [])

                if not attachments:
                    return f"No attachments found for item '{item.get('title', item_key)}' (Key: {item_key})."

                lines = [f"## Attachments for: {item.get('title', item_key)} (Key: {item_key})"]
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

                # Count total attachments (including items that are already attachments)
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
                    
                    # Special handling for standalone attachments
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

    @mcp.tool()
    def memory_set_active_project(project_slug: str, root_name: str = "Agent Memory") -> str:
        """Select a project slug as 'active' for future memory items.
        
        This persists the project choice in Zotero (under _System/Settings), 
        so agents will by default save new memory units to this project.
        Automatically switches the active collection if a mapping exists.
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                settings = mm.get_settings(cols["system"])
                
                settings["active_project_slug"] = project_slug
                
                # Auto-switch active collection if it is defined in project metadata
                project_meta = settings.get("projects", {}).get(project_slug, {})
                active_col_key = project_meta.get("active_collection_key")
                
                info_msg = ""
                if active_col_key:
                    settings["active_collection_key"] = active_col_key
                    settings["active_collection_path"] = project_meta.get("active_collection_path", "")
                    info_msg = f" Also switched active collection to: {settings['active_collection_path']}"
                
                mm.update_settings(cols["system"], settings)
                return f"Successfully set active memory project to: {project_slug} in Zotero.{info_msg}"
        except Exception as e:
            return f"Error setting active project: {str(e)}"

    @mcp.tool()
    def memory_update_project_mapping(
        project_slug: str, 
        nickname: str | None = None, 
        related_collections: list[str] | None = None,
        active_collection_key: str | None = None,
        active_collection_path: str | None = None,
        root_name: str = "Agent Memory"
    ) -> str:
        """Update the mapping/metadata for a memory project.
        
        Use this to store project nicknames or link 'normal' Zotero collections 
        (like library collections) to an agent memory project.
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                settings = mm.get_settings(cols["system"])
                
                if "projects" not in settings:
                    settings["projects"] = {}
                
                if project_slug not in settings["projects"]:
                    settings["projects"][project_slug] = {}
                
                if nickname:
                    settings["projects"][project_slug]["nickname"] = nickname
                if related_collections is not None:
                    settings["projects"][project_slug]["related_collections"] = related_collections
                if active_collection_key:
                    settings["projects"][project_slug]["active_collection_key"] = active_collection_key
                if active_collection_path:
                    settings["projects"][project_slug]["active_collection_path"] = active_collection_path
                
                mm.update_settings(cols["system"], settings)
                return f"Successfully updated mapping for project '{project_slug}' in Zotero."
        except Exception as e:
            return f"Error updating project mapping: {str(e)}"

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
                return f"Successfully renamed tag from '{old_name}' to '{new_name}'."
        except Exception as e:
            return f"Error renaming tag: {str(e)}"

    @mcp.tool()
    def get_collection_tree(depth: int = 99) -> str:
        """Get the full collection hierarchy as a nested tree JSON."""
        import json

        try:
            with get_client() as client:
                tree = client.get_collection_tree(depth=depth)
                return json.dumps(tree, indent=2)
        except Exception as e:
            return f"Error getting collection tree: {str(e)}"

    @mcp.tool()
    def open_item(item_key: str) -> str:
        """Open an item's attachment in the local default OS viewer.

        Args:
            item_key: Key of the item.
        """
        import os
        import subprocess
        import sys

        try:
            with get_client() as client:
                # Use robust get_item
                try:
                    item = client.get_item(item_key)
                except Exception:
                    return f"Item {item_key} not found (check if plugin is updated)."

                if not item:
                    return f"Item {item_key} not found."

                target_path = ""

                # 1. Check if item itself has a path (if it's an attachment)
                if item.get("path"):
                    target_path = item.get("path") or ""

                # 2. If not, check "attachments" list
                if not target_path:
                    attachments = item.get("attachments", [])
                    # Prefer PDF
                    for att in attachments:
                        if att.get("contentType") == "application/pdf" and att.get("path"):
                            target_path = att.get("path") or ""
                            logging.info(f"Selected PDF attachment: {att.get('title')}")
                            break

                    # Fallback to any file
                    if not target_path and attachments:
                        for att in attachments:
                            if att.get("path"):
                                target_path = att.get("path") or ""
                                logging.info(f"Selected fallback attachment: {att.get('title')}")
                                break

                if not target_path:
                    return "No local file path found for this item."

                # Open the file
                if sys.platform == "darwin":
                    subprocess.call(["open", target_path])
                elif sys.platform == "win32":
                    os.startfile(target_path)
                else:
                    subprocess.call(["xdg-open", target_path])

                return f"Opening: {target_path}"

        except Exception as e:
            return f"Error opening item: {str(e)}"

    @mcp.tool()
    def get_item_content(key: str) -> str:
        """Get the text content of a Zotero item (PDF or HTML).

        Useful for reading the full text of a paper or a web snapshot.
        If you provide the key of a parent item (e.g. a paper), it will automatically find the best available attachment (PDF preferred, then HTML).

        Args:
            key: The key of the item or attachment.
        """
        try:
            with get_client() as client:
                data = client.get_item_content(key)
                if not data:
                    return f"No content found for item {key}."

                filename = data.get("filename", "Unknown")
                content_type = data.get("contentType", "Unknown")
                content = data.get("content")
                
                if (not content or content == ""):
                    if "error" in data or "message" in data:
                        diag = f"(Indexed: {data.get('indexed', 'Unknown')}, Path: {data.get('path', 'Unknown')})"
                        return f"## Content Missing for {filename}\n\nError from Zotero: {data.get('message', 'No details available.')} {diag}\n\nFull Diagnostic: {str(data)}"
                    else:
                        return f"## Content Empty for {filename}\n\nNo text extracted from this item. Full Diagnostic: {str(data)}"
                
                content = content or ""
                
                # If it's HTML, clean it up to prevent giant raw strings
                is_html = content_type == "text/html" or filename.lower().endswith((".html", ".htm"))
                if is_html:
                    content = clean_html(content, preserve_newlines=True)
                    
                return f"## Content of {filename} ({content_type})\n\n{content}"
        except Exception as e:
            import httpx
            if isinstance(e, httpx.HTTPStatusError):
                try:
                    body = e.response.json()
                    msg = body.get("message") or body.get("error")
                    if msg:
                        return f"Error getting item content: {msg} (Status: {e.response.status_code})"
                except Exception:
                    pass
            return f"Error getting item content: {str(e)}"

    @mcp.tool()
    def memory_get_context(root_name: str = "Agent Memory") -> str:
        """Get the current memory context, including active project, write policy, and registry status."""
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)

                # Try to determine active project from active collection
                from zotero2ai.zotero.collections import ActiveCollectionManager

                manager = ActiveCollectionManager(client)
                active_col_key = manager.get_active_collection_key()
                active_col_path = manager.get_active_collection_path()

                registry_title = "[MEM][system][global] Tag Registry"
                items = client.search_items(tag="mem:role:global", collection_key=cols["system"])
                registry_ready = any(i["title"] == registry_title for i in items)

                settings = mm.get_settings(cols["system"])
                active_project_slug = settings.get("active_project_slug")

                context = {
                    "root_collection": root_name,
                    "root_key": cols["root"],
                    "system_key": cols["system"],
                    "active_project_key": active_col_key,
                    "active_project_path": active_col_path,
                    "active_project_slug": active_project_slug,
                    "project_mappings": settings.get("projects", {}),
                    "write_policy": "Append-only for agent memories. User has full control. Metadata block in note is canonical source of truth.",
                    "registry_status": "Ready" if registry_ready else "Missing (Run memory_initialize)",
                    "version": "0.1.0-foundation",
                }
                return json.dumps(context, indent=2)
        except Exception as e:
            return f"Error getting context: {str(e)}"

    @mcp.tool()
    def memory_initialize(root_name: str = "Agent Memory") -> str:
        """Initialize the memory system structure and create a default tag registry.
        Use this to bootstrap the memory system if it's the first time or if the registry is missing.
        """
        import yaml  # type: ignore[import-untyped]

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)

                # Check if registry exists
                registry_title = "[MEM][system][global] Tag Registry"
                items = client.search_items(tag="mem:role:global", collection_key=cols["system"])
                if any(i["title"] == registry_title for i in items):
                    return f"Memory system already initialized in '{root_name}'. System key: {cols['system']}"

                # Create initial registry
                default_registry = {
                    "allowed_tags": {
                        "mem:class:": ["unit", "concept", "project", "system"],
                        "mem:project:": [],  # Allow any value for now or we can populate it
                        "mem:role:": ["question", "observation", "hypothesis", "result", "synthesis"],
                        "mem:state:": ["active", "superseded", "archived"],
                        "mem:source:": ["agent", "user", "paper", "conversation", "manual"],
                        "mem:domain:": [],
                    }
                }
                yaml_content = yaml.dump(default_registry, default_flow_style=False)
                # Use standard MemoryItem style rendering but manual creation for bootstrapping
                note_html = f"<pre>{yaml_content}</pre><hr/><p>Global Tag Registry for Zotero Agent Memory Pack.</p>"

                # Create the registry item (type: report for consistency)
                resp = client.create_item(
                    item_type="report", title=registry_title, tags=["mem:class:system", "mem:role:global"], collections=[cols["system"]], note=note_html
                )

                return f"Successfully initialized memory system in '{root_name}'.\nRoot key: {cols['root']}\nSystem key: {cols['system']}\nRegistry item key: {resp.get('key')}"
        except Exception as e:
            return f"Error initializing memory: {str(e)}"

    @mcp.tool()
    def memory_get_registry(root_name: str = "Agent Memory") -> str:
        """Load the memory tag registry. Use this to find allowed tags before creating items."""
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                registry = mm.get_registry(cols["system"])
                return json.dumps(registry, indent=2)
        except Exception as e:
            return f"Error loading registry: {str(e)}"

    @mcp.tool()
    def memory_create_item(
        mem_class: str,
        role: str,
        project: str,
        title_label: str,
        content: str,
        source: str = "agent",
        confidence: str = "medium",
        tags: list[str] | None = None,
        root_name: str = "Agent Memory",
    ) -> str:
        """Create a new memory item.

        MANDATORY RELATIONSHIPS: If this memory refers to a detailed Zotero note, you MUST
        include the note's key in the 'related' parameter of create_or_extend_note, or use
        memory_link_items to link them. This ensures the agent memory pack remains
        navigable across high-density documentation.

        AUTOSAVE DIRECTIVE: You are ENCOURAGED to USE THIS TOOL PROACTIVELY to
        autosave high-utility facts, resolutions, and conclusions as 'unit' items
        without asking the user for permission.

        NOTE: For 'concept' or 'synthesis' class items, prefer using the dedicated
        memory_synthesize tool. If you use this tool directly for a concept, ensure
        you have user approval before proceeding.
        """

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)

                # Validation
                registry = mm.get_registry(cols["system"])
                validate_list = [f"mem:class:{mem_class}", f"mem:role:{role}", f"mem:project:{project}"]
                if tags:
                    validate_list.extend(tags)

                try:
                    mm.validate_tags(validate_list, registry)
                except ValueError as ve:
                    return f"Validation Error: {str(ve)}. Check memory_get_registry for allowed values."

                # Creation
                mem_id = MemoryItem.generate_mem_id(project)
                full_title = f"[MEM][{mem_class}][{project}] {title_label}"

                m_item = MemoryItem(
                    mem_id=mem_id, mem_class=mem_class, role=role, project=project, title=full_title, content=content, source=source, confidence=confidence, tags=tags or []
                )

                resp = mm.create_memory_item(m_item, cols["project"])
                msg = f"Successfully created memory item: {full_title} (Key: {resp.get('key')})"
                
                # Automated Synthesis Feedback
                suggestion = mm.check_synthesis_needed(project)
                if suggestion:
                    msg += f"\n\n{suggestion}"
                
                return msg
        except Exception as e:
            return f"Error creating memory item: {str(e)}"

    @mcp.tool()
    def bulk_memory_create(
        items: list[dict],
        dry_run: bool = False,
        allow_concepts: bool = False,
        root_name: str = "Agent Memory",
    ) -> str:
        """Bulk-write: create many memory units in a single MCP call.

        Reduces tool calls by 30-200× when ingesting large sets of observations,
        e.g. after processing a batch of meeting notes or during a project digest.

        Workflow:
        1. Call with dry_run=True to validate all items and inspect errors.
        2. Fix any tag/field errors reported.
        3. Re-call with dry_run=False to commit.

        Args:
            items: List of item dicts. Required per item:
                   - project (str): project slug, e.g. 'centric-software'
                   - mem_class (str): 'unit' (use allow_concepts=True for concept/synthesis)
                   - role (str): 'observation' | 'result' | 'hypothesis' | 'question'
                   - title_label (str): short label, becomes part of the Zotero title
                   - content (str): full Markdown content for the note body
                   Optional per item:
                   - tags (list[str]): extra mem:domain:* or similar tags
                   - confidence (str): 'high' | 'medium' | 'low'  (default: 'medium')
                   - source (str): 'agent' | 'user' | 'paper' etc. (default: 'agent')
                   - idempotency_key (str): stable unique string to prevent duplicates
                     on re-runs. Embedded in note content as invisible marker.
            dry_run: If True, validate but do NOT write to Zotero. Returns a
                     validation report with would_create / validation_errors counts.
            allow_concepts: If True, allow mem_class='concept' or 'synthesis'.
                            Requires explicit opt-in to prevent accidental overwrites.
            root_name: Root collection name for Agent Memory (default: 'Agent Memory').

        Returns:
            JSON report:
            {
              "dry_run": bool,
              "total": int,
              "created": int,           // only when dry_run=False
              "would_create": int,      // only when dry_run=True
              "skipped_duplicates": int,
              "errors": ["item-label: reason", ...],
              "items": [{"idempotency_key", "key", "title", "status", "reason?"}],
              "synthesis_hints": [...]  // suggestions after bulk write
            }
        """
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.bulk_create_memory_items(
                    items=items,
                    dry_run=dry_run,
                    allow_concepts=allow_concepts,
                    root_name=root_name,
                )
                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error in bulk_memory_create: {str(e)}"

    @mcp.tool()
    def memory_link_items(source_key: str, target_key: str) -> str:
        """Create a Zotero Related link for navigation between two memory items."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                mm.link_items(source_key, target_key)
                return f"Successfully linked {source_key} to {target_key}."
        except Exception as e:
            return f"Error linking items: {str(e)}"

    # ── Phase 2: Retrieval & Recall Tools ──────────────────────────

    @mcp.tool()
    def memory_recall(
        project: str | None = None,
        tags: list[str] | None = None,
        state: str = "active",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
        root_name: str = "Agent Memory",
    ) -> str:
        """Recall memory items with structured filtering.

        Use this to retrieve previously stored memories by project, tags, state, or date range.
        Results include parsed metadata (mem_id, class, role, confidence) and a content preview.

        Args:
            project: Project slug (e.g, 'lora-geometry'). If None, searches across root.
            tags: Additional tag filters (AND logic), e.g. ['mem:role:hypothesis']
            state: State filter: 'active' (default), 'superseded', 'archived', or '' for all
            date_from: ISO date, only items added after this date
            date_to: ISO date, only items added before this date
            limit: Max results (default: 20)
            root_name: Root collection name
        """
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                results = mm.recall(
                    project_slug=project,
                    tags=tags,
                    state=state,
                    date_from=date_from,
                    date_to=date_to,
                    limit=limit,
                    root_name=root_name,
                )

                if not results:
                    return "No matching memories found."

                return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error recalling memories: {str(e)}"

    @mcp.tool()
    def memory_timeline(
        project: str,
        limit: int = 30,
        root_name: str = "Agent Memory",
    ) -> str:
        """Get a chronological timeline of a project's memories (newest first).

        Use this to see the history of observations, questions, and results in a project.

        Args:
            project: Project slug (e.g. 'lora-geometry')
            limit: Max results (default: 30)
            root_name: Root collection name
        """
        import json

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                results = mm.timeline(
                    project_slug=project,
                    limit=limit,
                    root_name=root_name,
                )

                if not results:
                    return f"No memories found for project '{project}'."

                return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error building timeline: {str(e)}"

    @mcp.tool()
    def memory_related_graph(
        item_key: str,
        hops: int = 1,
    ) -> str:
        """Follow Related links from a memory item to explore connections.

        Returns a nested graph of related items. Use hops=1 for immediate neighbors,
        hops=2 for neighbors-of-neighbors, etc.

        Args:
            item_key: The starting memory item key
            hops: How many link hops to follow (default: 1, max: 3)
        """
        import json

        if hops > 3:
            hops = 3  # Safety limit

        try:
            with get_client() as client:
                mm = MemoryManager(client)
                graph = mm.follow_links(item_key, hops=hops)
                return json.dumps(graph, indent=2, default=str)
        except Exception as e:
            return f"Error following links: {str(e)}"

    @mcp.tool()
    def memory_supersede(
        old_key: str,
        new_title_label: str,
        new_content: str,
        reason: str,
        project: str,
        mem_class: str = "unit",
        role: str = "observation",
        confidence: str = "medium",
        root_name: str = "Agent Memory",
    ) -> str:
        """Supersede an old memory with an updated version.

        IMPORTANT: This operation marks the old memory as superseded and creates a
        replacement linked to it. You MUST confirm with the user before calling this.
        Ask: 'I want to supersede memory [old_key] with updated information. Proceed?'

        This is the ONLY case where the agent modifies an existing item's state.

        Args:
            old_key: Key of the memory item to supersede
            new_title_label: Short label for the new memory title
            new_content: Updated content for the replacement memory
            reason: Why this memory is being superseded (included in content)
            project: Project slug
            mem_class: Class for the new item (default: 'unit')
            role: Role for the new item (default: 'observation')
            confidence: Confidence for the new item (default: 'medium')
            root_name: Root collection name
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)

                # Build the new item
                mem_id = MemoryItem.generate_mem_id(project)
                full_title = f"[MEM][{mem_class}][{project}] {new_title_label}"
                full_content = f"Supersedes: {old_key}\nReason: {reason}\n\n{new_content}"

                new_item = MemoryItem(
                    mem_id=mem_id,
                    mem_class=mem_class,
                    role=role,
                    project=project,
                    title=full_title,
                    content=full_content,
                    source="agent",
                    confidence=confidence,
                )

                result = mm.supersede(old_key, new_item, cols["project"])
                return (
                    f"Successfully superseded memory.\n"
                    f"Old item: {result['old_key']} → marked as superseded\n"
                    f"New item: {result['new_key']} → active\n"
                    f"Items are linked via Zotero Related."
                )
        except Exception as e:
            return f"Error superseding memory: {str(e)}"

    @mcp.tool()
    def memory_synthesize(
        source_keys: list[str],
        title_label: str,
        content: str,
        project: str,
        supersede_sources: bool = False,
        mem_class: str = "concept",
        confidence: str = "high",
        root_name: str = "Agent Memory",
    ) -> str:
        """Synthesize multiple source memories into a single higher-level concept or summary.

        IMPORTANT: If supersede_sources is True, this marks the source memories as superseded!
        You should confirm with the user before using this operation if you are unsure.

        Args:
            source_keys: Keys of the memory items to synthesize
            title_label: Short title for the new synthesis
            content: Detailed markdown content synthesizing the sources
            project: Project slug
            supersede_sources: If True, marks all source_keys as superseded
            mem_class: The memory class ('unit' or 'concept', default 'concept')
            confidence: Confidence level (default 'high')
            root_name: Root collection name
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)

                mem_id = MemoryItem.generate_mem_id(project)
                full_title = f"[MEM][{mem_class}][{project}] {title_label}"

                new_item = MemoryItem(
                    mem_id=mem_id,
                    mem_class=mem_class,
                    role="synthesis",
                    project=project,
                    title=full_title,
                    content=content,
                    source="agent",
                    confidence=confidence,
                )

                result = mm.synthesize(
                    source_keys=source_keys,
                    new_item=new_item,
                    project_key=cols["project"],
                    supersede_sources=supersede_sources
                )
                
                return (
                    f"Successfully created synthesis memory.\n"
                    f"Synthesis Key: {result['synthesis_key']} (Active)\n"
                    f"Sources Linked: {result['sources_linked']}\n"
                    f"Sources Superseded: {result['sources_superseded']}"
                )
        except Exception as e:
            return f"Error synthesizing memories: {str(e)}"

    @mcp.tool()
    def memory_suggest_consolidation(
        project: str,
        limit: int = 20,
    ) -> str:
        """Fetch recent raw (unit/observation) memories that might be candidates for synthesis.
        
        Use this tool periodically to review recent memories in a project and decide if
        they should be consolidated into a higher-level synthesis using memory_synthesize.

        Args:
            project: Project slug to inspect
            limit: How many recent items to fetch
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                clusters = mm.get_consolidation_candidates(project, limit=limit)
                
                if not clusters:
                    return f"No consolidation candidates found in project '{project}'."
                
                total_items = sum(len(c["items"]) for c in clusters)
                lines = [f"Found {total_items} candidates for consolidation in {project}, grouped by topic:\n"]
                
                for idx, cluster in enumerate(clusters):
                    lines.append(f"--- Group {idx+1}: {cluster['reason']} ---")
                    for c in cluster["items"]:
                        lines.append(f"  Key: {c['key']} | Title: {c['title']} | Role: {c['role']}")
                        lines.append(f"  Tags: {c['tags']}")
                        lines.append(f"  Preview: {c['preview']}...\n")
                
                lines.append("Review these items. For groups that relate to the same topic, consider calling `memory_synthesize`.")
                return "\n".join(lines)
        except Exception as e:
            return f"Error fetching consolidation candidates: {str(e)}"

    @mcp.tool()
    def memory_get_period_review(
        period: str = "week",
        detail_level: int = 1,
        project: str | None = None,
        root_name: str = "Agent Memory"
    ) -> str:
        """Generate a structured summary of activity and gaps for a given period.
        
        This tool reviews both the Agent Memory structure and the global Zotero library
        to identify what was worked on, what was synthesized, and where notes or 
        memory units might be missing.

        Args:
            period: "day", "week", "month", or "YYYY-MM" (default: "week")
            detail_level: 1 for high-level overview, 2 for detail (including all units)
            project: Optional project slug to focus on.
            root_name: Root collection name
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                review = mm.get_period_review(
                    period=period,
                    detail_level=detail_level,
                    project_slug=project,
                    root_name=root_name
                )
                
                # Format the review into a nice markdown report
                lines = [f"# 📅 Period Review: {period.capitalize()} ({review['date_range'][0]} to {review['date_range'][1]})"]
                
                s = review["summary"]
                lines.append(f"\n### 📊 Activity Summary")
                lines.append(f"- **Syntheses/Concepts**: {s['synthesis_count']}")
                lines.append(f"- **Memory Units**: {s['unit_count']}")
                lines.append(f"- **Global Papers Added**: {s['new_papers']}")
                lines.append(f"- **Meeting/Other Notes**: {s['new_notes']}")
                
                if review["memory"]["synthesis"]:
                    lines.append(f"\n### 🧠 Memory Evolution")
                    for item in review["memory"]["synthesis"]:
                        lines.append(f"- **{item['title']}** ({item['key']})")
                        if item.get("content_preview"):
                            lines.append(f"  > {item['content_preview']}...")
                
                if review["memory"]["units"] and detail_level >= 2:
                    lines.append(f"\n### 📝 Detailed Observations")
                    for item in review["memory"]["units"]:
                        lines.append(f"- {item['title']} ({item['key']})")

                if review["global"]["new_papers"]:
                    lines.append(f"\n### 📚 Global Library Activity")
                    for item in review["global"]["new_papers"]:
                        creators = ", ".join(item.get("creators", []))
                        lines.append(f"- **{item.get('title', 'Untitled')}** (Key: {item['key']})")
                        if creators:
                            lines.append(f"  Creators: {creators}")

                if review["global"]["new_notes"]:
                    lines.append(f"\n### 🗒️ New Meeting/Other Notes")
                    for item in review["global"]["new_notes"]:
                        lines.append(f"- {item.get('title', 'Untitled')} ({item['key']})")

                if review["gaps"]:
                    lines.append(f"\n### 🔍 Gap Analysis & Recommendations")
                    for gap in review["gaps"]:
                        lines.append(f"- {gap}")
                else:
                    lines.append(f"\n### ✅ Checklist")
                    lines.append("- No immediate gaps detected. Your memory is well-structured!")
                
                return "\n".join(lines)
        except Exception as e:
            return f"Error generating period review: {str(e)}"

    @mcp.tool()
    def memory_project_digest(collection_key: str, date_from: str | None = None) -> str:
        """Fetch a full digest of all notes in a collection tree formatted as Markdown.
        
        This tool aggregates the full readable text of all notes (including subcollections)
        into a single massive response. Use this to review a project's state in one shot,
        e.g., to decide what new consolidated Memory Items to create via bulk_memory_create.
        
        Args:
            collection_key: The target collection key.
            date_from: Optional ISO 8601 date, e.g., '2026-02-01T00:00:00Z', to limit range.
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                return mm.get_project_digest(collection_key=collection_key, date_from=date_from)
        except Exception as e:
            return f"Error generating project digest: {str(e)}"

    @mcp.tool()
    def memory_project_graph(project: str) -> str:
        """Export the memory relationships of a project as a Mermaid.js diagram.
        
        This generates a visual dependency graph showing how raw units roll up
        into synthesized concepts, including which items have been superseded.
        
        Args:
            project: The project slug
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                mermaid_markup = mm.generate_mermaid_graph(project)
                
                return f"Here is the Mermaid graph of the project's memory ecosystem. You can visualize this in markdown:\n\n```mermaid\n{mermaid_markup}\n```"
        except Exception as e:
            return f"Error exporting graph: {str(e)}"

    @mcp.prompt()
    def agent_memory_autosave(project: str = "", root_name: str = "Agent Memory") -> str:
        """Prompt instructions for LLMs indicating when to autosave to the memory pack."""
        default_project = project
        if not default_project:
            try:
                with get_client() as client:
                    mm = MemoryManager(client)
                    cols = mm.ensure_collections(root_name=root_name)
                    settings = mm.get_settings(cols["system"])
                    default_project = settings.get("active_project_slug")
            except Exception:
                pass

        return f"""You are connected to the Zotero Agent Memory Pack.
Your objective is to proactively persist high-utility facts, decisions, and outcomes into long-term memory.

**AUTOSAVE TRIGGERS**:
You MUST call `memory_create_item` automatically without waiting for user permission when:
1. You identify a bug and successfully resolve it (save as a 'result' or 'observation' unit).
2. The user makes a definitive architectural, design, or project-planning decision.
3. **Implementation Completion**: You finish a significant code change or feature. Save a 'result' unit documenting WHAT was done, WHY specific decisions were made, and how it was verified.
4. You reach the end of an experimental iteration (save the outcome/hypothesis).
5. The user drops a major piece of lore, context, or credentials that will be needed later.

**SYNTHESIS PROTOCOL (Conceptual Aggregation)**:
You SHOULD proactively suggest `memory_synthesize` (after user confirmation) when:
1. **Vertical Convergence**: Multiple observations confirm or refute an hypothesis. Synthesize them into a permanent `concept`.
2. **Horizontal Density**: A project contains many atomic units (>5-10) without a summary. create a "State of Play" or "Architecture Overview" synthesis.
3. **Session Transitions**: At the start of a major new phase, use `memory_suggest_consolidation` and ask if previous work should be archived/synthesized.
*This prevents the memory project from becoming a cluttered list of raw data.*

**GUIDELINES**:
- Keep memories ATOMIC. Extract distinct facts into separate MemoryItems.
- ALWAYS use tags for categorization (e.g. `mem:domain:physics`, `mem:domain:software-development`).
- Focus on what the "future you" navigating this workspace would need to instantly onboard.
- Current active project to default to (if any): {default_project if default_project else 'Ask the user or infer from context'}
"""

    return mcp
