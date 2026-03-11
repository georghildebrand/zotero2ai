---
description: Daily Zotero Memory Extraction and Synthesis
---

# Zotero Memory Maintenance Workflow

Run this workflow daily to ensure recent manual notes from meetings are ingested into the structured Agent Memory system and summarized into higher-level concepts.

## Phase 1: Ingest Manual Meeting Notes
Before reviewing existing structured memories, you must look for new raw data in your manual Zotero folders.

1. **Target Folder**: `00 Projects / 00 2024-10 Centric First Thoughts, Todos And notes` (Key: `IRZCVT92`).
2. **Action**: 
   - Call `list_notes_recursive` for this collection key.
   - Set `date_from` to the last 48 hours (or since your last run).
   - Set `include_content=True` to read the meeting notes.
3. **Extraction**:
   - For each new/relevant meeting note, extract atomic facts, decisions, or action items.
   - Use `memory_create_item` to save these as `unit` class items in the `centric` project.
   - Add appropriate domain tags (e.g., `mem:domain:business-process`, `mem:domain:meeting-minutes`).
   - **Tagging**: Every new item MUST have at least one `mem:domain:<topic>` tag. Consult the `memory_get_registry` tool to see allowed domains or suggest new ones if the project evolves.
- **Linking**: Use `memory_link_items` to link the new structured memory unit back to the original Zotero meeting note.

## Phase 2: Maintenance & Synthesis
Once new data is ingested, perform standard maintenance with a focus on cross-coherence:

1. **Project Review & Context Retrieval**:
   - Set active project: `memory_set_active_project(project_slug="centric")`.
   - **Cross-Check Recall**: Call `memory_recall` for the `centric` project using the SAME `date_from` as in Phase 1. 
   - Purpose: Retrieve any memories created *automatically* by agents during the same timeframe to provide context for the manual notes.

2. **Coherence & De-duplication**:
   - Compare the newly created `unit` items (from manual notes) with the retrieved existing memories.
   - If a manual note and an existing memory cover the same fact: Use `memory_supersede` or `memory_synthesize` immediately to consolidate them.
   - Look for contradictions: If a manual note contradicts an existing agent observation, flag this to the user or create a new `question` unit.

3. **Tagging Hygiene**:
   - Review recent active `unit` and `concept` items.
   - If an item is missing a domain tag, or the tags are too vague, update them using `memory_supersede` (or the internal tag update mechanism if available).

4. **Weekly Project Aggregation (FRIDAYS ONLY)**:
   - If today is Friday:
   - Call `memory_recall` for all `concept` class items in the `centric` project.
   - Synthesize these into a single `project` class item titled "[MEM][project][centric] Weekly State of Play: YYYY-MM-DD".
   - This should summarize the week's key decisions and strategic shifts.

5. **Synthesis & Consolidation**:
   - Call `memory_suggest_consolidation(project="centric")`.
   - Cluster the new `unit` items (from today) with existing ones.
   - If a topic has >= 3 observations, use `memory_synthesize` to create a `concept`.
   - Set `supersede_sources=True` to keep the active memory view clean.

6. **Graphing**:
   - Periodically run `memory_project_graph(project="centric")` to visualize the evolution of the project knowledge.

## Termination Criteria
Success is reached when:
1. All recent notes from the meeting folder are mirrored as structured `unit` items.
2. All new items have correct `mem:domain:*` tags.
3. The `centric` project has no more than 7 *active* units.
4. On Fridays: A project-level "State of Play" has been created.
5. A summary of newly created concepts/projects is provided to the user.
