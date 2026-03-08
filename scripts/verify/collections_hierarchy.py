import os

from zotero2ai.zotero.plugin_client import PluginClient


def main() -> int:
    token = os.environ.get("ZOTERO_MCP_TOKEN", "")
    if not token:
        print("ERROR: Set ZOTERO_MCP_TOKEN first.")
        return 1

    with PluginClient(auth_token=token) as client:
        print("--- 1) Root collections (parentKey='root') ---")
        roots = client.get_collections(parent_key="root", limit=200, start=0)
        print(f"Found {len(roots)} root collections.")

        target_parent = next((c for c in roots if c.get("childCount", 0) > 0), None)
        for r in roots[:30]:
            child_count = r.get("childCount", 0)
            print(f"- {r.get('name')} (Key: {r.get('key')}) [Children: {child_count}]")

        if not target_parent:
            print("\nNo root collection with children found; nothing else to traverse.")
            return 0

        pkey = target_parent["key"]
        name = target_parent.get("name", pkey)
        print(f"\n--- 2) Sub-collections of '{name}' (Key: {pkey}) ---")
        children = client.get_collections(parent_key=pkey, limit=200, start=0)
        print(f"Found {len(children)} children.")
        for c in children:
            print(f"- {c.get('name')} (Key: {c.get('key')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

