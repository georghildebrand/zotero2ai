import os
import sys

from zotero2ai.zotero.plugin_client import PluginClient


def main() -> int:
    token = os.environ.get("ZOTERO_MCP_TOKEN", "")
    if not token:
        print("ERROR: Set ZOTERO_MCP_TOKEN first.")
        return 1

    with PluginClient(auth_token=token) as client:
        health = client.health_check()
        status = health.get("status")
        version = health.get("version")
        print(f"Health: status={status!r} version={version!r}")
        if status != "ok":
            print(f"ERROR: unexpected /health response: {health}")
            return 1

        roots = client.get_collections(parent_key="root", limit=20, start=0)
        print(f"Root collections: {len(roots)}")
        for c in roots[:10]:
            print(f"- {c.get('fullPath', c.get('name', ''))} ({c.get('key', '?')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

