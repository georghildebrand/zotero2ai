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
    def export_collection_to_markdown(collection_key: str, output_path: str | None = None) -> str:
        """Export all items in a collection (metadata + full text) to a single Markdown file.

        The file is saved to the specified output_path. If not provided, it defaults to
        ~/Downloads/zotero_export_{collection_key}.md.

        This fetches the full text content (from PDFs or snapshots) for each item in the collection.
        Note: This may take a few seconds for large collections (max 500 items).

        Args:
            collection_key: The key of the collection to export.
            output_path: Optional full path for the output file.
        """
        try:
            with get_client() as client:
                # 1. Get Items
                # Limit set to 500 to capture most collections
                items = client.get_collection_items(collection_key, limit=500)

                if not items:
                    return f"No items found in collection {collection_key}."

                # 2. Prepare Markdown content
                from datetime import datetime

                markdown_lines = [f"# Collection Export: {collection_key}", f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"Total Items: {len(items)}", "", "---"]

                success_count = 0

                for item in items:
                    title = item.get("title", "Untitled")
                    key: str = item.get("key") or ""
                    creators = ", ".join(item.get("creators", []))
                    date = item.get("date", "")
                    item_type = item.get("itemType", "unknown")
                    url = item.get("url", "")

                    markdown_lines.append(f"\n## {title}")
                    markdown_lines.append(f"- **Key**: {key}")
                    markdown_lines.append(f"- **Type**: {item_type}")
                    if creators:
                        markdown_lines.append(f"- **Creators**: {creators}")
                    if date:
                        markdown_lines.append(f"- **Date**: {date}")
                    if url:
                        markdown_lines.append(f"- **URL**: {url}")

                    # Fetch content
                    # If it's a note, use the note-specific logic.
                    # If it's a regular item or attachment, use get_item_content.
                    try:
                        if item_type == "note":
                            note_data = client.get_note(key or "")
                            content = note_data.get("note", "")
                            filename = generate_friendly_name(content)
                            content_type = "text/html"
                        else:
                            content_data = client.get_item_content(key or "")
                            content = content_data.get("content")
                            filename = content_data.get("filename", "Unknown")
                            content_type = content_data.get("contentType", "")

                        if content:
                            # If it's HTML, clean it up for the export (strip styles/scripts/etc)
                            if content_type == "text/html" or filename.endswith(".html") or filename.endswith(".htm"):
                                content = clean_html(content, preserve_newlines=True)

                            markdown_lines.append(f"\n### Content ({filename})")
                            markdown_lines.append("```text")
                            markdown_lines.append(content)
                            markdown_lines.append("```")
                            success_count += 1
                        else:
                            # Try to check if it has attachments listed in metadata
                            attachments = item.get("attachments", [])
                            if attachments:
                                att_names = [a.get("title", "Untitled") for a in attachments]
                                markdown_lines.append(f"\n*(No text content extracted. Attachments: {', '.join(att_names)})*")
                            else:
                                markdown_lines.append("\n*(No content available)*")
                    except Exception as e:
                        markdown_lines.append(f"\n*(Error fetching content: {str(e)})*")

                    markdown_lines.append("\n---\n")

                # 3. Determine Output Path
                from pathlib import Path

                final_path: Path
                if not output_path:
                    # Safe filename
                    from pathlib import Path

                    safe_key = "".join([c for c in collection_key if c.isalnum() or c in ("-", "_")])
                    filename = f"zotero_export_{safe_key}.md"
                    final_path = Path.expanduser(Path("~/Downloads") / filename)
                else:
                    final_path = Path(output_path)

                # 4. Write File
                try:
                    # Ensure directory exists
                    final_path.parent.mkdir(parents=True, exist_ok=True)

                    with final_path.open("w", encoding="utf-8") as f:
                        f.write("\n".join(markdown_lines))

                    return f"Successfully exported {len(items)} items (content extracted for {success_count}) to:\n{final_path}"
                except Exception as e:
                    return f"Error writing file to {output_path}: {e}"

        except Exception as e:
            return f"Error trying to export collection: {str(e)}"

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

                manager = ActiveCollectionManager()
                active_col_key = manager.get_active_collection_key()
                active_col_path = manager.get_active_collection_path()

                # Check if registry exists to report status
                registry_title = "[MEM][system][global] Tag Registry"
                items = client.search_items(tag="mem:role:global", collection_key=cols["system"])
                registry_ready = any(i["title"] == registry_title for i in items)

                context = {
                    "root_collection": root_name,
                    "root_key": cols["root"],
                    "system_key": cols["system"],
                    "active_project_key": active_col_key,
                    "active_project_path": active_col_path,
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
    def memory_list_projects(root_name: str = "Agent Memory") -> str:
        """List all active memory projects in Zotero."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                # Projects are subcollections of root, excluding _System
                root_children = client.get_collections(parent_key=cols["root"])
                projects = [c for c in root_children if c["name"] != "_System"]

                if not projects:
                    return "No memory projects found."

                lines = ["Active Memory Projects:"]
                for p in projects:
                    lines.append(f"- {p['name']} (key: {p['key']})")
                return "\n".join(lines)
        except Exception as e:
            return f"Error listing projects: {str(e)}"

    @mcp.tool()
    def memory_search(query: str | None = None, project: str | None = None, mem_class: str | None = None, role: str | None = None, limit: int = 20) -> str:
        """Search for memory items with filters. Returns metadata and content.

        Args:
            query: Optional search text
            project: Optional project slug (e.g., 'lora-geometry')
            mem_class: Optional class (unit, concept, project, system)
            role: Optional role (question, observation, hypothesis, result, synthesis)
            limit: Max results
        """
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                results = mm.search_memory(query, project, mem_class, role, limit)

                if not results:
                    return "No matching memories found."

                lines = [f"Found {len(results)} memory items:"]
                for item in results:
                    lines.append(f"\n### {item['title']} (key: {item['key']})")
                    lines.append(f"- Project: {project or 'unknown'}")
                    # Content is in child notes - we'd need to fetch child note for full content
                    # For search results, we just show the title for now or fetch the first note
                    notes = client.get_notes(parent_item_key=item["key"])
                    if notes:
                        content = clean_html(notes[0].get("note", ""))
                        # Truncate content for search overview
                        summary = (content[:300] + "...") if len(content) > 300 else content
                        lines.append(f"\n{summary}")

                return "\n".join(lines)
        except Exception as e:
            return f"Error searching memory: {str(e)}"

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

        AUTOSAVE DIRECTIVE: You are ENCOURAGED to USE THIS TOOL PROACTIVELY to
        autosave high-utility facts, resolutions, and conclusions as 'unit' items
        without asking the user for permission. If you solve a complex bug or the
        user shares important context, record it immediately.

        IMPORTANT: This tool requires USER CONFIRMATION for 'concept' and 'synthesis' types.
        Ensure tags follow 'mem:domain:<value>' pattern and are in the registry.

        Args:
            mem_class: unit | concept | project | system
            role: question | observation | hypothesis | result | synthesis
            project: lowercase slug (e.g. 'lora-geometry')
            title_label: Short descriptive label for the title
            content: The actual memory content (text)
            source: agent | user | paper | etc.
            confidence: low | medium | high
            tags: Optional domain tags, e.g., ['mem:domain:physics']
            root_name: The root memory collection name
        """
        # Gating check (Policy enforcement)
        if mem_class in ["concept", "synthesis"] or role == "synthesis":
            msg = (
                f"STOP: Creating a '{mem_class}' or '{role}' item requires manual user approval as per policy. "
                f"Please ask the user: 'I would like to create a {mem_class} item for project {project}. Is this okay?'"
            )
            return msg

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
                return f"Successfully created memory item: {full_title} (Key: {resp.get('key')})"
        except Exception as e:
            return f"Error creating memory item: {str(e)}"

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
    def memory_extract_from_text(
        project: str,
        text: str = "",
        source_item_key: str | None = None,
        source_uri: str | None = None,
    ) -> str:
        """Parse raw text (conversations, notes, papers) into structured MemoryItem candidates.

        This tool performs a 'pre-extract' analysis of the text to identify key themes,
        temporal anchors, and potential duplicates. It does NOT create the items;
        the agent should review the results and then call memory_create_item.

        Use this when a long conversation or a new paper contains multiple distinct
        observations or results that should be remembered separately.
        
        If 'text' is not provided and 'source_item_key' is provided, the tool will 
        automatically fetch the full text of the Zotero paper/attachment.

        Args:
            project: The target project slug
            text: The raw text to analyze (optional if source_item_key is given)
            source_item_key: Optional Zotero key of the source document
            source_uri: Optional URL or link to the source
        """
        try:
            with get_client() as client:
                fetch_status = ""
                if not text and source_item_key:
                    data = client.get_item_content(source_item_key)
                    if data and "content" in data:
                        text = data["content"]
                        fetch_status = f"Fetched {len(text)} chars from attachment '{data.get('filename', 'Unknown')}'. "
                
                if not text:
                    return "Error: You must provide either 'text' or a valid 'source_item_key' that contains readable content."

                mm = MemoryManager(client)
                
                # Pre-analysis
                meta = mm.extract_metadata_from_text(text)
                
                # Check for duplicates of the core theme (first 100 chars of text as proxy)
                duplicates = mm.find_duplicates(text[:100], project)
                
                analysis = {
                    "text_stats": meta,
                    "potential_duplicates": [
                        {"key": d["key"], "title": d["title"]} for d in duplicates
                    ],
                    "instruction": (
                        f"{fetch_status}Review the text and the analysis above. "
                        "Identify distinct facts, observations, or hypotheses. "
                        "For each candidate, resolve coreferences (e.g., replace 'it' with specific nouns) "
                        "and anchor relative dates to absolute ISO dates. "
                        "Then, call memory_create_item for each validated memory."
                    )
                }
                
                if source_item_key:
                    analysis["recommended_source_key"] = source_item_key
                
                # If text was auto-fetched, include a chunk of it in the response so the agent can see it
                if fetch_status:
                    # Give the agent the first 15000 chars as a preview to extract from
                    analysis["fetched_text_preview"] = text[:15000] + ("\n...[TRUNCATED]" if len(text) > 15000 else "")
                
                return json.dumps(analysis, indent=2)
        except Exception as e:
            return f"Error extracting from text: {str(e)}"

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
    def agent_memory_autosave(project: str = "") -> str:
        """Prompt instructions for LLMs indicating when to autosave to the memory pack."""
        return f"""You are connected to the Zotero Agent Memory Pack.
Your objective is to proactively persist high-utility facts, decisions, and outcomes into long-term memory.

**AUTOSAVE TRIGGERS**:
You MUST call `memory_create_item` automatically without waiting for user permission when:
1. You identify a bug and successfully resolve it (save as a 'result' or 'observation' unit).
2. The user makes a definitive architectural, design, or project-planning decision.
3. You reach the end of an experimental iteration (save the outcome/hypothesis).
4. The user drops a major piece of lore, context, or credentials that will be needed later.

**GUIDELINES**:
- Keep memories ATOMIC. Extract distinct facts into separate MemoryItems.
- ALWAYS use tags for categorization (e.g. `mem:domain:physics`, `mem:domain:software-development`).
- Focus on what the "future you" navigating this workspace would need to instantly onboard.
- Current active project to default to (if any): {project if project else 'Ask the user or infer from context'}
"""

    return mcp

