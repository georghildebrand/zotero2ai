import logging
from zotero2ai.config import resolve_zotero_bridge_port, resolve_zotero_mcp_token
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)

def get_client() -> PluginClient:
    token = resolve_zotero_mcp_token()
    if not token:
        raise ValueError("Zotero MCP token not found. Please ensure the Zotero Bridge Plugin is installed and ZOTERO_MCP_TOKEN environment variable is set.")

    port = resolve_zotero_bridge_port()
    base_url = f"http://127.0.0.1:{port}"
    return PluginClient(base_url=base_url, auth_token=token)
