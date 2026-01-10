
import os
import sys
# Add src to python path to ensure we use the local modified code
sys.path.append("/Users/georg.hildebrand/workspace/github.com/zotero2ai/src")

from zotero2ai.zotero.plugin_client import PluginClient

def test():
    try:
        # Initialize client (will use env vars or defaults)
        # Note: If ZOTERO_MCP_TOKEN is not in env, this might fail if not set in .env file loaded by system
        # checking if we need to mock or if valid envs are typically present in user shell.
        # usually run_command inherits shell env.
        
        client = PluginClient()
        
        print("--- 1. Testing Root Collections (parentKey='root') ---")
        roots = client.get_collections(parent_key='root')
        print(f"Found {len(roots)} root collections.")
        
        target_parent = None
        
        for r in roots:
            child_count = r.get('childCount', 0)
            print(f"  - {r.get('name')} (Key: {r.get('key')}) [Children: {child_count}]")
            if child_count > 0 and target_parent is None:
                target_parent = r
        
        if target_parent:
            pkey = target_parent['key']
            name = target_parent['name']
            print(f"\n--- 2. Testing Sub-Collections of '{name}' (Key: {pkey}) ---")
            children = client.get_collections(parent_key=pkey)
            print(f"Found {len(children)} children.")
            for c in children:
                print(f"  - {c.get('name')} (Key: {c.get('key')})")
        else:
            print("\n--- 2. (Skipping) No root collection with children found to test recursion. ---")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
