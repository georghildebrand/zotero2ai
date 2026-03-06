"""Memory manager for Zotero storage, implementing SimpleMem concepts."""

import json
import logging
from typing import Any, List, Optional

from zotero2ai.zotero.models import MemoryEntry
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages long-term memory stored in Zotero."""

    def __init__(self, client: PluginClient):
        self.client = client

    def store_memory_entry(self, entry: MemoryEntry, collection_key: str) -> str:
        """Store a single memory entry as a Zotero note.

        Args:
            entry: The MemoryEntry to store.
            collection_key: The Zotero collection key to store it in.

        Returns:
            The key of the newly created note.
        """
        content = entry.to_html()
        tags = entry.keywords + entry.persons + entry.entities
        if entry.topic:
            tags.append(f"topic:{entry.topic}")
        
        # Add a special tag to identify it as a memory entry
        tags.append("simplemem:memory")

        response = self.client.create_note(
            content=content,
            tags=list(set(tags)), # unique tags
            collections=[collection_key]
        )
        return response.get("key", "unknown")

    def search_memory(self, query: str, collection_key: Optional[str] = None) -> List[MemoryEntry]:
        """Search Zotero for relevant memory entries.

        Args:
            query: The search query (keywords).
            collection_key: Optional collection key to restrict search.

        Returns:
            List of MemoryEntry objects.
        """
        # 1. Search for notes with the special tag and query
        # Since the plugin search_items can filter by tag and collection, we use it.
        items = self.client.search_items(query=query, tag="simplemem:memory", collection_key=collection_key)
        
        entries = []
        for item in items:
            if item.get("itemType") == "note":
                # We need to parse our own HTML format back. 
                # For now, let's just return the content as a restatement 
                # or better, fetch the full note if needed.
                # Actually, the search result has the content in "note" if we're lucky.
                note_key = item["key"]
                note_data = self.client.get_note(note_key)
                content = note_data.get("note", "")
                
                # Robust parsing of our HTML format
                # (This is a bit simplified, but Zotero's notes are standard HTML)
                # Restatement is the first paragraph's text.
                restatement = content # fallback
                import re
                match = re.search(r"<b>Restatement:</b> (.*?)</p>", content)
                if match:
                    restatement = match.group(1)
                
                entry = MemoryEntry(
                    lossless_restatement=restatement,
                    keywords=item.get("tags", []),
                    # Other fields can be parsed too if necessary
                )
                entries.append(entry)
        
        return entries
