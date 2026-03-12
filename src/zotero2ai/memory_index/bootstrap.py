import logging
from datetime import datetime
from typing import Dict, List, Any

from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.models import MemoryItem
from zotero2ai.memory_index.store import MemoryIndexStore
from zotero2ai.memory_index.types import CatalogConcept

logger = logging.getLogger(__name__)

async def rebuild_index(memory_manager: MemoryManager, store: MemoryIndexStore, root_name: str = "Agent Memory"):
    """
    Rebuild the sidecar index from scratch by scanning Zotero Agent Memory.
    """
    logger.info("Starting rebuild of sidecar memory index...")
    store.clear_all()

    # 1. Resolve basic collections
    cols = memory_manager.ensure_collections(root_name=root_name)
    root_key = cols.get("root")
    if not root_key:
        logger.error("Root collection '%s' not found.", root_name)
        return

    # 2. Find all project sub-collections
    sub_cols = memory_manager.client.get_collections(parent_key=root_key)
    projects = []
    
    for col in sub_cols:
        if col["name"].startswith("_"): continue 
        slug = col["name"].lower().replace(" ", "-")
        projects.append({"slug": slug, "key": col["key"], "name": col["name"]})

    logger.info("Found %d projects to index.", len(projects))

    # 3. First pass: Index all Concepts to establish catalog mapping
    concept_map = {} # item_key -> catalog_id
    all_mem_items = []

    for project in projects:
        logger.info("First pass (concepts): %s", project["name"])
        items = memory_manager.recall(
            project_slug=project["slug"], 
            state=None, 
            limit=2000, 
            include_full_content=True
        )
        
        for item in items:
            m_key = item.get("key")
            # We need raw notes for catalog_concept_id parsing
            try:
                notes = memory_manager.client.get_notes(parent_item_key=m_key)
                note_content = notes[0].get("note", "") if notes else ""
                
                raw_item = memory_manager.client.get_item(m_key)
                if isinstance(raw_item, list): raw_item = raw_item[0]
                
                mem_item = MemoryItem.from_zotero_data(raw_item, note_content)
                if not mem_item: continue
                
                all_mem_items.append((mem_item, m_key, raw_item.get("related", [])))

                if mem_item.mem_class == "concept":
                    cat_id = mem_item.catalog_concept_id or store.make_catalog_concept_id(mem_item.title)
                    concept_map[m_key] = cat_id
                    
                    store.add_concept(CatalogConcept(
                        catalog_concept_id=cat_id,
                        title=mem_item.title,
                        concept_label=store.extract_concept_label(mem_item.title),
                        summary=mem_item.summary,
                        state="stable" if mem_item.state == "active" else "archived"
                    ))
                    store.register_usage(mem_item.project, cat_id, m_key)
            except Exception as e:
                logger.warning("Error processing item %s: %s", m_key, str(e))

    # 4. Second pass: Register unit support using the concept map
    logger.info("Second pass: Linking units to concepts...")
    for mem_item, m_key, related in all_mem_items:
        if mem_item.mem_class == "unit":
            # Check for related items that are concepts
            for related_key in related:
                if related_key in concept_map:
                    cat_id = concept_map[related_key]
                    store.register_unit_support(m_key, cat_id, mem_item.project)

    for project in projects:
        try:
            memory_manager._refresh_project_candidates(project["slug"])
        except Exception as e:
            logger.warning("Could not refresh candidates for %s: %s", project["slug"], str(e))

    store.update_index_state("last_rebuild_at", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    logger.info("Rebuild completed successfully.")
