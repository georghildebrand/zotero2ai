"""Memory manager for Zotero storage, implementing Zotero Agent Memory Pack v0.1."""

import logging
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from zotero2ai.zotero.models import MemoryItem
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages Zotero Agent Memory Pack v0.1 items."""

    def __init__(self, client: PluginClient):
        self.client = client

    def ensure_collections(self, root_name: str = "Agent Memory", project_slug: str | None = None) -> dict[str, str]:
        """Ensure the root, system, and project collections exist.

        Returns:
            dict mapping collection paths/slugs to their keys.
        """
        keys = {}

        # 1. Ensure Root "Agent Memory"
        root = self.client.search_collections(root_name)
        root_key = None
        if root:
            # Take the best match
            root_key = root[0]["key"]
        else:
            resp = self.client.create_collection(root_name)
            root_key = resp["key"]
        keys["root"] = root_key

        # 2. Ensure "_System"
        system_name = "_System"
        system = self.client.get_collections(parent_key=root_key)
        system_key = next((c["key"] for c in system if c["name"] == system_name), None)
        if not system_key:
            resp = self.client.create_collection(system_name, parent_key=root_key)
            system_key = resp["key"]
        keys["system"] = system_key

        # 3. Ensure Project Collection
        if project_slug:
            # Map slug to display name: lora-geometry -> LoRA Geometry
            display_name = " ".join(word.capitalize() for word in project_slug.split("-"))
            project = next((c["key"] for c in system if c["name"] == display_name), None)
            if not project:
                # Search in all children of root just in case
                children = self.client.get_collections(parent_key=root_key)
                project_key = next((c["key"] for c in children if c["name"] == display_name), None)
                if not project_key:
                    resp = self.client.create_collection(display_name, parent_key=root_key)
                    project_key = resp["key"]
            else:
                project_key = project
            keys["project"] = project_key

        return keys

    def get_registry(self, system_collection_key: str) -> dict[str, Any]:
        """Load the Tag Registry from the _System collection."""
        registry_title = "[MEM][system][global] Tag Registry"

        # Find the item by title
        items = self.client.search_items(query=registry_title, collection_key=system_collection_key)
        registry_item = next((i for i in items if i["title"] == registry_title), None)

        if not registry_item:
            raise RuntimeError(f"Registry item not found: {registry_title}")

        # Get the child note
        notes = self.client.get_notes(parent_item_key=registry_item["key"])
        if not notes:
            raise RuntimeError(f"Registry item '{registry_title}' has no child note.")

        # Extract YAML from <pre> or raw text
        note_content = notes[0]["note"]
        import re

        # Try to find content inside <pre> tags first
        pre_match = re.search(r"<pre>(.*?)</pre>", note_content, re.DOTALL)
        yaml_content = pre_match.group(1) if pre_match else note_content

        try:
            registry = yaml.safe_load(yaml_content)
            if not registry or "allowed_tags" not in registry:
                raise ValueError("Registry missing 'allowed_tags' key.")
            return cast(dict[str, Any], registry)
        except Exception as e:
            raise RuntimeError(f"Failed to parse Tag Registry YAML: {e}") from e

    def validate_tags(self, tags: list[str], registry: dict[str, Any]) -> None:
        """Validate tags against the registry. Rejects if any tag is not allowed."""
        allowed = registry.get("allowed_tags", {})

        for tag in tags:
            # Check if it follows the mem:axis:value pattern
            parts = tag.split(":")
            if len(parts) >= 3 and parts[0] == "mem":
                axis = f"mem:{parts[1]}:"
                value = parts[2]

                # If axis exists in registry, the value must be allowed
                if axis in allowed:
                    if value not in allowed[axis]:
                        raise ValueError(f"Tag '{tag}' value '{value}' not allowed for axis '{axis}'.")
                else:
                    # Registry doesn't know this axis - for Phase 1 we reject unknown axes
                    raise ValueError(f"Tag '{tag}' uses unknown axis '{axis}'.")
            else:
                # Not a memory tag - Phase 1 only allows memory tags from registry
                raise ValueError(f"Tag '{tag}' does not follow the memory tag pattern 'mem:axis:value'.")

    def create_memory_item(self, item: MemoryItem, collection_key: str) -> dict[str, Any]:
        """Create a Zotero memory item with metadata and child note."""
        # Note: Registry validation and collection ensuring should be handled by the caller (MCP tool)
        # to avoid repeated heavy lookups, or we can do it here if needed.

        tags = item.generate_tags()
        note_html = item.to_note_html()

        return self.client.create_item(
            item_type="report",  # Phase 1 Standard
            title=item.title,
            tags=tags,
            collections=[collection_key],
            note=note_html,
        )

    def search_memory(
        self,
        query: str | None = None,
        project: str | None = None,
        mem_class: str | None = None,
        role: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for memory items with filters."""
        # Phase 1 simple filtering
        tag_filter = None
        if project:
            tag_filter = f"mem:project:{project}"
        # If we have multiple tags to filter by, we'd need to use Zotero's complex search
        # For now, we prioritize project tag, then filter others in Python

        results = self.client.search_items(query=query, tag=tag_filter, limit=limit)

        # Filter by class and role in Python if provided
        filtered = []
        for item in results:
            tags = item.get("tags", [])
            if mem_class and f"mem:class:{mem_class}" not in tags:
                continue
            if role and f"mem:role:{role}" not in tags:
                continue
            filtered.append(item)

        return filtered

    def link_items(self, source_key: str, target_key: str) -> dict[str, Any]:
        """Create a Zotero Related link for navigation (navigation only)."""
        return self.client.add_related(source_key, [target_key])

    # ── Phase 2: Retrieval & Recall ─────────────────────────────────

    def recall(
        self,
        project_slug: str | None = None,
        tags: list[str] | None = None,
        state: str = "active",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 20,
        root_name: str = "Agent Memory",
    ) -> list[dict[str, Any]]:
        """Structured recall of memory items with filtering.

        Args:
            project_slug: Project to search in (optional; if None, searches root)
            tags: Additional mem:* tag filters (AND logic)
            state: State filter (default: 'active')
            date_from: ISO date, items after this date
            date_to: ISO date, items before this date
            limit: Max results
            root_name: Name of the root collection

        Returns:
            List of enriched item dicts with parsed metadata.
        """
        # Build tag list
        tag_list: list[str] = []
        if state:
            tag_list.append(f"mem:state:{state}")
        if tags:
            tag_list.extend(tags)

        # Resolve collection
        collection_key: str | None = None
        if project_slug:
            cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
            collection_key = cols.get("project")
        else:
            cols = self.ensure_collections(root_name=root_name)
            collection_key = cols.get("root")

        # Zotero search indices can be milliseconds to seconds delayed behind DB transactions.
        # To ensure the agent can reliably recall items it JUST superseded/synthesized,
        # we bypass the backend `tag` search cache and filter strictly in Python.
        results = self.client.search_items(
            collection_key=collection_key,
            date_from=date_from,
            date_to=date_to,
            limit=limit if not tag_list else 1000,
        )

        filtered_results = []
        for item in results:
            if tag_list:
                item_tags = item.get("tags", [])
                item_tag_strs = [t.get("tag", "") if isinstance(t, dict) else str(t) for t in item_tags]
                
                # AND logic: MUST have all requested tags
                missing = [t for t in tag_list if t not in item_tag_strs]
                if missing:
                    continue
            filtered_results.append(item)
        results = filtered_results[:limit]

        # Enrich each item with parsed metadata from child note
        enriched = []
        for item in results:
            entry: dict[str, Any] = {
                "key": item.get("key", ""),
                "title": item.get("title", ""),
                "tags": item.get("tags", []),
                "dateAdded": item.get("dateAdded", ""),
                "related": item.get("related", []),
            }
            # Try to parse metadata from the first child note
            try:
                notes = self.client.get_notes(parent_item_key=item["key"])
                if notes:
                    mem = MemoryItem.from_zotero_data(item, notes[0].get("note", ""))
                    if mem:
                        entry["mem_id"] = mem.mem_id
                        entry["mem_class"] = mem.mem_class
                        entry["role"] = mem.role
                        entry["state"] = getattr(mem, "state", "active")
                        entry["confidence"] = mem.confidence
                        entry["content_preview"] = mem.content[:200]
            except Exception:
                pass  # Graceful degradation
            enriched.append(entry)

        return enriched

    def timeline(
        self,
        project_slug: str,
        limit: int = 30,
        root_name: str = "Agent Memory",
    ) -> list[dict[str, Any]]:
        """Chronological view of a project's memories.

        Returns items sorted by dateAdded, newest first.
        """
        cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
        collection_key = cols.get("project")

        results = self.client.search_items(
            collection_key=collection_key,
            sort_by="dateAdded",
            limit=limit,
        )

        # Same enrichment as recall
        enriched = []
        for item in results:
            entry: dict[str, Any] = {
                "key": item.get("key", ""),
                "title": item.get("title", ""),
                "tags": item.get("tags", []),
                "dateAdded": item.get("dateAdded", ""),
            }
            try:
                notes = self.client.get_notes(parent_item_key=item["key"])
                if notes:
                    mem = MemoryItem.from_zotero_data(item, notes[0].get("note", ""))
                    if mem:
                        entry["mem_id"] = mem.mem_id
                        entry["mem_class"] = mem.mem_class
                        entry["role"] = mem.role
                        entry["content_preview"] = mem.content[:200]
            except Exception as e:
                logger.warning(f"Error enriching memory item {item.get('key')}: {e}")
            enriched.append(entry)

        return enriched

    def follow_links(
        self,
        item_key: str,
        hops: int = 1,
        _visited: set[str] | None = None,
    ) -> dict[str, Any]:
        """Navigate the Related graph from a starting item.

        Args:
            item_key: Starting item key
            hops: How many hops to follow (default: 1)
            _visited: Internal set to prevent cycles

        Returns:
            Nested dict with root item and its related items.
        """
        if _visited is None:
            _visited = set()
        _visited.add(item_key)

        # Load the item
        item = self.client.get_item(item_key)
        if not item:
            return {"key": item_key, "error": "not found"}

        # item might be wrapped in a list from formatItems
        if isinstance(item, list):
            item = item[0] if item else {}

        node: dict[str, Any] = {
            "key": item.get("key", item_key),
            "title": item.get("title", ""),
            "tags": item.get("tags", []),
        }

        # Extract mem_class from tags
        for t in node.get("tags", []):
            if isinstance(t, str) and t.startswith("mem:class:"):
                node["mem_class"] = t.split(":")[-1]
                break

        # Follow related links if we have hops left
        if hops > 0:
            related_keys = item.get("related", [])
            node["related"] = []
            for rk in related_keys:
                if rk and rk not in _visited:
                    child = self.follow_links(rk, hops=hops - 1, _visited=_visited)
                    node["related"].append(child)

        return node

    def supersede(
        self,
        old_key: str,
        new_item: MemoryItem,
        project_key: str,
    ) -> dict[str, Any]:
        """Replace an old memory with a new one.

        1. Create the new memory item.
        2. Link old → new via Related.
        3. Retag old item: remove mem:state:active, add mem:state:superseded.

        This is the ONLY place the agent modifies existing item tags.

        Args:
            old_key: Key of the item being superseded.
            new_item: The replacement MemoryItem.
            project_key: Collection key for the project.

        Returns:
            Dict with old_key, new_key, and status.
        """
        # 1. Create new item
        new_resp = self.create_memory_item(new_item, project_key)
        new_key = new_resp.get("key", "")

        # 2. Link old → new
        self.link_items(old_key, new_key)

        # 3. Retag the old item
        # Load old item's current tags
        old_item = self.client.get_item(old_key)
        if old_item:
            if isinstance(old_item, list):
                old_item = old_item[0] if old_item else {}
            old_tags = old_item.get("tags", [])
            # Build new tag list
            new_tags = []
            for t in old_tags:
                tag_str = t.get("tag", "") if isinstance(t, dict) else str(t)
                if tag_str == "mem:state:active":
                    continue  # Remove active
                if tag_str:
                    new_tags.append(tag_str)
            new_tags.append("mem:state:superseded")

            # Update the old item's tags directly
            try:
                self.client.update_item(key=old_key, tags=new_tags)
                
                # Also update note tags for fallback
                notes = self.client.get_notes(parent_item_key=old_key)
                if notes:
                    note_key = notes[0]["key"]
                    self.client.update_note(key=note_key, tags=new_tags)
            except Exception as e:
                logger.warning(f"Could not update old item tags: {e}")

        return {
            "old_key": old_key,
            "new_key": new_key,
            "status": "superseded",
        }

    def synthesize(
        self,
        source_keys: list[str],
        new_item: MemoryItem,
        project_key: str,
        supersede_sources: bool = False,
    ) -> dict[str, Any]:
        """Synthesize multiple source items into a new higher-level item.

        Args:
            source_keys: List of item keys to synthesize.
            new_item: The new synthesis MemoryItem.
            project_key: Collection key where the synthesis is stored.
            supersede_sources: Whether to mark sources as superseded.

        Returns:
            Dict with synthesis metadata.
        """
        # 1. Create new item
        new_resp = self.create_memory_item(new_item, project_key)
        new_key = new_resp.get("key", "")

        # 2. Add related links
        if new_key and source_keys:
            try:
                self.client.add_related(new_key, source_keys)
            except Exception as e:
                logger.warning(f"Could not link synthesis {new_key} to sources {source_keys}: {e}")

        # 3. Retag sources if requested
        retagged = []
        if supersede_sources:
            for skey in source_keys:
                old_item = self.client.get_item(skey)
                if old_item:
                    if isinstance(old_item, list):
                        old_item = old_item[0] if old_item else {}
                    old_tags = old_item.get("tags", [])
                    new_tags = []
                    for t in old_tags:
                        tag_str = t if isinstance(t, str) else str(t)
                        if tag_str == "mem:state:active":
                            continue
                        new_tags.append(tag_str)
                    new_tags.append("mem:state:superseded")
                    
                    try:
                        self.client.update_item(key=skey, tags=new_tags)
                        
                        notes = self.client.get_notes(parent_item_key=skey)
                        if notes:
                            self.client.update_note(key=notes[0]["key"], tags=new_tags)
                        retagged.append(skey)
                    except Exception as e:
                        logger.warning(f"Failed to supersede source {skey}: {e}")

        return {
            "synthesis_key": new_key,
            "sources_linked": len(source_keys),
            "sources_superseded": len(retagged)
        }

    def get_consolidation_candidates(self, project: str, limit: int = 20) -> list[dict[str, Any]]:
        """Fetch and cluster recent active raw memory items from a project for potential synthesis.
        """
        items = self.recall(project, tags=["mem:state:active"], limit=limit)
        
        candidates = []
        for item in items:
            cl = item.get("mem_class")
            role = item.get("role")
            if cl == "unit" and role in ["observation", "result", "hypothesis"]:
                candidates.append({
                    "key": item.get("key"),
                    "title": item.get("title"),
                    "role": role,
                    "tags": item.get("tags", []),
                    "preview": item.get("content_preview", "")
                })

        # Simple Clustering Heuristic
        # 1. Group by 'mem:domain:' tags
        clusters: dict[str, list[dict[str, Any]]] = {}
        unclustered = []
        
        for c in candidates:
            domains = [t for t in c["tags"] if isinstance(t, str) and t.startswith("mem:domain:")]
            # Remove the base mem:* tags from titles to not muddy keywords later
            clean_title = c["title"].replace("[MEM]", "").replace(f"[{c['role']}]", "").replace("[unit]", "").replace(f"[{project}]", "")
            c["clean_title"] = clean_title.strip()
            
            if domains:
                for d in domains:
                    group_name = f"Domain focus: {d.split(':', 2)[-1]}"
                    clusters.setdefault(group_name, []).append(c)
            else:
                unclustered.append(c)
                
        # 2. Heuristic word overlap grouping for unclustered items
        stop_words = {"this", "that", "with", "from", "these", "those", "observation", "result", "hypothesis"}
        import collections
        import re
        word_counts: collections.Counter[str] = collections.Counter()
        
        for c in unclustered:
            title_words = [w.lower() for w in re.split(r'\W+', c["clean_title"]) if len(w) > 4 and w.lower() not in stop_words]
            word_counts.update(title_words)
            
        common_themes = [word for word, count in word_counts.items() if count >= 2]
        
        final_clusters: list[dict[str, Any]] = []
        for group_name, grouped_items in clusters.items():
            if len(grouped_items) > 1:
                # Deduplicate by key if the same item had multiple domains
                unique = list({v['key']:v for v in grouped_items}.values())
                final_clusters.append({
                    "reason": group_name,
                    "items": unique
                })
                
        # Cluster unclustered by common themes
        already_clustered_keys = set()
        for theme in common_themes:
            theme_items = []
            for c in unclustered:
                if c["key"] in already_clustered_keys:
                    continue
                if theme in c["clean_title"].lower():
                    theme_items.append(c)
            if len(theme_items) >= 2:
                for c in theme_items:
                    already_clustered_keys.add(c["key"])
                final_clusters.append({
                    "reason": f"Shared Topic: '{theme}'",
                    "items": theme_items
                })
                
        # Any remaining that did not fit a cluster >= 2 items
        clustered_keys = {cast(dict[str, Any], i)["key"] for cl in final_clusters for i in cast(list[Any], cl["items"])}
        leftovers = [c for c in candidates if c["key"] not in clustered_keys]
        if leftovers:
            final_clusters.append({
                "reason": "Unclustered / Independent Observations",
                "items": leftovers
            })
            
        return final_clusters

    def find_duplicates(self, title_query: str, project: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search for potential duplicate memory items in the same project.
        """
        results = self.recall(project, limit=limit)
        
        # Simple string overlap for now
        duplicates = []
        query_words = set(title_query.lower().split())
        
        for item in results:
            item_title = item.get("title", "").lower()
            item_words = set(item_title.split())
            overlap = query_words.intersection(item_words)
            if len(overlap) > 2: # Heuristic
                duplicates.append(item)
                
        return duplicates

    def extract_metadata_from_text(self, text: str) -> dict[str, Any]:
        """Placeholder for logic that helps structure raw text for extraction.
        In the future, this could use local NLP or heuristics to suggest 
        keywords, domains, or cross-references.
        """
        # For now, just return word frequency or simple keyword extraction
        words = text.lower().split()
        # Filter for common long words as keyword candidates
        keywords = list({w for w in words if len(w) > 6})[:10]
        
        return {
            "suggested_keywords": keywords,
            "char_count": len(text),
            "word_count": len(words)
        }

    def generate_mermaid_graph(self, project: str) -> str:
        """Generate a Mermaid.js graph string visualizing a project's memory items and their links."""
        # 1. Fetch active and superseded items
        active = self.recall(project, state="active", limit=200)
        superseded = self.recall(project, state="superseded", limit=200)
        all_items = active + superseded
        
        if not all_items:
            return f"graph TD;\n  node[\"No memory items found in project '{project}'\"];"
            
        lines = ["graph TD;"]
        
        item_keys = {item.get("key") for item in all_items}
        
        for item in all_items:
            key = item.get("key")
            title = item.get("title", "Untitled").replace('"', "'")
            mem_class = item.get("mem_class", "unit")
            state = item.get("state", "active")
            is_superseded = state == "superseded"
            
            # Formatting based on class
            shape_start, shape_end = "[", "]"
            if mem_class in ["concept", "synthesis"]:
                shape_start, shape_end = "[[", "]]"
                
            display_title = f"{title} (Superseded)" if is_superseded else title
            
            # Node definition
            lines.append(f"  {key}{shape_start}\"{display_title}\"{shape_end};")
            
            # Special style for superseded nodes
            if is_superseded:
                lines.append(f"  style {key} stroke-dasharray: 5 5,color:#888,stroke:#888;")
                
            # Links
            related = item.get("related", [])
            for rk in related:
                # Zotero links are bidirectional, but for our DAG conceptually, 
                # a synthesis points *to* its sources. So we draw the arrow 
                # from the source -> new item (rk -> key) to show evolution.
                if rk in item_keys:
                    lines.append(f"  {rk} --> {key};")
                    
        return "\n".join(lines)
