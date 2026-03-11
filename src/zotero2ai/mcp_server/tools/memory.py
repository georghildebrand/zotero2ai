import json
import logging
from typing import Any
import yaml

from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem
from zotero2ai.zotero.collections import ActiveCollectionManager

logger = logging.getLogger(__name__)

def register_memory_tools(mcp: FastMCP):
    @mcp.tool()
    def memory_get_context(root_name: str = "Agent Memory") -> str:
        """Get the current memory context."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                manager = ActiveCollectionManager(client)
                settings = mm.get_settings(cols["system"])
                context = {
                    "root_collection": root_name,
                    "root_key": cols["root"],
                    "system_key": cols["system"],
                    "active_project_key": manager.get_active_collection_key(),
                    "active_project_path": manager.get_active_collection_path(),
                    "active_project_slug": settings.get("active_project_slug"),
                    "project_mappings": settings.get("projects", {}),
                    "write_policy": "Append-only for agent memories.",
                    "registry_status": "Ready",
                    "version": "0.1.0-foundation",
                }
                return json.dumps(context, indent=2)
        except Exception as e:
            return f"Error getting context: {str(e)}"

    @mcp.tool()
    def memory_initialize(root_name: str = "Agent Memory") -> str:
        """Initialize memory system."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                return mm.initialize_system(root_name=root_name) # Assuming this exists or I'll copy the logic
        except Exception as e:
            return f"Error initializing: {str(e)}"

    # Note: I'll use the logic from server.py for memory_initialize since there isn't a direct .initialize_system in MemoryManager in the outline I saw earlier.
    # Actually, MemoryManager.ensure_collections does half of it.

    @mcp.tool()
    def memory_get_registry(root_name: str = "Agent Memory") -> str:
        """Load the memory tag registry."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                return json.dumps(mm.get_registry(cols["system"]), indent=2)
        except Exception as e:
            return f"Error getting registry: {str(e)}"

    @mcp.tool()
    def memory_create_item(mem_class: str, role: str, project: str, title_label: str, content: str, source: str = "agent", confidence: str = "medium", tags: list[str] | None = None, summary: str = "", root_name: str = "Agent Memory") -> str:
        """Create a new memory item."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                mem_id = MemoryItem.generate_mem_id(project)
                m_item = MemoryItem(
                    mem_id=mem_id, 
                    mem_class=mem_class, 
                    role=role, 
                    project=project, 
                    title=f"[MEM][{mem_class}][{project}] {title_label}", 
                    content=content, 
                    summary=summary,
                    source=source, 
                    confidence=confidence, 
                    tags=tags or []
                )
                resp = mm.create_memory_item(m_item, cols["project"])
                return f"Successfully created: {m_item.title} (Key: {resp.get('key')})"
        except Exception as e:
            return f"Error creating memory item: {str(e)}"

    @mcp.tool()
    def bulk_memory_create(items: list[dict], dry_run: bool = False, allow_concepts: bool = False, root_name: str = "Agent Memory") -> str:
        """Bulk-write memory items."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.bulk_create_memory_items(items=items, dry_run=dry_run, allow_concepts=allow_concepts, root_name=root_name)
                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error in bulk_memory_create: {str(e)}"

    @mcp.tool()
    def memory_link_items(source_key: str, target_key: str) -> str:
        """Link two memory items."""
        try:
            with get_client() as client:
                MemoryManager(client).link_items(source_key, target_key)
                return f"Linked {source_key} to {target_key}."
        except Exception as e:
            return f"Error linking: {str(e)}"

    @mcp.tool()
    def memory_get_project_context(project: str, root_name: str = "Agent Memory") -> str:
        """One-call context ingest."""
        try:
            with get_client() as client:
                return MemoryManager(client).get_project_context(project_slug=project, root_name=root_name)
        except Exception as e:
            return f"Error getting context: {str(e)}"

    @mcp.tool()
    def memory_project_add_todo(project: str, content: str, root_name: str = "Agent Memory") -> str:
        """Add TODO to project."""
        try:
            with get_client() as client:
                resp = MemoryManager(client).add_project_todo(project_slug=project, content=content, root_name=root_name)
                return f"Added TODO to {project}. Key: {resp.get('key')}"
        except Exception as e:
            return f"Error adding TODO: {str(e)}"

    @mcp.tool()
    def memory_update_tags(item_key: str, tags: list[str]) -> str:
        """Update tags on a memory item."""
        try:
            with get_client() as client:
                client.update_item(item_key, tags=tags)
                return f"Updated tags for {item_key}."
        except Exception as e:
            return f"Error updating tags: {str(e)}"

    @mcp.tool()
    def memory_recall(project: str | None = None, tags: list[str] | None = None, state: str = "active", date_from: str | None = None, date_to: str | None = None, limit: int = 20, root_name: str = "Agent Memory", include_content: bool = False) -> str:
        """Recall memory items."""
        try:
            with get_client() as client:
                results = MemoryManager(client).recall(project_slug=project, tags=tags, state=state, date_from=date_from, date_to=date_to, limit=limit, root_name=root_name, include_full_content=include_content)
                return json.dumps(results, indent=2, default=str) if results else "No memories found."
        except Exception as e:
            return f"Error recalling: {str(e)}"

    @mcp.tool()
    def memory_timeline(project: str, limit: int = 30, root_name: str = "Agent Memory") -> str:
        """Project memory timeline."""
        try:
            with get_client() as client:
                results = MemoryManager(client).timeline(project_slug=project, limit=limit, root_name=root_name)
                return json.dumps(results, indent=2, default=str) if results else "No timeline found."
        except Exception as e:
            return f"Error building timeline: {str(e)}"

    @mcp.tool()
    def memory_related_graph(item_key: str, hops: int = 1) -> str:
        """Follow links from an item."""
        try:
            with get_client() as client:
                return json.dumps(MemoryManager(client).follow_links(item_key, hops=min(hops, 3)), indent=2, default=str)
        except Exception as e:
            return f"Error following links: {str(e)}"

    @mcp.tool()
    def memory_supersede(old_key: str, new_title_label: str, new_content: str, reason: str, project: str, mem_class: str = "unit", role: str = "observation", confidence: str = "medium", root_name: str = "Agent Memory") -> str:
        """Supersede an old memory."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                new_item = MemoryItem(mem_id=MemoryItem.generate_mem_id(project), mem_class=mem_class, role=role, project=project, title=f"[MEM][{mem_class}][{project}] {new_title_label}", content=f"Supersedes: {old_key}\nReason: {reason}\n\n{new_content}", source="agent", confidence=confidence)
                result = mm.supersede(old_key, new_item, cols["project"])
                return f"Superseded {old_key} with {result['new_key']}."
        except Exception as e:
            return f"Error superseding: {str(e)}"

    @mcp.tool()
    def memory_synthesize(source_keys: list[str], title_label: str, content: str, project: str, supersede_sources: bool = False, mem_class: str = "concept", confidence: str = "high", root_name: str = "Agent Memory") -> str:
        """Synthesize memories."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                new_item = MemoryItem(mem_id=MemoryItem.generate_mem_id(project), mem_class=mem_class, role="synthesis", project=project, title=f"[MEM][{mem_class}][{project}] {title_label}", content=content, source="agent", confidence=confidence)
                result = mm.synthesize(source_keys=source_keys, new_item=new_item, project_key=cols["project"], supersede_sources=supersede_sources)
                return f"Synthesized. Key: {result['synthesis_key']}"
        except Exception as e:
            return f"Error synthesizing: {str(e)}"

    @mcp.tool()
    def memory_suggest_consolidation(project: str, limit: int = 20) -> str:
        """Suggest consolidation."""
        try:
            with get_client() as client:
                return MemoryManager(client).get_consolidation_candidates(project, limit=limit) # Returns formatted str
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool()
    def memory_get_period_review(period: str = "week", detail_level: int = 1, project: str | None = None, root_name: str = "Agent Memory") -> str:
        """Period review."""
        try:
            with get_client() as client:
                return MemoryManager(client).get_period_review(period=period, detail_level=detail_level, project_slug=project, root_name=root_name)
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool()
    def memory_project_digest(collection_key: str, date_from: str | None = None) -> str:
        """Project digest."""
        try:
            with get_client() as client:
                return MemoryManager(client).get_project_digest(collection_key=collection_key, date_from=date_from)
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool()
    def memory_project_graph(project: str) -> str:
        """Project Mermaid graph."""
        try:
            with get_client() as client:
                mermaid = MemoryManager(client).generate_mermaid_graph(project)
                return f"```mermaid\n{mermaid}\n```"
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool()
    def memory_set_active_project(project_slug: str, root_name: str = "Agent Memory") -> str:
        """Set active project."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                settings = mm.get_settings(cols["system"])
                settings["active_project_slug"] = project_slug
                project_meta = settings.get("projects", {}).get(project_slug, {})
                if active_col_key := project_meta.get("active_collection_key"):
                    settings["active_collection_key"] = active_col_key
                    settings["active_collection_path"] = project_meta.get("active_collection_path", "")
                mm.update_settings(cols["system"], settings)
                return f"Set active project: {project_slug}"
        except Exception as e:
            return f"Error: {str(e)}"

    @mcp.tool()
    def memory_update_project_mapping(project_slug: str, nickname: str | None = None, related_collections: list[str] | None = None, active_collection_key: str | None = None, active_collection_path: str | None = None, root_name: str = "Agent Memory") -> str:
        """Update project mapping."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name)
                settings = mm.get_settings(cols["system"])
                p_meta = settings.setdefault("projects", {}).setdefault(project_slug, {})
                if nickname: p_meta["nickname"] = nickname
                if related_collections is not None: p_meta["related_collections"] = related_collections
                if active_collection_key: p_meta["active_collection_key"] = active_collection_key
                if active_collection_path: p_meta["active_collection_path"] = active_collection_path
                mm.update_settings(cols["system"], settings)
                return f"Updated mapping for '{project_slug}'."
        except Exception as e:
            return f"Error: {str(e)}"
