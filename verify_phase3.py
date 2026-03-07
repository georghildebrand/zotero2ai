import asyncio
import json
import os
import sys

# Append project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem

async def verify_phase3():
    token = os.environ.get("ZOTERO_MCP_TOKEN")
    if not token:
        print("ERROR: ZOTERO_MCP_TOKEN not set.", file=sys.stderr)
        sys.exit(1)
        
    client = PluginClient(auth_token=token)
    mm = MemoryManager(client)
    
    project = "phase3-verify"
    print("=" * 60)
    print("Phase 3 Verification: Consolidation & Synthesis")
    print("=" * 60 + "\n")

    try:
        print("--- 1. Setting up project ---")
        cols = mm.ensure_collections(root_name="Agent Memory", project_slug=project)
        print(f"  Project collection: {cols['project']}")
        
        print("\n--- 2. Creating multiple base observations ---")
        observations = []
        for i in range(1, 4):
            mem = MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project),
                mem_class="unit",
                role="observation",
                project=project,
                title=f"[MEM][unit][phase3-verify] Obv {i}",
                content=f"This is the raw observation number {i} for phase 3.",
                source="agent"
            )
            result = mm.create_memory_item(mem, cols["project"])
            key = result["key"]
            observations.append(key)
            print(f"  Created Obv {i} -> key={key}")

        print("\n--- 3. Testing get_consolidation_candidates ---")
        clusters = mm.get_consolidation_candidates(project, limit=10)
        total_cands = sum(len(c["items"]) for c in clusters)
        print(f"  Found {total_cands} candidates:")
        for cluster in clusters:
            for c in cluster["items"]:
                if c["key"] in observations:
                    print(f"    - [{c['role']}] {c['title']} (key={c['key']})")

        print("\n--- 4. Synthesizing these candidates ---")
        synthesis_item = MemoryItem(
            mem_id=MemoryItem.generate_mem_id(project),
            mem_class="concept",
            role="synthesis",
            project=project,
            title="[MEM][concept][phase3-verify] Unified Theory",
            content="By looking at Obv 1, 2, and 3, we can conclude that phase 3 is going to be incredibly powerful.",
            source="agent"
        )
        
        synth_result = mm.synthesize(
            source_keys=observations,
            new_item=synthesis_item,
            project_key=cols["project"],
            supersede_sources=True
        )
        synth_key = synth_result["synthesis_key"]
        print(f"  Created Synthesis -> key={synth_key}")
        print(f"  Sources Linked: {synth_result['sources_linked']}")
        print(f"  Sources Superseded: {synth_result['sources_superseded']}")

        print("\n--- 5. Verifying Graph structure ---")
        graph = mm.follow_links(synth_key, hops=1)
        print(f"  Graph connected to {synth_key}:")
        related = graph.get("related", [])
        print(f"  Count of linked sources from synthesis: {len(related)}")
        for r in related:
            print(f"    - {r.get('title')} (key={r.get('key')})")

        print("\n--- 6. Verifying Candidates after Synthesis ---")
        import time
        print("  Waiting 2 seconds for Zotero tag indexing...")
        time.sleep(2)
        new_candidates = mm.get_consolidation_candidates(project)
        total_new_cands = sum(len(c["items"]) for c in new_candidates)
        print(f"  Found {total_new_cands} candidates. (Should be 0 if they were superseded)")

        
        print("\n" + "=" * 60)
        print("Phase 3 Verification Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_phase3())
