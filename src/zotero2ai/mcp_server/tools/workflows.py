import os
import logging
import json
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
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Simple frontmatter/description extraction
                        description = "No description available."
                        if "description:" in content:
                            lines = content.split("\n")
                            for line in lines:
                                if line.startswith("description:"):
                                    description = line.replace("description:", "").strip()
                                    break
                        elif content.startswith("#"):
                            description = content.split("\n")[0].replace("#", "").strip()
                        
                        workflows.append({
                            "name": filename.replace(".md", ""),
                            "description": description
                        })
            return json.dumps(workflows, indent=2)
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
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
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
            "collections": {
                "recommended": ["list_collections", "get_collection_tree"],
                "tools": [
                    "list_collections",
                    "search_collections",
                    "set_active_collection",
                    "get_active_collection",
                    "get_collection_tree",
                    "get_collection_attachments",
                ],
            },
            "items_and_notes": {
                "recommended": ["search_papers", "list_notes", "create_or_extend_note"],
                "tools": [
                    "search_papers",
                    "read_note",
                    "list_notes",
                    "list_notes_recursive",
                    "create_or_extend_note",
                    "get_item_attachments",
                    "get_item_content",
                    "rename_tag",
                    "list_tags",
                    "get_recent_papers",
                ],
            },
            "memory_core": {
                "recommended": ["memory_create_item", "memory_recall", "memory_timeline"],
                "tools": [
                    "memory_initialize",
                    "memory_get_registry",
                    "memory_create_item",
                    "memory_recall",
                    "memory_timeline",
                    "memory_supersede",
                    "memory_synthesize",
                    "memory_archive_item",
                    "memory_inspect",
                ],
            },
            "memory_insights": {
                "recommended": ["memory_overview"],
                "tools": [
                    "memory_overview",
                    "memory_get_workflow_instructions",
                    "memory_list_workflows",
                ],
            },
        }
        return json.dumps(catalog, indent=2)

    @mcp.tool()
    def host_tool_groups() -> str:
        """Host-facing grouped tool metadata with preferred/legacy flags."""
        data = {
            "preferred": [
                "list_collections",
                "get_collection_tree",
                "search_papers",
                "list_notes",
                "create_or_extend_note",
                "memory_create_item",
                "memory_recall",
                "memory_timeline",
                "memory_overview",
                "memory_inspect",
            ],
            "legacy": [],
            "notes": "Surface preferred tools by default; others remain available but may be hidden in host UIs.",
        }
        return json.dumps(data, indent=2)
