import logging
import os
import subprocess
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.utils import clean_html, generate_friendly_name

logger = logging.getLogger(__name__)

def register_item_tools(mcp: FastMCP):
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
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}")
                        continue

                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Type: {item.get('itemType', 'unknown')}\n- Creators: {creators}\n- Date: {item.get('date', 'Unknown')}"
                    if item.get("url"): item_info += f"\n- URL: {item['url']}"
                    if item.get("tags"): item_info += f"\n- Tags: {', '.join(item['tags'])}"
                    
                    attachments = item.get("attachments", [])
                    if attachments:
                        item_info += "\n- Attachments:"
                        for att in attachments:
                            item_info += f"\n  - {att['title']} ({att['contentType']})"
                            if att.get("path"): item_info += f"\n    Path: `{att['path']}`"
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
                if not items: return "No papers found."
                lines = []
                for item in items:
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}")
                        continue
                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Creators: {creators}"
                    attachments = item.get("attachments", [])
                    if attachments:
                        item_info += "\n- Attachments:"
                        for att in attachments:
                            item_info += f"\n  - {att['title']} ({att['contentType']})"
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
                if not note: return f"Note with key {key} not found."
                return f"## Note {key}\n\n{note.get('note', 'No content.')}"
        except Exception as e:
            return f"Error reading note: {str(e)}"

    @mcp.tool()
    def list_notes(collection_key: str | None = None, parent_item_key: str | None = None) -> str:
        """List notes from Zotero."""
        try:
            with get_client() as client:
                manager = ActiveCollectionManager(client)
                if not collection_key and not parent_item_key:
                    collection_key = manager.get_active_collection_key()
                if not collection_key and not parent_item_key:
                    return "Error: Provide a collection_key, parent_item_key, or set an active collection first."
                notes = client.get_notes(collection_key=collection_key, parent_item_key=parent_item_key)
                if not notes: return "No notes found."
                lines = [f"- {generate_friendly_name(n.get('note', ''))} ({n['key']})" for n in notes]
                return "Available Notes:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing notes: {str(e)}"

    @mcp.tool()
    def list_notes_recursive(collection_key: str, date_from: str | None = None, date_to: str | None = None, include_content: bool = False, query: str | None = None, max_items: int = 200, cursor: int = 0) -> str:
        """Bulk-read notes recursively."""
        import json
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.list_notes_recursive(collection_key=collection_key, date_from=date_from, date_to=date_to, include_content=include_content, query=query, max_items=max_items, cursor=cursor)
                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error in list_notes_recursive: {str(e)}"

    @mcp.tool()
    def create_or_extend_note(content: str, note_key: str | None = None, parent_item_key: str | None = None, collection_key: str | None = None, extend: bool = False, tags: list[str] | None = None, related: list[str] | None = None) -> str:
        """Create or extend a Zotero note."""
        try:
            with get_client() as client:
                if extend and note_key:
                    client.extend_note(note_key, content)
                    if tags or related: client.update_note(note_key, tags=tags or None, related=related or None)
                    return f"Successfully extended note {note_key}."
                if note_key:
                    client.update_note(note_key, content=content, tags=tags if tags else None, related=related if related else None)
                    return f"Successfully updated note {note_key}."
                target_collection = collection_key
                if not target_collection and not parent_item_key:
                    target_collection = ActiveCollectionManager(client).get_active_collection_key()
                if not target_collection and not parent_item_key:
                    return "Error: target not resolved."
                result = client.create_note(content=content, parent_item_key=parent_item_key, collections=[target_collection] if target_collection else None, tags=tags if tags else None)
                new_key = result.get("key", "")
                if related and new_key: client.update_note(new_key, related=related)
                return f"Successfully created note. Key: {new_key}"
        except Exception as e:
            return f"Error in create_or_extend_note: {str(e)}"

    @mcp.tool()
    def get_item_attachments(item_key: str) -> str:
        """Get attachments for an item."""
        try:
            with get_client() as client:
                item = client.get_item(item_key)
                if not item: return f"Item {item_key} not found."
                attachments = item.get("attachments", [])
                if not attachments and item.get("itemType") != "attachment": return "No attachments."
                lines = [f"## Attachments for: {item.get('title', item_key)}"]
                if item.get("itemType") == "attachment": attachments = [item]
                for att in attachments:
                    lines.append(f"- {att['title']} ({att['contentType']}) [Key: {att['key']}]")
                    if att.get("path"): lines.append(f"  Path: `{att['path']}`")
                return "\n".join(lines)
        except Exception as e:
            return f"Error getting attachments: {str(e)}"

    @mcp.tool()
    def get_item_content(key: str) -> str:
        """Get text content of an item (PDF/HTML)."""
        try:
            with get_client() as client:
                data = client.get_item_content(key)
                if not data: return "No content."
                content = data.get("content") or ""
                if filename := data.get("filename"):
                    if filename.lower().endswith((".html", ".htm")):
                        content = clean_html(content, preserve_newlines=True)
                return f"## Content of {data.get('filename', 'Unknown')}\n\n{content}"
        except Exception as e:
            return f"Error getting content: {str(e)}"

    @mcp.tool()
    def open_item(item_key: str) -> str:
        """Open an item in local viewer."""
        try:
            with get_client() as client:
                item = client.get_item(item_key)
                if not item: return "Item not found."
                path = item.get("path")
                if not path:
                    for att in item.get("attachments", []):
                        if att.get("path"):
                            path = att["path"]
                            if att.get("contentType") == "application/pdf": break
                if not path: return "No local path."
                if sys.platform == "darwin": subprocess.call(["open", path])
                elif sys.platform == "win32": os.startfile(path)
                else: subprocess.call(["xdg-open", path])
                return f"Opening: {path}"
        except Exception as e:
            return f"Error opening: {str(e)}"

    @mcp.tool()
    def rename_tag(old_name: str, new_name: str) -> str:
        """Rename a tag."""
        try:
            with get_client() as client:
                client.rename_tag(old_name, new_name)
                return f"Renamed {old_name} to {new_name}."
        except Exception as e:
            return f"Error renaming tag: {str(e)}"

    @mcp.tool()
    def memory_consolidate_tags(old_tags: list[str], new_tag: str) -> str:
        """Consolidate multiple tags into a single new tag library-wide.
        
        This is useful for ontological refactoring, e.g., merging variants of a tag.
        If the new_tag already exists, Zotero will merge the tags.
        """
        try:
            with get_client() as client:
                for tag in old_tags:
                    client.rename_tag(tag, new_tag)
                return f"Successfully consolidated {len(old_tags)} tags into '{new_tag}'."
        except Exception as e:
            return f"Error consolidating tags: {str(e)}"

    @mcp.tool()
    def memory_move_item(item_key: str, collection_key: str) -> str:
        """Move an item to a specific collection (replacing current collections)."""
        try:
            with get_client() as client:
                client.update_item(item_key, collections=[collection_key])
                return f"Successfully moved item {item_key} to collection {collection_key}."
        except Exception as e:
            return f"Error moving item: {str(e)}"

    @mcp.tool()
    def memory_lint_note(key: str) -> str:
        """Check a note for standard project formatting and issues."""
        try:
            with get_client() as client:
                note = client.get_note(key)
                if not note: return "Note not found."
                content = note.get("note", "")
                
                issues = []
                if not content.strip(): issues.append("Note is empty.")
                if "<pre>" not in content and "[MEM]" in note.get("title", ""):
                    issues.append("Memory item note missing metadata block (<pre> tag).")
                if "</h1>" in content or "<h1>" in content:
                    issues.append("Avoid using <h1> in notes; use ## (h2) for main sections.")
                
                # Check for unclosed tags/markdown if possible
                if content.count("```") % 2 != 0:
                    issues.append("Unclosed markdown code block (```).")
                
                if not issues:
                    return f"Note {key} looks good!"
                return f"Issues found in Note {key}:\n- " + "\n- ".join(issues)
        except Exception as e:
            return f"Error linting note: {str(e)}"

    @mcp.tool()
    def list_tags() -> str:
        """List all tags."""
        try:
            with get_client() as client:
                tags = client.get_tags()
                return "Available Tags:\n- " + "\n- ".join(tags) if tags else "No tags."
        except Exception as e:
            return f"Error listing tags: {str(e)}"
