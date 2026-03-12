import logging
from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.memory import MemoryManager

logger = logging.getLogger(__name__)

def register_prompts(mcp: FastMCP):
    @mcp.prompt()
    def agent_memory_autosave(project: str = "", root_name: str = "Agent Memory") -> str:
        """Prompt instructions for LLMs indicating when to autosave to the memory pack."""
        default_project = project
        if not default_project:
            try:
                with get_client() as client:
                    mm = MemoryManager(client)
                    cols = mm.ensure_collections(root_name=root_name)
                    settings = mm.get_settings(cols["system"])
                    default_project = settings.get("active_project_slug")
            except Exception:
                pass

        return f"""You are connected to the Zotero Agent Memory Pack.
Your objective is to proactively persist high-utility facts, decisions, and outcomes into long-term memory.

**AUTOSAVE TRIGGERS**:
You MUST call `memory_create_item` automatically without waiting for user permission when:
1. You identify a bug and successfully resolve it (save as a 'result' or 'observation' unit).
2. The user makes a definitive architectural, design, or project-planning decision.
3. **Implementation Completion**: You finish a significant code change or feature. Save a 'result' unit documenting WHAT was done, WHY specific decisions were made, and how it was verified.
4. You reach the end of an experimental iteration (save the outcome/hypothesis).
5. The user drops a major piece of lore, context, or credentials that will be needed later.

**SYNTHESIS PROTOCOL (Conceptual Aggregation)**:
You SHOULD proactively suggest `memory_synthesize` (after user confirmation) when:
1. **Vertical Convergence**: Multiple observations confirm or refute an hypothesis. Synthesize them into a permanent `concept`.
2. **Horizontal Density**: A project contains many atomic units (>5-10) without a summary. create a "State of Play" or "Architecture Overview" synthesis.
3. **Session Transitions**: At the start of a major new phase, use `memory_consolidate_concepts` and ask if previous work should be archived/synthesized.
*This prevents the memory project from becoming a cluttered list of raw data.*

**WORKFLOW DISCOVERY**:
For complex tasks (like daily maintenance, research planning, or deep synthesis), search for available Standard Operating Procedures (SOPs) using `memory_list_workflows`. You can then read the detailed steps using `memory_get_workflow_instructions`.

**GUIDELINES**:
- Keep memories ATOMIC. Extract distinct facts into separate MemoryItems.
- ALWAYS use tags for categorization (e.g. `mem:domain:physics`, `mem:domain:software-development`).
- Focus on what the "future you" navigating this workspace would need to instantly onboard.
- Current active project to default to (if any): {default_project or 'Ask the user or infer from context'}
"""
