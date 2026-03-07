import asyncio
import json
import os
import sys

# Append project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.memory import MemoryManager

async def verify_phase5():
    token = os.environ.get("ZOTERO_MCP_TOKEN")
    if not token:
        print("ERROR: ZOTERO_MCP_TOKEN not set.", file=sys.stderr)
        sys.exit(1)
        
    client = PluginClient(auth_token=token)
    mm = MemoryManager(client)
    
    project = "phase3-verify"  # Has synthesis items!
    print("=" * 60)
    print("Phase 5 Verification: Mermaid Graph")
    print("=" * 60 + "\n")

    try:
        col_key = mm.ensure_collections(project_slug=project)["project"]
        print(f"Project Col Key: {col_key}")
        all_col_items = mm.client.search_items(collection_key=col_key, limit=500)
        
        super_count = 0
        active_count = 0
        for i in all_col_items:
            tags = i.get('tags', [])
            tag_strings = [t.get('tag') if isinstance(t, dict) else t for t in tags]
            if "mem:state:superseded" in tag_strings:
                super_count += 1
            if "mem:state:active" in tag_strings:
                active_count += 1
                
        print(f"Direct collection fetch -> Superseded: {super_count}, Active: {active_count}")

        # Fetch using recall
        active = mm.recall(project, state="active", limit=100)
        superseded = mm.recall(project, state="superseded", limit=100)
        print(f"Recall fetch -> Active: {len(active)}, Superseded: {len(superseded)}")

        mermaid = mm.generate_mermaid_graph(project)
        print("\n--- Graph ---")
        print(mermaid)
    except Exception as e:
        print(f"\\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_phase5())
