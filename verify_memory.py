import asyncio
from zotero2ai.zotero.plugin_client import PluginClient
from zotero2ai.zotero.memory import MemoryManager
import os

async def verify():
    token = os.environ.get("ZOTERO_MCP_TOKEN")
    if not token:
        print("Set ZOTERO_MCP_TOKEN!")
        return
    
    client = PluginClient(auth_token=token)
    mm = MemoryManager(client)
    
    print("--- 1. Testing Connection & Collection Creation ---")
    try:
        cols = mm.ensure_collections(root_name="Agent Memory - Test", project_slug="verification")
        print(f"Collections set up: {cols}")
        
    except Exception as e:
        print(f"Error connecting to Zotero (did you update the plugin?): {e}")
        return

    print("\n--- 2. Testing Tag Registry Initial Content ---")
    # Manually bootstrapping the registry note if it doesn't exist
    registry_title = "[MEM][system][global] Tag Registry"
    items = client.search_items(query=registry_title, collection_key=cols["system"])
    
    if not any(i["title"] == registry_title for i in items):
        print("Initializing Registry note...")
        note_html = "<pre>allowed_tags:\n  mem:class: [unit, concept, project, system]\n  mem:role: [question, observation, hypothesis, result, synthesis]</pre>"
        client.create_item(
            item_type="report",
            title=registry_title,
            tags=["mem:class:system"],
            collections=[cols["system"]],
            note=note_html
        )
        print("Registry initialized!")
    else:
        print("Registry already exists.")

    print("\n--- 3. Testing Memory Creation (The 'Digital Thread') ---")
    from zotero2ai.zotero.models import MemoryItem
    import httpx
    
    mem_id = MemoryItem.generate_mem_id("verification")
    m_item = MemoryItem(
        mem_id=mem_id,
        mem_class="unit",
        role="observation",
        project="verification",
        title=f"[MEM][unit][verification] Digital Thread Verified",
        content="This memory confirms that the Python -> Bridge -> Zotero communication chain is operational.",
        source="mcp-verifier",
        confidence="high",
        tags=["mem:domain:dev-ops"]
    )
    
    try:
        resp = mm.create_memory_item(m_item, cols["project"])
        print(f"SUCCESS! Created memory item key: {resp.get('key')}")
        print("Please check your Zotero to see the item under 'Agent Memory - Test/Verification'.")
    except httpx.HTTPStatusError as e:
        print(f"Creation failed with {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"Creation failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify())
