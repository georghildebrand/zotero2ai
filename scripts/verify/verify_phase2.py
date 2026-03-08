"""Phase 2 Verification: Retrieval & Recall end-to-end test (manual).

WARNING: This script creates items in your Zotero library under a dedicated test root.
There is no automated cleanup. Run only when you explicitly want to verify write paths.
"""

import asyncio
import json
import os

import httpx

from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem
from zotero2ai.zotero.plugin_client import PluginClient


async def main() -> int:
    token = os.environ.get("ZOTERO_MCP_TOKEN", "")
    if not token:
        print("ERROR: Set ZOTERO_MCP_TOKEN first.")
        return 1

    client = PluginClient(auth_token=token)
    mm = MemoryManager(client)

    root_name = "Agent Memory - Test"
    project_slug = "phase2-verify"

    try:
        print("=" * 60)
        print("Phase 2 Verification (manual)")
        print("=" * 60)

        cols = mm.ensure_collections(root_name=root_name, project_slug=project_slug)
        print(f"Collections set up: root={cols['root']} system={cols['system']} project={cols['project']}")

        print("\n--- 1) Creating test memories ---")
        keys: list[str] = []
        test_items = [
            ("Observation Alpha", "observation", "First observation about the system.", "high"),
            ("Hypothesis Beta", "hypothesis", "If we change X, then Y should improve.", "medium"),
            ("Result Gamma", "result", "Experiment confirmed: Y improved by 15%.", "high"),
        ]
        for label, role, content, confidence in test_items:
            mem_id = MemoryItem.generate_mem_id(project_slug)
            m = MemoryItem(
                mem_id=mem_id,
                mem_class="unit",
                role=role,
                project=project_slug,
                title=f"[MEM][unit][{project_slug}] {label}",
                content=content,
                source="manual",
                confidence=confidence,
                tags=["mem:domain:software-development"],
            )
            resp = mm.create_memory_item(m, cols["project"])
            key = str(resp.get("key", "?"))
            keys.append(key)
            print(f"  Created: {label} → key={key}")

        await asyncio.sleep(1)

        print("\n--- 2) Recall active ---")
        results = mm.recall(project_slug=project_slug, state="active", root_name=root_name)
        print(f"Found {len(results)} active memories.")

        print("\n--- 3) Recall only hypotheses ---")
        results = mm.recall(project_slug=project_slug, tags=["mem:role:hypothesis"], state="active", root_name=root_name)
        print(f"Found {len(results)} hypotheses.")

        print("\n--- 4) Timeline ---")
        timeline = mm.timeline(project_slug=project_slug, root_name=root_name)
        print(f"Timeline entries: {len(timeline)}")

        print("\n--- 5) Link & graph traversal ---")
        if len(keys) >= 3:
            mm.link_items(keys[0], keys[1])
            mm.link_items(keys[1], keys[2])
            graph = mm.follow_links(keys[0], hops=2)
            print(json.dumps(graph, indent=2, default=str))

        print("\n--- 6) Supersede ---")
        if keys:
            old_key = keys[0]
            new_item = MemoryItem(
                mem_id=MemoryItem.generate_mem_id(project_slug),
                mem_class="unit",
                role="observation",
                project=project_slug,
                title=f"[MEM][unit][{project_slug}] Observation Alpha v2",
                content="Updated observation: the system behaves differently under load.",
                source="manual",
                confidence="high",
                tags=["mem:domain:software-development"],
            )
            result = mm.supersede(old_key, new_item, cols["project"])
            print(f"Superseded: {result['old_key']} → {result['new_key']} ({result['status']})")

        print("\nDone.")
        return 0

    except httpx.HTTPStatusError as e:
        print(f"\nHTTP error {e.response.status_code}: {e.response.text}")
        return 1
    except Exception as e:
        print(f"\nVerification failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

