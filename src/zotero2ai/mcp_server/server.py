import logging

from mcp.server.fastmcp import FastMCP

from zotero2ai.config import resolve_zotero_bridge_port, resolve_zotero_mcp_token
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryEntry
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
    def list_collections(
        library_id: int | None = None,
        parent_key: str | None = None,
        limit: int = 100,
        start: int = 0
    ) -> str:
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
                response = client.get_collections_paginated(
                    parent_key=parent_key,
                    library_id=library_id,
                    limit=limit,
                    start=start
                )
                
                pagination = response.get('pagination', {})
                if pagination.get('hasMore'):
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
                    if query: msg += f" matching '{query}'"
                    if tag: msg += f" with tag '{tag}'"
                    if collection_key: msg += f" in collection '{collection_key}'"
                    return msg + "."

                lines = []
                for item in items:
                    # Check for error in formatted item
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}\n- Details: {item.get('details', 'No details available')}")
                        continue

                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Type: {item.get('itemType', 'unknown')}\n- Creators: {creators}\n- Date: {item.get('date', 'Unknown')}"
                    
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
        import subprocess
        import sys
        import os
        
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
                    target_path = item.get("path")
                
                # 2. If not, check "attachments" list
                if not target_path:
                    attachments = item.get("attachments", [])
                    # Prefer PDF
                    for att in attachments:
                        if att.get("contentType") == "application/pdf" and att.get("path"):
                            target_path = att.get("path")
                            logging.info(f"Selected PDF attachment: {att.get('title')}")
                            break
                    
                    # Fallback to any file
                    if not target_path and attachments:
                        for att in attachments:
                            if att.get("path"):
                                target_path = att.get("path")
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
                content = data.get("content", "")
                
                return f"## Content of {filename} ({content_type})\n\n{content}"
        except Exception as e:
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
        import os
        from datetime import datetime
        
        try:
            with get_client() as client:
                # 1. Get Items
                # Limit set to 500 to capture most collections
                items = client.get_collection_items(collection_key, limit=500)
                
                if not items:
                     return f"No items found in collection {collection_key}."

                # 2. Prepare Markdown content
                markdown_lines = [
                    f"# Collection Export: {collection_key}", 
                    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                    f"Total Items: {len(items)}",
                    "",
                    "---"
                ]
                
                success_count = 0
                
                for item in items:
                    title = item.get('title', 'Untitled')
                    key = item['key']
                    creators = ", ".join(item.get('creators', []))
                    date = item.get('date', '')
                    item_type = item.get('itemType', 'unknown')
                    url = item.get('url', '')
                    
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
                        if item_type == 'note':
                             note_data = client.get_note(key)
                             content = note_data.get('note', '')
                             filename = generate_friendly_name(content)
                             content_type = "text/html"
                        else:
                             content_data = client.get_item_content(key)
                             content = content_data.get('content')
                             filename = content_data.get('filename', 'Unknown')
                             content_type = content_data.get('contentType', '')

                        if content:
                            # If it's HTML, clean it up for the export (strip styles/scripts/etc)
                            if content_type == 'text/html' or filename.endswith('.html') or filename.endswith('.htm'):
                                content = clean_html(content, preserve_newlines=True)

                            markdown_lines.append(f"\n### Content ({filename})")
                            markdown_lines.append("```text")
                            markdown_lines.append(content)
                            markdown_lines.append("```")
                            success_count += 1
                        else:
                             # Try to check if it has attachments listed in metadata
                             attachments = item.get('attachments', [])
                             if attachments:
                                 att_names = [a.get('title', 'Untitled') for a in attachments]
                                 markdown_lines.append(f"\n*(No text content extracted. Attachments: {', '.join(att_names)})*")
                             else:
                                 markdown_lines.append("\n*(No content available)*")
                    except Exception as e:
                        markdown_lines.append(f"\n*(Error fetching content: {str(e)})*")
                    
                    markdown_lines.append("\n---\n")

                # 3. Determine Output Path
                if not output_path:
                    # Safe filename
                    safe_key = "".join([c for c in collection_key if c.isalnum() or c in ('-','_')])
                    filename = f"zotero_export_{safe_key}.md"
                    output_path = os.path.join(os.path.expanduser("~/Downloads"), filename)
                
                # 4. Write File
                try:
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write("\n".join(markdown_lines))
                    
                    return f"Successfully exported {len(items)} items (content extracted for {success_count}) to:\n{output_path}"
                except Exception as e:
                    return f"Error writing file to {output_path}: {e}"

        except Exception as e:
            return f"Error trying to export collection: {str(e)}"

    @mcp.tool()
    def memory_set_collection(name: str) -> str:
        """Find and select a Zotero collection for memory storage.
        
        Args:
            name: The exact name of the collection (e.g., '04ReadingList/SimpleMem').
        """
        try:
            with get_client() as client:
                # Search for collection by name
                collections = client.search_collections(name)
                # Find exact match
                target = None
                for c in collections:
                    if c["name"] == name or c["fullPath"] == name:
                        target = c
                        break
                
                if not target:
                    # Provide list of close matches
                    matches = "\n".join([f"- {c['fullPath']} (key: {c['key']})" for c in collections])
                    return f"Collection '{name}' not found. Please ensure it exists in Zotero.\nClose matches:\n{matches}"
                
                # We can store the memory collection key using ActiveCollectionManager 
                # or a separate manager. Let's reuse ActiveCollectionManager with a prefix if needed, 
                # but for now let's just use it as the active one.
                manager = ActiveCollectionManager()
                manager.set_active_collection(target["key"], target["fullPath"])
                return f"Successfully set memory storage collection to: {target['fullPath']} (Key: {target['key']})"
        except Exception as e:
            return f"Error setting memory collection: {str(e)}"

    @mcp.tool()
    def memory_add_entry(
        lossless_restatement: str,
        keywords: list[str] | None = None,
        timestamp: str | None = None,
        location: str | None = None,
        persons: list[str] | None = None,
        entities: list[str] | None = None,
        topic: str | None = None,
        collection_key: str | None = None
    ) -> str:
        """Store an atomic memory entry in Zotero (following SimpleMem patterns).
        
        This tool resolves a self-contained fact into a Zotero Note.
        
        Args:
            lossless_restatement: The disambiguated fact (absolute time, no pronouns).
            keywords: List of core keywords.
            timestamp: ISO 8601 timestamp for the event.
            location: The event location.
            persons: List of people involved.
            entities: Companies, products, etc.
            topic: The general topic of the memory.
            collection_key: Optional target collection (defaults to active collection).
        """
        try:
            if not collection_key:
                manager = ActiveCollectionManager()
                collection_key = manager.get_active_collection_key()
            
            if not collection_key:
                return "Error: No memory collection set. Use memory_set_collection first or provide a collection_key."

            entry = MemoryEntry(
                lossless_restatement=lossless_restatement,
                keywords=keywords or [],
                timestamp=timestamp,
                location=location,
                persons=persons or [],
                entities=entities or [],
                topic=topic
            )

            with get_client() as client:
                memory_manager = MemoryManager(client)
                note_key = memory_manager.store_memory_entry(entry, collection_key)
                return f"Successfully stored memory entry in Zotero. Note Key: {note_key}"
        except Exception as e:
            return f"Error storing memory: {str(e)}"

    @mcp.tool()
    def memory_search(query: str, collection_key: str | None = None) -> str:
        """Search for relevant memory entries in Zotero.
        
        Args:
            query: The search terms.
            collection_key: Optional collection key to restrict search.
        """
        try:
            if not collection_key:
                manager = ActiveCollectionManager()
                collection_key = manager.get_active_collection_key()

            with get_client() as client:
                memory_manager = MemoryManager(client)
                entries = memory_manager.search_memory(query, collection_key)
                
                if not entries:
                    return f"No memories matching '{query}' found."
                
                lines = [f"Found {len(entries)} relevant memory entries:"]
                for i, entry in enumerate(entries, 1):
                    lines.append(f"{i}. {entry.lossless_restatement}")
                
                return "\n".join(lines)
        except Exception as e:
            return f"Error searching memory: {str(e)}"

    return mcp
