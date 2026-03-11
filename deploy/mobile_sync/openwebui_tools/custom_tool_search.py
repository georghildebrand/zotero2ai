"""
This script should be copied and pasted into a new "Tool" inside Open WebUI.
It gives the mobile LLM the ability to search and read exported Zotero data (Read Cache) directly from the mapped Docker volume.

Prerequisites on the laptop:
1. In Zotero, right-click the collection you want to have on your phone (e.g., "Agent Memory").
2. Select "Export Collection..."
3. Choose "Better CSL JSON" or "Better BibTeX JSON", and check "Keep updated".
4. Save the file into your Syncthing sync folder (e.g., Zotero_Read_Cache/memory.json).
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any

# Important: This path must match the volume mapping for the read cache in docker-compose.yml
READ_CACHE_DIR = Path("/app/backend/data/zotero_read_cache")

class Tools:
    def __init__(self):
        pass

    def search_zotero_cache(self, query: str, limit: int = 5) -> str:
        """
        Search your local Zotero Read Cache (exported JSON collections) from your mobile device.
        Use this to look up specific papers, notes, or memories while offline.
        
        :param query: The search term (e.g., title, author, or keyword).
        :param limit: Maximum number of results to return.
        """
        if not READ_CACHE_DIR.exists():
            return f"Error: Read cache directory not found at {READ_CACHE_DIR}. Ensure the Docker volume is properly mapped."

        results = []
        query_lower = query.lower()

        # Iterate over all JSON export files in the cache directory
        for file_path in READ_CACHE_DIR.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # BBT CSL JSON and standard JSON exports usually contain an array of items
                items = data.get("items", []) if isinstance(data, dict) else data
                if not isinstance(items, list):
                    continue

                for item in items:
                    title = item.get("title", "").lower()
                    abstract = item.get("abstract", "").lower()
                    note = item.get("note", "").lower()
                    
                    # Search logic
                    if query_lower in title or query_lower in abstract or query_lower in note:
                        results.append(item)
                        if len(results) >= limit:
                            break
            
            except Exception as e:
                print(f"Failed to read {file_path.name}: {e}")

            if len(results) >= limit:
                break

        if not results:
            return f"No matches found for '{query}' in the Zotero cache."

        # Format results
        output = [f"Found {len(results)} matches for '{query}':\n"]
        for r in results:
            output.append(f"### {r.get('title', 'Untitled')}")
            output.append(f"- Type: {r.get('type', r.get('itemType', 'unknown'))}")
            
            authors = [a.get("family", "") for a in r.get("author", [])]
            if authors:
                output.append(f"- Authors: {', '.join(authors)}")
                
            if "abstract" in r:
                output.append(f"- Abstract: {r['abstract'][:200]}...")
            if "note" in r:
                output.append(f"- Note: {r['note'][:200]}...")
            
            output.append("") # Empty line separator

        return "\n".join(output)
