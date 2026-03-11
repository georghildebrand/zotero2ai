import os
import logging
import json
from mcp.server.fastmcp import FastMCP

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
