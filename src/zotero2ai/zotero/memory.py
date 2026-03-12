"""Memory manager for Zotero storage, implementing Zotero Agent Memory Pack v0.1."""

import logging
import re
import collections
from typing import Any, cast

import yaml  # type: ignore[import-untyped]
from datetime import datetime, timedelta

from zotero2ai.zotero.models import MemoryItem
from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.utils import normalize_tags

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages Zotero Agent Memory Pack v0.1 items."""

    def __init__(self, client: PluginClient, store: Any = None):
        self.client = client
        if store is None:
            try:
                from zotero2ai.config import resolve_sidecar_db_path
                from zotero2ai.memory_index.store import MemoryIndexStore
                self.store = MemoryIndexStore(resolve_sidecar_db_path())
            except Exception as e:
                logger.warning(f"Could not initialize sidecar store: {e}")
                self.store = None
        else:
            self.store = store

    def _sync_to_sidecar(self, item_key: str):
        """Update sidecar for a specific item."""
        if not self.store: return
        try:
            raw_item = self.client.get_item(item_key)
            if not raw_item: return
            if isinstance(raw_item, list): raw_item = raw_item[0]
            
            notes = self.client.get_notes(parent_item_key=item_key)
            note_content = notes[0]["note"] if notes else ""
            
            mem_item = MemoryItem.from_zotero_data(raw_item, note_content)
            if not mem_item: return

            if mem_item.mem_class == "concept":
                from zotero2ai.memory_index.types import CatalogConcept
                cat_id = mem_item.catalog_concept_id or self.store.make_catalog_concept_id(mem_item.title)
                self.store.add_concept(CatalogConcept(
                    catalog_concept_id=cat_id,
                    title=mem_item.title,
                    concept_label=self.store.extract_concept_label(mem_item.title),
                    summary=mem_item.summary,
                    state="stable" if mem_item.state == "active" else "archived"
                ))
                self.store.register_usage(mem_item.project, cat_id, item_key)
            elif mem_item.mem_class == "unit" and mem_item.state == "active":
                self._refresh_project_candidates(mem_item.project)
        except Exception as e:
            logger.warning(f"Failed to sync item {item_key} to sidecar: {e}")

    def _ensure_concept_identity(self, item: MemoryItem):
        if not self.store or item.mem_class != "concept" or item.catalog_concept_id:
            return
        label = self.store.extract_concept_label(item.title)
        item.catalog_concept_id = self.store.make_catalog_concept_id(label)

    def _normalize_unit_candidate_label(self, title: str) -> str:
        label = self.store.extract_concept_label(title) if self.store else title
        label = re.sub(r"\s+", " ", label).strip()
        return label

    def _refresh_project_candidates(self, project: str, threshold: int = 3):
        if not self.store or not project:
            return

        items = self.recall(project_slug=project, state="active", limit=1000)
        counts: collections.Counter[str] = collections.Counter()
        labels_by_normalized: dict[str, str] = {}
        existing_concepts = self.store.list_project_concept_labels(project)

        for item in items:
            if item.get("mem_class") != "unit":
                continue
            title = item.get("title", "")
            label = self._normalize_unit_candidate_label(title)
            normalized = self.store.normalize_concept_label(label)
            if len(normalized.split()) < 2:
                continue
            if normalized in existing_concepts:
                continue
            counts[normalized] += 1
            labels_by_normalized.setdefault(normalized, label)

        self.store.delete_candidates_for_project(project)
        for normalized, evidence_count in counts.items():
            if evidence_count < threshold:
                continue
            title = labels_by_normalized[normalized]
            candidate_id = self.store.make_candidate_id(project, title)
            self.store.add_candidate(candidate_id, title, evidence_count=evidence_count, project=project)

    def ensure_collections(self, root_name: str = "Agent Memory", project_slug: str | None = None) -> dict[str, str]:
        """Ensure the root, system, and project collections exist.
        
        Returns:
            dict mapping collection paths/slugs to their keys.
        """
        # Resolve root
        root_key = ""
        cols = self.client.get_collections(parent_key="root")
        for c in cols:
            if c["name"] == root_name:
                root_key = c["key"]
                break

        if not root_key:
            resp = self.client.create_collection(name=root_name)
            root_key = resp["key"]

        # Resolve system
        system_key = ""
        cols_sub = self.client.get_collections(parent_key=root_key)
        for c in cols_sub:
            if c["name"] == "_System":
                system_key = c["key"]
                break

        if not system_key:
            resp = self.client.create_collection(name="_System", parent_key=root_key)
            system_key = resp["key"]

        # Resolve project if requested
        project_key = ""
        if project_slug:
            # Map slug to display name: lora-geometry -> LoRA Geometry
            display_name = " ".join(word.capitalize() for word in project_slug.split("-"))
            for c in cols_sub:
                if c["name"] == display_name:
                    project_key = c["key"]
                    break

            if not project_key:
                resp = self.client.create_collection(display_name, parent_key=root_key)
                project_key = resp["key"]

        return {"root": root_key, "system": system_key, "project": project_key}

    def initialize_system(self, root_name: str = "Agent Memory") -> str:
        """Initialize the memory system structure and create a default tag registry."""
        import yaml
        
        cols = self.ensure_collections(root_name=root_name)
        
        # Check if registry exists
        registry_title = "[MEM][system][global] Tag Registry"
        items = self.client.search_items(tag="mem:role:global", collection_key=cols["system"])
        if any(i["title"] == registry_title for i in items):
            return f"Memory system already initialized in '{root_name}'. System key: {cols['system']}"

        # Create initial registry
        default_registry = {
            "allowed_tags": {
                "mem:class:": ["unit", "concept", "project", "system"],
                "mem:project:": [],
                "mem:role:": ["question", "observation", "hypothesis", "result", "synthesis"],
                "mem:state:": ["active", "superseded", "archived"],
                "mem:source:": ["agent", "user", "paper", "conversation", "manual"],
                "mem:domain:": [],
            }
        }
        yaml_content = yaml.dump(default_registry, default_flow_style=False)
        note_html = f"<pre>{yaml_content}</pre><hr/><p>Global Tag Registry for Zotero Agent Memory Pack.</p>"

        resp = self.client.create_item(
            item_type="report",
            title=registry_title,
            tags=["mem:class:system", "mem:role:global"],
            collections=[cols["system"]],
            note=note_html
        )

        return f"Successfully initialized memory system in '{root_name}'.\nRoot key: {cols['root']}\nSystem key: {cols['system']}\nRegistry item key: {resp.get('key')}"

    def get_registry(self, system_collection_key: str) -> dict[str, Any]:
        """Load the Tag Registry from the _System collection."""
        registry_title = "[MEM][system][global] Tag Registry"

        # Find the item by role tag (more reliable than fuzzy title search in Zotero)
        items = self.client.search_items(tag="mem:role:global", collection_key=system_collection_key)
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
                    allowed_values = allowed[axis]
                    # If empty list, we allow any value (free-form axis)
                    if allowed_values and value not in allowed_values:
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
        self._ensure_concept_identity(item)

        tags = item.generate_tags()
        note_html = item.to_note_html()

        resp = self.client.create_item(
            item_type="report",  # Phase 1 Standard
            title=item.title,
            tags=tags,
            collections=[collection_key],
            note=note_html,
            fields={"abstractNote": item.summary} if item.summary else None,
        )
        if "key" in resp:
            self._sync_to_sidecar(resp["key"])
        return resp

    @staticmethod
    def _dedupe_strings(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _collect_operational_refs(self, memories: list[dict[str, Any]]) -> dict[str, list[str]]:
        repos: list[str] = []
        ticket_ids: list[str] = []
        architecture_refs: list[str] = []
        implementation_instructions: list[str] = []
        for mem in memories:
            repos.extend([str(v) for v in mem.get("repos", []) if isinstance(v, str)])
            ticket_ids.extend([str(v) for v in mem.get("ticket_ids", []) if isinstance(v, str)])
            architecture_refs.extend([str(v) for v in mem.get("architecture_refs", []) if isinstance(v, str)])
            implementation_instructions.extend([str(v) for v in mem.get("implementation_instructions", []) if isinstance(v, str)])
        return {
            "repos": self._dedupe_strings(repos),
            "ticket_ids": self._dedupe_strings(ticket_ids),
            "architecture_refs": self._dedupe_strings(architecture_refs),
            "implementation_instructions": self._dedupe_strings(implementation_instructions),
        }

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
            tags = normalize_tags(item.get("tags", []))
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
        include_full_content: bool = False,
        catalog_concept_id: str | None = None,
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
        if project_slug:
            tag_list.append(f"mem:project:{project_slug}")
        if state:
            tag_list.append(f"mem:state:{state}")
        if tags:
            tag_list.extend(tags)

        # Resolve collection
        collection_key: str | None = None
        if project_slug:
            cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
            collection_key = cols.get("project")
        # If no project_slug, we leave collection_key as None to search the whole library
        # (scoped by tags later). This ensures we find items in any project subcollection.

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
                        if project_slug and mem.project != project_slug:
                            continue
                        entry["mem_id"] = mem.mem_id
                        entry["mem_class"] = mem.mem_class
                        entry["role"] = mem.role
                        entry["state"] = getattr(mem, "state", "active")
                        entry["confidence"] = mem.confidence
                        entry["catalog_concept_id"] = mem.catalog_concept_id
                        entry["repos"] = mem.repos
                        entry["ticket_ids"] = mem.ticket_ids
                        entry["architecture_refs"] = mem.architecture_refs
                        entry["implementation_instructions"] = mem.implementation_instructions
                        entry["content_preview"] = mem.content[:200]
                        if include_full_content:
                            entry["content"] = mem.content
                        
                        # Apply late filter for catalog_concept_id if requested
                        if catalog_concept_id and mem.catalog_concept_id != catalog_concept_id:
                            continue
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
                        if mem.project != project_slug:
                            continue
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
                    self.client.update_note(note_key, tags=new_tags)
                
                self._sync_to_sidecar(old_key)
                return {"old_key": old_key, "new_key": new_key, "status": "superseded"}
            except Exception as e:
                logger.error(f"Error retagging old item {old_key}: {str(e)}")
                return {"old_key": old_key, "new_key": new_key, "status": "new_created_link_failed"}
        return {"old_key": old_key, "new_key": new_key, "status": "new_created_no_old_item"}

    def archive_item(self, key: str) -> dict[str, Any]:
        """Move a memory item from active/superseded to archived state.

        1. Load current tags.
        2. Remove existing state tags (active/superseded).
        3. Add mem:state:archived.
        4. Update Zotero item.

        Args:
            key: Zotero item key.

        Returns:
            Dict with key and status.
        """
        item = self.client.get_item(key)
        if not item:
            return {"key": key, "status": "error", "message": "not found"}

        if isinstance(item, list):
            item = item[0] if item else {}
        
        old_tags = item.get("tags", [])
        new_tags = []
        for t in old_tags:
            tag_str = t.get("tag", "") if isinstance(t, dict) else str(t)
            if tag_str in ["mem:state:active", "mem:state:superseded", "mem:state:archived"]:
                continue
            if tag_str:
                new_tags.append(tag_str)
        
        new_tags.append("mem:state:archived")

        try:
            self.client.update_item(key=key, tags=new_tags)
            self._sync_to_sidecar(key)
            return {"key": key, "status": "archived"}
        except Exception as e:
            logger.error(f"Error archiving item {key}: {str(e)}")
            return {"key": key, "status": "error", "message": str(e)}

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
                        self._sync_to_sidecar(skey)
                        retagged.append(skey)
                    except Exception as e:
                        logger.warning(f"Failed to supersede source {skey}: {e}")

        return {
            "synthesis_key": new_key,
            "sources_linked": len(source_keys),
            "sources_superseded": len(retagged)
        }

    def get_consolidation_candidates(self, project: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return merge/consolidation suggestions for human review."""
        if self.store:
            try:
                return self.store.get_consolidation_candidates(project=project, limit=limit)
            except Exception as e:
                logger.warning(f"Failed sidecar consolidation lookup for project {project}: {e}")

        # Fallback heuristic for cases where the sidecar is unavailable.
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

    def seed_session(
        self,
        project_slug: str,
        task: str | None = None,
        depth: str = "adaptive",
        root_name: str = "Agent Memory",
    ) -> dict[str, Any]:
        """Build a project-first session bootstrap packet for coding and research work."""
        inspect_data: dict[str, Any] = {}
        try:
            cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
            inspect_data = {
                "project_slug": project_slug,
                "project_key": cols.get("project"),
            }
        except Exception:
            inspect_data = {"project_slug": project_slug}

        project_items = self.recall(
            project_slug=project_slug,
            state="active",
            tags=["mem:class:project"],
            limit=5,
            root_name=root_name,
            include_full_content=True,
        )
        concept_items = self.recall(
            project_slug=project_slug,
            state="active",
            tags=["mem:class:concept"],
            limit=12 if depth != "deep" else 20,
            root_name=root_name,
            include_full_content=True,
        )
        unit_limit = 0
        if depth == "deep":
            unit_limit = 12
        elif depth == "adaptive":
            unit_limit = 6
        unit_items: list[dict[str, Any]] = []
        if unit_limit:
            unit_items = self.recall(
                project_slug=project_slug,
                state="active",
                tags=["mem:class:unit"],
                limit=unit_limit,
                root_name=root_name,
                include_full_content=False,
            )

        consolidation_candidates = []
        try:
            consolidation_candidates = self.get_consolidation_candidates(project_slug, limit=5)
        except Exception:
            consolidation_candidates = []

        refs = self._collect_operational_refs(project_items + concept_items + unit_items)
        project_summary = ""
        if project_items:
            project_summary = project_items[0].get("content", "") or project_items[0].get("content_preview", "")
        elif concept_items:
            project_summary = concept_items[0].get("content", "") or concept_items[0].get("content_preview", "")

        open_questions = [u for u in unit_items if u.get("role") == "question"][:5]
        research_suggestions: list[str] = []
        if not refs["repos"]:
            research_suggestions.append("No relevant repos captured yet; inspect project-level implementation context.")
        if not refs["architecture_refs"]:
            research_suggestions.append("No architecture references captured yet; consider retrieving system design context.")
        if consolidation_candidates:
            research_suggestions.append("Concept consolidation candidates exist; inspect before creating new concepts.")

        return {
            "project": project_slug,
            "task": task,
            "depth": depth,
            "project_brief": {
                "summary": project_summary,
                "repos": refs["repos"],
                "ticket_ids": refs["ticket_ids"],
                "architecture_refs": refs["architecture_refs"],
                "implementation_instructions": refs["implementation_instructions"],
                "risks": [],
                "next_reads": [item.get("title", "") for item in concept_items[:3] if item.get("title")],
            },
            "relevant_concepts": concept_items,
            "relevant_units": unit_items,
            "open_questions": open_questions,
            "consolidation_candidates": consolidation_candidates,
            "research_suggestions": research_suggestions,
            "inspect": inspect_data,
        }

    def commit_episode(
        self,
        project_slug: str,
        task_summary: str,
        learnings: list[str],
        decisions: list[str] | None = None,
        changes_made: list[str] | None = None,
        open_questions: list[str] | None = None,
        repos: list[str] | None = None,
        ticket_ids: list[str] | None = None,
        architecture_refs: list[str] | None = None,
        implementation_instructions: list[str] | None = None,
        root_name: str = "Agent Memory",
    ) -> dict[str, Any]:
        """Persist the outcome of a coding or research episode as atomic unit memories."""
        cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
        created: list[dict[str, str]] = []

        shared_kwargs = {
            "project": project_slug,
            "source": "agent",
            "confidence": "high",
            "repos": repos or [],
            "ticket_ids": ticket_ids or [],
            "architecture_refs": architecture_refs or [],
            "implementation_instructions": implementation_instructions or [],
        }

        items_to_write: list[MemoryItem] = []
        for text in learnings:
            items_to_write.append(MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project_slug),
                mem_class="unit",
                role="result",
                title=f"[MEM][unit][{project_slug}] Learning: {text[:60]}",
                content=f"Episode: {task_summary}\n\nLearning:\n{text}",
                **shared_kwargs,
            ))
        for text in decisions or []:
            items_to_write.append(MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project_slug),
                mem_class="unit",
                role="observation",
                title=f"[MEM][unit][{project_slug}] Decision: {text[:60]}",
                content=f"Episode: {task_summary}\n\nDecision:\n{text}",
                **shared_kwargs,
            ))
        for text in changes_made or []:
            items_to_write.append(MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project_slug),
                mem_class="unit",
                role="result",
                title=f"[MEM][unit][{project_slug}] Change: {text[:60]}",
                content=f"Episode: {task_summary}\n\nChange:\n{text}",
                **shared_kwargs,
            ))
        for text in open_questions or []:
            items_to_write.append(MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project_slug),
                mem_class="unit",
                role="question",
                title=f"[MEM][unit][{project_slug}] Open Question: {text[:60]}",
                content=f"Episode: {task_summary}\n\nOpen question:\n{text}",
                **shared_kwargs,
            ))

        for item in items_to_write:
            resp = self.create_memory_item(item, cols["project"])
            created.append({"key": str(resp.get("key", "")), "title": item.title, "role": item.role})

        synthesis_hint = self.check_synthesis_needed(project_slug)
        consolidation_candidates = []
        try:
            consolidation_candidates = self.get_consolidation_candidates(project_slug, limit=5)
        except Exception:
            consolidation_candidates = []

        return {
            "project": project_slug,
            "task_summary": task_summary,
            "created_units": created,
            "synthesis_hint": synthesis_hint,
            "consolidation_candidates": consolidation_candidates,
        }

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
    def get_settings(self, system_collection_key: str) -> dict[str, Any]:
        """Load persistent settings from the _System collection."""
        settings_title = "[MEM][system][global] Settings"
        
        # Search for the settings item
        items = self.client.search_items(tag="mem:role:global", collection_key=system_collection_key)
        settings_item = next((i for i in items if i["title"] == settings_title), None)
        
        if not settings_item:
            return {}
            
        # Get the child note
        notes = self.client.get_notes(parent_item_key=settings_item["key"])
        if not notes:
            return {}
            
        # Extract YAML from <pre> or raw text
        note_content = notes[0]["note"]
        import re
        pre_match = re.search(r"<pre>(.*?)</pre>", note_content, re.DOTALL)
        yaml_content = pre_match.group(1) if pre_match else note_content
        
        try:
            settings = yaml.safe_load(yaml_content)
            return cast(dict[str, Any], settings) if settings else {}
        except Exception:
            return {}

    def update_settings(self, system_collection_key: str, settings: dict[str, Any]) -> None:
        """Update or create persistent settings in the _System collection."""
        settings_title = "[MEM][system][global] Settings"
        
        # 1. Check if it exists
        items = self.client.search_items(tag="mem:role:global", collection_key=system_collection_key)
        settings_item = next((i for i in items if i["title"] == settings_title), None)
        
        yaml_content = yaml.dump(settings, default_flow_style=False)
        note_html = f"<pre>{yaml_content}</pre><hr/><p>Persistent Settings for Zotero Agent Memory Pack.</p>"
        
        if settings_item:
            # Update child note
            notes = self.client.get_notes(parent_item_key=settings_item["key"])
            if notes:
                self.client.update_note(notes[0]["key"], note_html)
            else:
                self.client.create_note(note_html, parent_item_key=settings_item["key"])
        else:
            # Create new item with note
            self.client.create_item(
                item_type="report",
                title=settings_title,
                tags=["mem:class:system", "mem:role:global"],
                collections=[system_collection_key],
            )

    def check_synthesis_needed(self, project: str, unit_limit: int = 7) -> str | None:
        """Check if a project needs a synthesis/aggregation.
        
        Returns a recommendation message if needed, else None.
        """
        try:
            # Fetch recent items for this project
            items = self.recall(project_slug=project, limit=20)
            
            if not items:
                return None
                
            active_units = [i for i in items if i.get("mem_class") == "unit" and i.get("state") == "active"]
            superseded = [i for i in items if i.get("state") == "superseded"]
            
            # 1. Horizontal Density check
            if len(active_units) >= unit_limit:
                return (
                    f"NOTE: Synthesis Recommended! This project now has {len(active_units)} active memory units. "
                    "Consider using `memory_synthesize` to consolidate these into a higher-level concept "
                    "to maintain clarity."
                )
                
            # 2. Superseding Patterns check
            if len(superseded) >= 5 and len(superseded) > len(active_units):
                return (
                    "NOTE: Synthesis Recommended! There is a high count of superseded items in this project. "
                    "Consider consolidating the lineage of changes into a single 'concept' to define the current truth."
                )
        except Exception as e:
            logger.warning(f"Error checking synthesis needs: {e}")
            
        return None

    def list_notes_recursive(
        self,
        collection_key: str,
        date_from: str | None = None,
        date_to: str | None = None,
        include_content: bool = False,
        query: str | None = None,
        max_items: int = 500,
        cursor: int = 0,
    ) -> dict[str, Any]:
        """Traverse a collection tree and return all notes with metadata.

        Traverses the collection subtree rooted at collection_key server-side,
        fetching notes from every subcollection in one call instead of requiring
        the agent to call list_collections + list_notes per subcollection.

        Args:
            collection_key: Root collection key. Use 'root' for the full library.
            date_from: ISO 8601 date string – only notes modified after this date.
            date_to: ISO 8601 date string – only notes modified before this date.
            include_content: If True, fetch and include HTML + plain-text content.
            query: Optional substring filter on note title.
            max_items: Maximum number of notes to return (default: 500).
            cursor: Pagination offset into the flat result set.

        Returns:
            {
              "items": [...],
              "total": N,          # total matching before cursor/max_items slice
              "next_cursor": M | null
            }
        """
        from zotero2ai.zotero.utils import clean_html

        # 1. Build flat list of all (collection_key, collection_path) pairs to visit
        tree = self.client.get_collection_tree(depth=99)
        collection_map: dict[str, str] = {}  # key -> path

        def _collect_subtree(nodes: list[dict[str, Any]], target_found: bool) -> None:
            for node in nodes:
                node_key = node.get("key", "")
                node_path = node.get("path", node.get("name", ""))
                if collection_key == "root" or target_found or node_key == collection_key:
                    collection_map[node_key] = node_path
                    _collect_subtree(node.get("children", []), True)
                else:
                    _collect_subtree(node.get("children", []), False)

        _collect_subtree(tree, collection_key == "root")

        # Fallback: if the key wasn't found in the tree, still try it directly
        if not collection_map and collection_key != "root":
            collection_map[collection_key] = collection_key

        # 2. Fetch notes from each collection
        all_notes: list[dict[str, Any]] = []
        visited_keys: set[str] = set()

        for col_key, col_path in collection_map.items():
            try:
                raw_notes = self.client.get_notes(collection_key=col_key)
            except Exception as e:
                logger.warning(f"Could not fetch notes for collection {col_key}: {e}")
                continue

            for note in raw_notes:
                note_key = note.get("key", "")
                if note_key in visited_keys:
                    continue
                visited_keys.add(note_key)

                # Date filtering (use dateModified if available, else dateAdded)
                note_date = note.get("dateModified") or note.get("dateAdded") or ""
                if date_from and note_date and note_date < date_from:
                    continue
                if date_to and note_date and note_date > date_to:
                    continue

                # Title query filter
                title = note.get("title") or f"Note ({note_key})"
                if query and query.lower() not in title.lower():
                    continue

                entry: dict[str, Any] = {
                    "note_key": note_key,
                    "title": title,
                    "created": note.get("dateAdded", ""),
                    "modified": note.get("dateModified", ""),
                    "collection_key": col_key,
                    "collection_path": col_path,
                    "parent_item_key": note.get("parentItem") or note.get("parentItemKey"),
                }

                if include_content:
                    try:
                        full = self.client.get_note(note_key)
                        html = full.get("note", "")
                        entry["content_html"] = html
                        entry["content_plain"] = clean_html(html) if html else ""
                    except Exception as e:
                        logger.warning(f"Could not fetch content for note {note_key}: {e}")
                        entry["content_html"] = ""
                        entry["content_plain"] = ""

                all_notes.append(entry)

        # 3. Sort by modified desc
        all_notes.sort(key=lambda n: n.get("modified") or n.get("created") or "", reverse=True)

        total = len(all_notes)
        page = all_notes[cursor: cursor + max_items]
        next_cursor: int | None = cursor + max_items if cursor + max_items < total else None

        return {
            "items": page,
            "total": total,
            "next_cursor": next_cursor,
        }

    def bulk_create_memory_items(
        self,
        items: list[dict[str, Any]],
        dry_run: bool = False,
        allow_concepts: bool = False,
        root_name: str = "Agent Memory",
    ) -> dict[str, Any]:
        """Create multiple memory items in a single call.

        Validates all items first (tag normalisation, class gating), then writes
        them in sequence. Supports dry_run mode and per-item idempotency keys.

        Args:
            items: List of item dicts. Required keys: project, mem_class, role,
                   title_label, content. Optional: tags, confidence, source,
                   idempotency_key.
            dry_run: If True, only validate – do not write to Zotero.
            allow_concepts: If True, allow mem_class in ['concept','synthesis'].
                            Default is False (only 'unit' class without explicit opt-in).
            root_name: Root collection name for Agent Memory.

        Returns:
            {
              "dry_run": bool,
              "total": int,
              "created": int,
              "skipped_duplicates": int,
              "errors": [...],
              "items": [{"idempotency_key", "key", "title", "status", "reason?"}]
            }
        """
        # --- Phase 1: Validate all items ---
        registry: dict[str, Any] | None = None
        col_cache: dict[str, str] = {}  # project_slug -> project collection key
        system_key: str | None = None

        # Load registry once
        try:
            bootstrap = self.ensure_collections(root_name=root_name)
            system_key = bootstrap.get("system")
            if system_key:
                registry = self.get_registry(system_key)
        except Exception as e:
            return {
                "dry_run": dry_run,
                "total": len(items),
                "created": 0,
                "skipped_duplicates": 0,
                "errors": [f"Cannot load registry: {e}"],
                "items": [],
            }

        validation_errors: list[str] = []
        validated: list[dict[str, Any]] = []  # items that pass validation

        CONCEPT_CLASSES = {"concept", "synthesis"}

        for idx, raw in enumerate(items):
            label = raw.get("idempotency_key") or raw.get("title_label") or f"item[{idx}]"

            # Required field check
            for req in ("project", "mem_class", "role", "title_label", "content"):
                if not raw.get(req):
                    validation_errors.append(f"{label}: missing required field '{req}'")
                    validated.append({"idempotency_key": label, "status": "error", "reason": f"missing '{req}'"})
                    break
            else:
                mem_class = raw["mem_class"]
                role = raw["role"]
                project = raw["project"]

                # Concept gating
                if not allow_concepts and mem_class in CONCEPT_CLASSES:
                    validation_errors.append(
                        f"{label}: mem_class='{mem_class}' requires allow_concepts=True. "
                        "Use dry_run=True first, then re-submit with allow_concepts=True after user approval."
                    )
                    validated.append({"idempotency_key": label, "status": "error", "reason": "concept class not allowed"})
                    continue

                # Tag validation
                extra_tags = raw.get("tags") or []
                base_tags = [f"mem:class:{mem_class}", f"mem:role:{role}", f"mem:project:{project}"]
                all_tags = base_tags + extra_tags

                tag_error: str | None = None
                if registry:
                    try:
                        self.validate_tags(all_tags, registry)
                    except ValueError as ve:
                        tag_error = str(ve)

                if tag_error:
                    validation_errors.append(f"{label}: {tag_error}")
                    validated.append({"idempotency_key": label, "status": "error", "reason": tag_error})
                    continue

                validated.append({"_raw": raw, "idempotency_key": label, "status": "pending"})

        if dry_run:
            pending = [v for v in validated if v.get("status") == "pending"]
            errors = [v for v in validated if v.get("status") == "error"]
            return {
                "dry_run": True,
                "total": len(items),
                "would_create": len(pending),
                "validation_errors": len(errors),
                "errors": validation_errors,
                "items": [{k: v for k, v in item.items() if k != "_raw"} for item in validated],
            }

        # --- Phase 2: Write valid items ---
        created_count = 0
        skipped_count = 0
        write_errors: list[str] = []
        result_items: list[dict[str, Any]] = []
        affected_projects: set[str] = set()

        for item_meta in validated:
            if item_meta.get("status") != "pending":
                result_items.append({k: v for k, v in item_meta.items() if k != "_raw"})
                continue

            raw = item_meta["_raw"]
            label = item_meta["idempotency_key"]
            project = raw["project"]
            idempotency_key = raw.get("idempotency_key")

            # Idempotency check: search by key in note content
            if idempotency_key:
                try:
                    existing = self.client.search_items(query=idempotency_key, limit=3)
                    if any(idempotency_key in (i.get("title", "") + i.get("extra", "")) for i in existing):
                        skipped_count += 1
                        result_items.append({"idempotency_key": label, "status": "skipped", "reason": "duplicate"})
                        continue
                except Exception:
                    pass  # If check fails, proceed with creation

            # Resolve collection (cached per project)
            if project not in col_cache:
                try:
                    cols = self.ensure_collections(root_name=root_name, project_slug=project)
                    col_cache[project] = cols["project"]
                except Exception as e:
                    write_errors.append(f"{label}: could not resolve collection for project '{project}': {e}")
                    result_items.append({"idempotency_key": label, "status": "error", "reason": str(e)})
                    continue

            project_col_key = col_cache[project]

            # Build MemoryItem
            try:
                mem_id = MemoryItem.generate_mem_id(project)
                full_title = f"[MEM][{raw['mem_class']}][{project}] {raw['title_label']}"

                # Embed idempotency_key in content for future deduplication
                content = raw["content"]
                if idempotency_key:
                    content = f"{content}\n\n<!-- idempotency: {idempotency_key} -->"

                m_item = MemoryItem(
                    mem_id=mem_id,
                    mem_class=raw["mem_class"],
                    role=raw["role"],
                    project=project,
                    title=full_title,
                    content=content,
                    source=raw.get("source", "agent"),
                    confidence=raw.get("confidence", "medium"),
                    tags=raw.get("tags") or [],
                )

                resp = self.create_memory_item(m_item, project_col_key)
                created_count += 1
                affected_projects.add(project)
                result_items.append({
                    "idempotency_key": label,
                    "key": resp.get("key", ""),
                    "title": full_title,
                    "status": "created",
                })
            except Exception as e:
                write_errors.append(f"{label}: {e}")
                result_items.append({"idempotency_key": label, "status": "error", "reason": str(e)})

        # Post-batch synthesis check for affected projects
        synthesis_hints: list[str] = []
        for proj in affected_projects:
            try:
                hint = self.check_synthesis_needed(proj)
                if hint:
                    synthesis_hints.append(hint)
            except Exception:
                pass

        return {
            "dry_run": False,
            "total": len(items),
            "created": created_count,
            "skipped_duplicates": skipped_count,
            "errors": validation_errors + write_errors,
            "items": result_items,
            "synthesis_hints": synthesis_hints,
        }

    def get_project_digest(self, collection_key: str, date_from: str | None = None) -> str:
        """Aggregates all recent notes in a collection into a single Markdown document.
        
        This is designed to be fed directly to an agent to generate new Memory Items
        and decision logs via `memory_create_item` and follow-up synthesis tools.
        """
        # Fetch all notes including content, passing cursor=0 and a large limit
        # In a real environment we might want to paginate, but for a digest we need everything up to a limit
        res = self.list_notes_recursive(
            collection_key=collection_key,
            date_from=date_from,
            include_content=True,
            max_items=200
        )
        items = res.get("items", [])
        
        if not items:
            return f"No notes found in collection '{collection_key}' since {date_from or 'the beginning'}."
            
        lines = [
            f"# Project Digest: Collection {collection_key}",
            f"**Total Notes:** {len(items)}",
            f"**Since:** {date_from or 'Anytime'}",
            "\n---\n"
        ]
        
        for idx, item in enumerate(items, 1):
            lines.append(f"## [{idx}] {item.get('title', 'Untitled')} (Key: {item.get('note_key')})")
            lines.append(f"**Modified:** {item.get('modified')} | **Path:** {item.get('collection_path')}\n")
            
            content = item.get("content_plain", "").strip()
            if not content:
                content = "*(No text content)*"
                
            lines.append(content)
            lines.append("\n---\n")
            
        return "\n".join(lines)

    def get_period_review(
        self,
        period: str = "week",
        detail_level: int = 1,
        project_slug: str | None = None,
        root_name: str = "Agent Memory"
    ) -> dict[str, Any]:
        """Aggregate activity and perform gap analysis for a specific time period."""
        now = datetime.utcnow()
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:
            # Try to parse YYYY-MM
            try:
                start_date = datetime.strptime(period, "%Y-%m")
            except ValueError:
                start_date = now - timedelta(days=7)

        date_from = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # 1. Fetch Agent Memory Activity
        memory_items = self.recall(
            project_slug=project_slug,
            date_from=date_from,
            state="",  # All states
            limit=200,
            root_name=root_name
        )
        
        # 2. Fetch Global Zotero Activity (Recently added/modified papers and notes)
        global_items = self.client.search_items(
            date_from=date_from,
            limit=100,
            sort_by="dateModified"
        )
        
        # Filter global items: exclude those already in Agent Memory as reports
        mem_keys = {item["key"] for item in memory_items}
        other_items = [i for i in global_items if i["key"] not in mem_keys and i.get("itemType") != "report"]

        # 3. Categorize Memory Items
        synthesis = [i for i in memory_items if i.get("role") == "synthesis" or i.get("mem_class") == "concept"]
        units = [i for i in memory_items if i.get("mem_class") == "unit"]
        
        # 4. Group Global Items by Type and Collection
        notes = [i for i in global_items if (i.get("itemType") == "note" or not i.get("title")) and i["key"] not in mem_keys]
        # Ensure notes from search have a title for display
        for n in notes:
            if not n.get("title") and n.get("key"):
                # We'll rely on the agent to fetch the note content if needed, 
                # but let's try to provide a generic title
                n["title"] = f"Note ({n['key']})"

        papers = [i for i in other_items if i.get("itemType") not in ("note", "attachment") and i.get("title")]
        
        # Basic Gap Analysis
        gaps = []
        # - Search for items with no related memory units? (Simplified: check for papers in project collections)
        if project_slug:
            cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
            proj_key = cols.get("project")
            proj_papers = [p for p in papers if proj_key in p.get("collections", [])]
            for p in proj_papers:
                # Check if any memory unit refers to this paper
                ref_found = any(p["key"] in (i.get("related") or []) for i in memory_items)
                if not ref_found:
                    gaps.append(f"Dangling Paper: '{p['title']}' was added to {project_slug} but has no observations.")
        
        # - Synthesis recommendations
        if project_slug:
            rec = self.check_synthesis_needed(project_slug)
            if rec:
                gaps.append(rec)

        return {
            "period": period,
            "date_range": [date_from, now.strftime("%Y-%m-%dT%H:%M:%SZ")],
            "summary": {
                "synthesis_count": len(synthesis),
                "unit_count": len(units),
                "new_papers": len(papers),
                "new_notes": len(notes)
            },
            "memory": {
                "synthesis": synthesis if detail_level >= 1 else synthesis[:5],
                "units": units if detail_level >= 2 else []
            },
            "global": {
                "new_papers": papers[:10],
                "new_notes": notes[:10]
            },
            "gaps": gaps
        }

    def get_project_context(self, project_slug: str, root_name: str = "Agent Memory") -> str:
        """Fetch a summary of all active memory items (concepts and units) for a project.
        
        Returns a formatted Markdown document for the agent to quickly ingest state.
        Now includes 'guideline' and 'sop' items for default context.
        """
        # Fetch active guidelines/SOPs (default context)
        guidelines = self.recall(
            project_slug=project_slug,
            state="active",
            tags=["mem:role:guideline"],
            limit=10,
            root_name=root_name,
            include_full_content=True
        )
        
        # Also check for global guidelines (generic system context)
        global_guidelines = self.recall(
            project_slug=None, # Cross-project search
            state="active",
            tags=["mem:class:system", "mem:role:guideline"],
            limit=5,
            root_name=root_name,
            include_full_content=True
        )

        # Fetch active concepts (high level)
        concepts = self.recall(
            project_slug=project_slug, 
            state="active", 
            tags=["mem:class:concept"], 
            limit=20, 
            root_name=root_name,
            include_full_content=True
        )
        
        # Fetch active units (raw/recent)
        units = self.recall(
            project_slug=project_slug, 
            state="active", 
            tags=["mem:class:unit"], 
            limit=50, 
            root_name=root_name,
            include_full_content=False # Just previews for units to keep it concise
        )
        
        if not concepts and not units and not guidelines:
            return f"# Project Context: {project_slug}\n\nNo active memory items found. Start by observing or creating memories."
            
        lines = [f"# Project Context: {project_slug}", f"**Generated:** {datetime.now().isoformat()}", "\n---\n"]
        
        if global_guidelines or guidelines:
            lines.append("## 📜 Guidelines & Standard Operating Procedures")
            all_guidelines = (global_guidelines or []) + (guidelines or [])
            for g in all_guidelines:
                lines.append(f"### {g['title']} (Key: {g['key']})")
                lines.append(f"\n{g.get('content', g.get('content_preview', ''))}")
                lines.append("\n")
            lines.append("\n---\n")

        if concepts:
            lines.append("## 🧠 High-Level Concepts & Strategic State")
            for c in concepts:
                lines.append(f"### {c['title']} (Key: {c['key']})")
                lines.append(f"**Confidence:** {c.get('confidence', 'medium')} | **Role:** {c.get('role', 'synthesis')}")
                lines.append(f"\n{c.get('content', c.get('content_preview', ''))}")
                lines.append("\n")
            lines.append("\n---\n")
            
        if units:
            lines.append("## 📝 Active Observations & Findings")
            for u in units:
                # Skip guideline items if they were already listed
                if "guideline" in u.get('tags', []):
                    continue
                role_label = u.get('role', 'unit').capitalize()
                lines.append(f"- **{u['title']}** (Key: {u['key']}) [{role_label}]")
                if u.get('content_preview'):
                    lines.append(f"  > {u['content_preview']}...")
            lines.append("\n")
        
        lines.append("---")
        lines.append("*Use memory_recall with specific keys to see full content of individual units.*")
            
        return "\n".join(lines)

    def add_project_todo(self, project_slug: str, content: str, root_name: str = "Agent Memory") -> dict[str, Any]:
        """Add a lightweight TODO/Question to a project's memory."""
        mem_id = MemoryItem.generate_mem_id(project_slug)
        # Limit title length
        title_summary = content[:50].replace("\n", " ")
        if len(content) > 50:
            title_summary += "..."
            
        m_item = MemoryItem(
            mem_id=mem_id,
            mem_class="unit",
            role="question",
            project=project_slug,
            title=f"[MEM][unit][{project_slug}] TODO: {title_summary}",
            content=content,
            source="agent",
            confidence="high",
            tags=["mem:domain:management"]
        )
        
        cols = self.ensure_collections(root_name=root_name, project_slug=project_slug)
        return self.create_memory_item(m_item, cols["project"])
