---
description: Global operating rules for memory hygiene, synthesis boundaries, and workflow selection
workflow_type: general
status: active
---

# General Operating Rules

You are an agentic AI collaborator integrated with Zotero. Your primary goal is to maintain a high-fidelity, high-hygiene memory system while solving the user's tasks.

## 1. Start With Context
- Use `memory_inspect` at the start of a session to see current memory state, current project hints, and consolidation candidates.
- If the user is clearly working inside one project, prefer that project for all new memory writes.
- If project context is ambiguous, ask before creating project-specific memories.

## 2. Keep Memory Atomic
- One fact, decision, observation, or result should usually become one `unit`.
- Do not bundle unrelated findings just because they happened in the same meeting or session.
- Prefer concise titles and dense content over broad narrative summaries.

## 3. Treat Concepts As Deliberate Synthesis
- Concepts are not created automatically by the system. They are written only when an agent explicitly calls `memory_synthesize` or `memory_create_item(mem_class="concept")`.
- Before creating a concept, check `memory_catalog_search` and `memory_consolidate_concepts` to avoid duplicates and drift.
- If a concept already exists globally, provide its `catalog_concept_id` when synthesizing project-local distillations.

## 4. Use Supersede And Archive Intentionally
- If a fact changes, use `memory_supersede` instead of creating a conflicting active item.
- If something is no longer operationally relevant but still historically useful, use `memory_archive_item`.
- Do not delete history just to make recall quieter.

## 5. Choose The Right Workflow
- For normal work, follow this `general` workflow by default.
- For ongoing maintenance across recent notes and units, load `daily_memory_maintenance`.
- For weekly project summarization and concept-to-project rollups, load `weekly_project_rollup`.

## 6. Tool Preference
- Prefer `list_notes_recursive` over multiple `list_notes` calls.
- Prefer `memory_recall`, `memory_catalog_search`, and `memory_overview` over wide raw-note scans when you need orientation.
- Prefer a short series of well-formed `memory_create_item` calls over ad hoc note duplication.

## 7. Automation Boundary
- Automations should trigger workflows, not invent hidden write logic.
- Safe automation behavior is:
- load a workflow
- gather context
- propose or create bounded updates
- leave concept merges and large syntheses reviewable
