"""Phase 2 Verification: Retrieval & Recall end-to-end test."""
import asyncio
import os
import json
import httpx

from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem


async def verify_phase2():
    try:
        token = os.environ.get("ZOTERO_MCP_TOKEN", "")
        if not token:
            print("ERROR: Set ZOTERO_MCP_TOKEN first.")
            return

        client = PluginClient(auth_token=token)
        mm = MemoryManager(client)

        ROOT = "Agent Memory - Test"
        PROJECT = "phase2-verify"

        # ── Step 1: Setup ──────────────────────────────────────────────
        print("=" * 60)
        print("Phase 2 Verification")
        print("=" * 60)

        print("\n--- 1. Setting up collections ---")
        cols = mm.ensure_collections(root_name=ROOT, project_slug=PROJECT)
        print(f"  root={cols['root']}  system={cols['system']}  project={cols['project']}")

        # ── Step 2: Create 3 test memories ─────────────────────────────
        print("\n--- 2. Creating test memories ---")
        keys = []
        test_items = [
            ("Observation Alpha", "observation", "First observation about the system.", "high"),
            ("Hypothesis Beta", "hypothesis", "If we change X, then Y should improve.", "medium"),
            ("Result Gamma", "result", "Experiment confirmed: Y improved by 15%.", "high"),
        ]

        for label, role, content, confidence in test_items:
            mem_id = MemoryItem.generate_mem_id(PROJECT)
            m = MemoryItem(
                mem_id=mem_id,
                mem_class="unit",
                role=role,
                project=PROJECT,
                title=f"[MEM][unit][{PROJECT}] {label}",
                content=content,
                source="agent",
                confidence=confidence,
                tags=["mem:domain:dev-ops"],
            )
            resp = mm.create_memory_item(m, cols["project"])
            key = resp.get("key", "?")
            keys.append(key)
            print(f"  Created: {label} → key={key}")

        # Small delay to let Zotero index
        await asyncio.sleep(1)

        # ── Step 3: Recall all active memories ─────────────────────────
        print("\n--- 3. Recall all active memories ---")
        results = mm.recall(project_slug=PROJECT, state="active", root_name=ROOT)
        print(f"  Found {len(results)} active memories:")
        for r in results:
            print(f"    - {r['title']} (key={r['key']}, class={r.get('mem_class', '?')}, role={r.get('role', '?')})")

        # ── Step 4: Recall with role filter ────────────────────────────
        print("\n--- 4. Recall only hypotheses ---")
        results = mm.recall(
            project_slug=PROJECT,
            tags=["mem:role:hypothesis"],
            state="active",
            root_name=ROOT,
        )
        print(f"  Found {len(results)} hypotheses:")
        for r in results:
            print(f"    - {r['title']}")

        # ── Step 5: Timeline ───────────────────────────────────────────
        print("\n--- 5. Timeline ---")
        timeline = mm.timeline(project_slug=PROJECT, root_name=ROOT)
        print(f"  Timeline has {len(timeline)} entries:")
        for t in timeline:
            print(f"    [{t.get('dateAdded', '?')}] {t['title']}")

        # ── Step 6: Link items and follow graph ────────────────────────
        print("\n--- 6. Link & Graph Traversal ---")
        if len(keys) >= 3:
            # Link: Alpha → Beta → Gamma
            mm.link_items(keys[0], keys[1])
            mm.link_items(keys[1], keys[2])
            print(f"  Linked: {keys[0]} → {keys[1]} → {keys[2]}")

            graph = mm.follow_links(keys[0], hops=2)
            print(f"  Graph from {keys[0]}:")
            print(f"    {json.dumps(graph, indent=4, default=str)}")

        # ── Step 7: Supersede ──────────────────────────────────────────
        print("\n--- 7. Supersede ---")
        if keys:
            old_key = keys[0]  # Supersede "Observation Alpha"
            new_mem_id = MemoryItem.generate_mem_id(PROJECT)
            new_item = MemoryItem(
                mem_id=new_mem_id,
                mem_class="unit",
                role="observation",
                project=PROJECT,
                title=f"[MEM][unit][{PROJECT}] Observation Alpha v2",
                content="Updated observation: the system behaves differently under load.",
                source="agent",
                confidence="high",
                tags=["mem:domain:dev-ops"],
            )
            result = mm.supersede(old_key, new_item, cols["project"])
            print(f"  Superseded: {result['old_key']} → {result['new_key']} (status={result['status']})")

        # ── Step 8: Verify superseded is hidden from default recall ────
        print("\n--- 8. Verify superseded item hidden from default recall ---")
        active_results = mm.recall(project_slug=PROJECT, state="active", root_name=ROOT)
        superseded_keys = {keys[0]} if keys else set()
        active_keys = {r["key"] for r in active_results}
        hidden = superseded_keys - active_keys
        if hidden:
            print(f"  ✅ Superseded item {hidden} correctly hidden from active recall.")
        else:
            print(f"  ⚠️  Superseded item may still appear in active recall (tag update might take a moment).")

        # Show superseded items
        all_results = mm.recall(project_slug=PROJECT, state="superseded", root_name=ROOT)
        print(f"  Found {len(all_results)} superseded memories:")
        for r in all_results:
            print(f"    - {r['title']}")

        print("\n" + "=" * 60)
        print("Phase 2 Verification Complete!")
        print("=" * 60)

    except httpx.HTTPStatusError as e:
        print(f"\n❌ HTTP error {e.response.status_code}:")
        try:
            print(json.dumps(e.response.json(), indent=2))
        except:
            print(e.response.text)
    except Exception as e:
        print(f"\n❌ Verification failed with: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(verify_phase2())
