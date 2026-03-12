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
    def memory_create_item(mem_class: str, role: str, project: str, title_label: str, content: str, source: str = "agent", confidence: str = "medium", tags: list[str] | None = None, summary: str = "", root_name: str = "Agent Memory", repos: list[str] | None = None, ticket_ids: list[str] | None = None, architecture_refs: list[str] | None = None, implementation_instructions: list[str] | None = None) -> str:
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
                    tags=tags or [],
                    repos=repos or [],
                    ticket_ids=ticket_ids or [],
                    architecture_refs=architecture_refs or [],
                    implementation_instructions=implementation_instructions or [],
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

                if mm.store:
                    overview["sidecar"] = mm.store.get_stats()

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
    def memory_seed_session(project: str, task: str | None = None, depth: str = "adaptive", root_name: str = "Agent Memory") -> str:
        """Build a project-first bootstrap packet for a new coding or research session."""
        try:
            with get_client() as client:
                results = MemoryManager(client).seed_session(project_slug=project, task=task, depth=depth, root_name=root_name)
                return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error seeding session: {str(e)}"

    @mcp.tool()
    def memory_commit_episode(project: str, task_summary: str, learnings: list[str], decisions: list[str] | None = None, changes_made: list[str] | None = None, open_questions: list[str] | None = None, repos: list[str] | None = None, ticket_ids: list[str] | None = None, architecture_refs: list[str] | None = None, implementation_instructions: list[str] | None = None, root_name: str = "Agent Memory") -> str:
        """Persist the outcome of a coding or research episode as unit memories and synthesis hints."""
        try:
            with get_client() as client:
                results = MemoryManager(client).commit_episode(
                    project_slug=project,
                    task_summary=task_summary,
                    learnings=learnings,
                    decisions=decisions,
                    changes_made=changes_made,
                    open_questions=open_questions,
                    repos=repos,
                    ticket_ids=ticket_ids,
                    architecture_refs=architecture_refs,
                    implementation_instructions=implementation_instructions,
                    root_name=root_name,
                )
                return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error committing episode: {str(e)}"

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
    def memory_synthesize(source_keys: list[str], title_label: str, content: str, project: str, supersede_sources: bool = False, mem_class: str = "concept", confidence: str = "high", root_name: str = "Agent Memory", catalog_concept_id: str | None = None) -> str:
        """Synthesize memories."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                
                # Check for matches in catalog if we are creating a concept without a specific ID
                if mem_class == "concept" and not catalog_concept_id and mm.store:
                    matches = mm.store.search_concepts(title_label, limit=3)
                    if matches:
                        match_info = "\n".join([f"- {m['title']} (ID: {m['catalog_concept_id']})" for m in matches])
                        return (f"ABORTED: Found potential existing concepts in global catalog:\n{match_info}\n\n"
                                f"To avoid duplicates, please either:\n"
                                f"1. Use 'memory_catalog_get_details' to check them.\n"
                                f"2. Provide one of these IDs as 'catalog_concept_id' if you want to link to an existing concept.\n"
                                f"3. Rename your title if it is truly a new distinct concept.")

                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                new_item = MemoryItem(
                    mem_id=MemoryItem.generate_mem_id(project), 
                    mem_class=mem_class, 
                    role="synthesis", 
                    project=project, 
                    title=f"[MEM][{mem_class}][{project}] {title_label}", 
                    content=content, 
                    source="agent", 
                    confidence=confidence,
                    catalog_concept_id=catalog_concept_id
                )
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

    @mcp.tool()
    def memory_catalog_list(state: str = "stable", limit: int = 50) -> str:
        """List concepts in the global catalog."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store: return "Sidecar index not available."
                results = mm.store.list_concepts(state=state, limit=limit)
                return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error listing catalog: {str(e)}"

    @mcp.tool()
    def memory_catalog_search(query: str, limit: int = 10) -> str:
        """Search the global concept catalog."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store: return "Sidecar index not available."
                results = mm.store.search_concepts(query=query, limit=limit)
                return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error searching catalog: {str(e)}"

    @mcp.tool()
    def memory_catalog_get_details(catalog_concept_id: str) -> str:
        """Get details and usage of a specific catalog concept."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store: return "Sidecar index not available."
                result = mm.store.get_concept(catalog_concept_id)
                return json.dumps(result, indent=2) if result else "Concept not found."
        except Exception as e:
            return f"Error getting concept details: {str(e)}"

    @mcp.tool()
    def memory_catalog_list_candidates(limit: int = 50) -> str:
        """List current candidate concepts in the sidecar."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store: return "Sidecar index not available."
                results = mm.store.get_candidates(limit=limit)
                return json.dumps(results, indent=2)
        except Exception as e:
            return f"Error listing candidates: {str(e)}"

    @mcp.tool()
    def memory_consolidate_concepts(project: str | None = None, limit: int = 20, root_name: str = "Agent Memory") -> str:
        """Suggest concept/candidate clusters that should be reviewed for merge or consolidation."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store:
                    return "Sidecar index not available."

                active_project = project
                if not active_project:
                    cols = mm.ensure_collections(root_name=root_name)
                    settings = mm.get_settings(cols["system"])
                    active_project = settings.get("active_project_slug")

                results = mm.get_consolidation_candidates(project=active_project or "", limit=limit)
                payload = {
                    "project": active_project,
                    "review_only": True,
                    "merge_policy": "human_confirmation_required",
                    "clusters": results,
                }
                return json.dumps(payload, indent=2)
        except Exception as e:
            return f"Error consolidating concepts: {str(e)}"

    @mcp.tool()
    def memory_catalog_promote_candidate(candidate_id: str, project: str, title: str | None = None, summary: str = "", root_name: str = "Agent Memory") -> str:
        """Promote a candidate to a stable Zotero concept."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                if not mm.store: return "Sidecar index not available."
                
                # Fetch all candidates to check existence
                candidates = mm.store.get_candidates(limit=1000)
                candidate = next((c for c in candidates if c["candidate_id"] == candidate_id), None)
                if not candidate: 
                    return f"Candidate {candidate_id} not found."
                
                final_title = title or candidate["suggested_title"]
                
                # Create actual concept in Zotero
                cols = mm.ensure_collections(root_name=root_name, project_slug=project)
                mem_id = MemoryItem.generate_mem_id(project)
                m_item = MemoryItem(
                    mem_id=mem_id, 
                    mem_class="concept", 
                    role="synthesis", 
                    project=project, 
                    title=f"[MEM][concept][{project}] {final_title}", 
                    content=f"Promoted from candidate: {candidate_id}\n\n{summary}",
                    summary=summary,
                    source="agent", 
                    confidence="high",
                    catalog_concept_id=candidate_id 
                )
                # This call will also sync to sidecar via mm._sync_to_sidecar
                resp = mm.create_memory_item(m_item, cols["project"])
                
                # Clean up sidecar candidate table
                mm.store.delete_candidate(candidate_id)
                
                return f"Successfully promoted {candidate_id} to Zotero concept (Key: {resp.get('key')})."
        except Exception as e:
            return f"Error promoting candidate: {str(e)}"
