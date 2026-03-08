import os

import pytest

from zotero2ai.zotero.plugin_client import PluginClient


@pytest.mark.e2e
def test_e2e_bridge_smoke():
    """Optional read-only E2E smoke test against a running Zotero + Bridge plugin.

    Enable explicitly via environment:
      - ZOTERO_E2E=1
      - ZOTERO_MCP_TOKEN=...

    This test is read-only and should not create or modify library content.
    """
    if os.environ.get("ZOTERO_E2E") != "1":
        pytest.skip("E2E smoke disabled (set ZOTERO_E2E=1 to enable).")

    token = os.environ.get("ZOTERO_MCP_TOKEN", "")
    if not token:
        pytest.skip("ZOTERO_MCP_TOKEN not set.")

    with PluginClient(auth_token=token) as client:
        health = client.health_check()
        assert health.get("status") == "ok"
        assert isinstance(health.get("version", ""), str)

        # Basic read operation (root collections), to ensure auth + list endpoints work.
        collections = client.get_collections(parent_key="root", limit=5, start=0)
        assert isinstance(collections, list)

