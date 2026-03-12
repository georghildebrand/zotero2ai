import os
import logging
import json
import yaml
from mcp.server.fastmcp import FastMCP

from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.memory import MemoryManager

logger = logging.getLogger(__name__)

def register_workflow_tools(mcp: FastMCP):
    # Determine the project root (assuming we are in src/zotero2ai/mcp_server/tools)
    # A more robust way would be to pass the path or use a config, 
    # but for now, we'll look for .agent/workflows relative to the current working directory
    # or the package root.
    
    def get_workflow_dir():
        # Try to find .agent/workflows starting from CWD
        cwd = os.getcwd()
        potential_path = os.path.join(cwd, ".agent", "workflows")
        if os.path.isdir(potential_path):
            return potential_path
        
        # Fallback: search upwards from this file
        current_file = os.path.abspath(__file__)
        path = os.path.dirname(current_file)
        while path != os.path.dirname(path):  # Stop at root
            check_path = os.path.join(path, ".agent", "workflows")
            if os.path.isdir(check_path):
                return check_path
            path = os.path.dirname(path)
        
        return None

    def parse_workflow_file(path: str) -> dict[str, str]:
        metadata: dict[str, str] = {}
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    parsed = yaml.safe_load(parts[1]) or {}
                    if isinstance(parsed, dict):
                        metadata = {str(k): str(v) for k, v in parsed.items()}
                    body = parts[2].lstrip()
                except Exception:
                    body = content

        description = metadata.get("description", "No description available.")
        if description == "No description available." and body.startswith("#"):
            description = body.split("\n")[0].replace("#", "").strip()

        metadata["description"] = description
        metadata["body"] = body
        metadata.setdefault("workflow_type", "task_sop")
        metadata.setdefault("status", "active")
        return metadata

    @mcp.tool()
    def memory_list_workflows() -> str:
        """List available agentic workflow templates (Standard Operating Procedures)."""
        workflow_dir = get_workflow_dir()
        if not workflow_dir:
            return "Error: Workflow directory (.agent/workflows) not found."

        workflows = []
        try:
            for filename in os.listdir(workflow_dir):
                if filename.endswith(".md"):
                    path = os.path.join(workflow_dir, filename)
                    metadata = parse_workflow_file(path)
                    workflows.append({
                        "name": filename.replace(".md", ""),
                        "description": metadata["description"],
                        "workflow_type": metadata.get("workflow_type", "task_sop"),
                        "status": metadata.get("status", "active"),
                        "project_hint": metadata.get("project_hint", ""),
                        "schedule_hint": metadata.get("schedule_hint", ""),
                    })
            workflows.sort(key=lambda wf: (wf["workflow_type"] != "general", wf["name"]))
            return json.dumps({
                "general": [w for w in workflows if w["workflow_type"] == "general"],
                "task_sops": [w for w in workflows if w["workflow_type"] != "general"],
            }, indent=2)
        except Exception as e:
            return f"Error listing workflows: {str(e)}"

    @mcp.tool()
    def memory_get_workflow_instructions(workflow_name: str) -> str:
        """Get the detailed step-by-step instructions for a specific workflow."""
        workflow_dir = get_workflow_dir()
        if not workflow_dir:
            return "Error: Workflow directory not found."

        filename = f"{workflow_name}.md"
        path = os.path.join(workflow_dir, filename)
        
        if not os.path.isfile(path):
            return f"Error: Workflow '{workflow_name}' not found."

        try:
            metadata = parse_workflow_file(path)
            payload = {
                "name": workflow_name,
                "workflow_type": metadata.get("workflow_type", "task_sop"),
                "status": metadata.get("status", "active"),
                "description": metadata.get("description", ""),
                "instructions": metadata.get("body", ""),
            }
            if metadata.get("project_hint"):
                payload["project_hint"] = metadata["project_hint"]
            if metadata.get("schedule_hint"):
                payload["schedule_hint"] = metadata["schedule_hint"]
            return json.dumps(payload, indent=2)
        except Exception as e:
            return f"Error reading workflow: {str(e)}"

    @mcp.tool()
    def memory_overview(project_slug: str, timeline_limit: int = 15) -> str:
        """Compact project overview (context + graph + timeline)."""
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                mm.ensure_collections(project_slug=project_slug)

                context = mm.get_project_context(project_slug=project_slug)
                graph = mm.generate_mermaid_graph(project_slug)
                timeline = mm.timeline(project_slug=project_slug, limit=timeline_limit)

            lines: list[str] = [context.rstrip(), "\n---\n", "## Project Graph (Mermaid)", graph.rstrip(), "\n---\n", "## Recent Timeline"]
            for entry in timeline:
                title = entry.get("title", "(untitled)")
                key = entry.get("key", "")
                date_added = entry.get("dateAdded", "")
                lines.append(f"- {date_added} :: {title} ({key})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error building overview: {str(e)}"

    @mcp.tool()
    def tool_catalog() -> str:
        """Grouped list of tools with recommended entry points (non-breaking)."""
        catalog = {
            "preferred": {
                "recommended": [
                    "search_papers",
                    "list_notes_recursive",
                    "read_note",
                    "memory_inspect",
                    "memory_seed_session",
                    "memory_create_item",
                    "memory_recall",
                    "memory_timeline",
                    "memory_catalog_search",
                    "memory_consolidate_concepts",
                    "memory_commit_episode",
                    "memory_overview",
                    "memory_list_workflows",
                    "memory_get_workflow_instructions",
                ],
                "tools": [
                    "search_papers",
                    "read_note",
                    "list_notes_recursive",
                    "create_or_extend_note",
                    "memory_inspect",
                    "memory_seed_session",
                    "memory_create_item",
                    "memory_recall",
                    "memory_timeline",
                    "memory_synthesize",
                    "memory_catalog_search",
                    "memory_consolidate_concepts",
                    "memory_commit_episode",
                    "memory_overview",
                    "memory_list_workflows",
                    "memory_get_workflow_instructions",
                ],
            },
            "advanced": {
                "recommended": ["get_collection_tree", "list_collections", "memory_catalog_get_details"],
                "tools": [
                    "list_collections",
                    "search_collections",
                    "set_active_collection",
                    "get_active_collection",
                    "get_collection_tree",
                    "get_collection_attachments",
                    "list_notes",
                    "get_item_attachments",
                    "get_item_content",
                    "rename_tag",
                    "list_tags",
                    "get_recent_papers",
                    "memory_supersede",
                    "memory_archive_item",
                    "memory_catalog_list",
                    "memory_catalog_get_details",
                    "memory_catalog_list_candidates",
                    "memory_catalog_promote_candidate",
                ],
            },
            "legacy": {
                "recommended": [],
                "tools": [
                    "memory_initialize",
                    "memory_get_registry",
                ],
                "notes": "Available for backward compatibility and setup flows, but not preferred for normal agent use.",
            },
        }
        return json.dumps(catalog, indent=2)

    @mcp.tool()
    def host_tool_groups() -> str:
        """Host-facing grouped tool metadata with preferred/advanced/legacy flags."""
        data = {
            "preferred": [
                "search_papers",
                "list_notes_recursive",
                "read_note",
                "create_or_extend_note",
                "memory_inspect",
                "memory_seed_session",
                "memory_create_item",
                "memory_recall",
                "memory_timeline",
                "memory_catalog_search",
                "memory_consolidate_concepts",
                "memory_commit_episode",
                "memory_overview",
                "memory_list_workflows",
                "memory_get_workflow_instructions",
            ],
            "advanced": [
                "list_collections",
                "search_collections",
                "set_active_collection",
                "get_active_collection",
                "get_collection_tree",
                "get_collection_attachments",
                "list_notes",
                "get_item_attachments",
                "get_item_content",
                "rename_tag",
                "list_tags",
                "get_recent_papers",
                "memory_supersede",
                "memory_archive_item",
                "memory_catalog_list",
                "memory_catalog_get_details",
                "memory_catalog_list_candidates",
                "memory_catalog_promote_candidate",
            ],
            "legacy": [
                "memory_initialize",
                "memory_get_registry",
            ],
            "notes": "Surface preferred tools by default; keep advanced tools available for deliberate use; legacy tools remain for compatibility.",
        }
        return json.dumps(data, indent=2)
