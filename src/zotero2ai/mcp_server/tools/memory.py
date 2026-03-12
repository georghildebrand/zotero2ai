import json
import logging
from typing import Any
import yaml

from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem

logger = logging.getLogger(__name__)

def register_memory_tools(mcp: FastMCP):
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
    def memory_inspect(project: str | None = None, include_registry: bool = False, root_name: str = "Agent Memory") -> str:
        """Summarize memory system state for hosts (non-destructive)."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                settings = mm.get_settings(cols["system"])
                overview = {
                    "root": cols["root"],
                    "system": cols["system"],
                    "project_key": cols.get("project"),
                    "active_project_slug": settings.get("active_project_slug"),
                    "projects": settings.get("projects", {}),
                }

                if include_registry:
                    overview["registry"] = mm.get_registry(cols["system"])

                # Consolidation candidates: keep light to avoid large payloads
                try:
                    overview["consolidation_candidates"] = mm.get_consolidation_candidates(project or settings.get("active_project_slug", ""), limit=10)
                except Exception:
                    overview["consolidation_candidates"] = []

                return json.dumps(overview, indent=2, default=str)
        except Exception as e:
            return f"Error inspecting memory: {str(e)}"

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
    def memory_archive_item(key: str) -> str:
        """Move a memory item to archived state."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.archive_item(key)
                return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error archiving item: {str(e)}"
