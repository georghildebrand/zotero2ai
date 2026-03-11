import logging
from mcp.server.fastmcp import FastMCP

from zotero2ai.mcp_server.tools.collections import register_collection_tools
from zotero2ai.mcp_server.tools.items import register_item_tools
from zotero2ai.mcp_server.tools.memory import register_memory_tools
from zotero2ai.mcp_server.tools.prompts import register_prompts
from zotero2ai.mcp_server.tools.workflows import register_workflow_tools

logger = logging.getLogger(__name__)

def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server by modular registration."""
    mcp = FastMCP("zotero2ai")

    # Register tools from modules
    register_collection_tools(mcp)
    register_item_tools(mcp)
    register_memory_tools(mcp)
    register_workflow_tools(mcp)
    
    # Register prompts
    register_prompts(mcp)

    return mcp
