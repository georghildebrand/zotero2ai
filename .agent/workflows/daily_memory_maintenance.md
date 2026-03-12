---
description: Daily maintenance pass for ingesting fresh notes, cleaning units, and proposing concept synthesis
workflow_type: task_sop
status: active
schedule_hint: daily
---

# Daily Memory Maintenance

Use this workflow for a bounded daily pass over recent work. The goal is to keep units fresh, reduce duplication, and surface concept synthesis opportunities without silently creating broad abstractions.

## 1. Gather Today’s Context
- Call `memory_inspect` first.
- If the user already implies a project, use that project.
- Otherwise pick the active project from `memory_inspect` or ask before writing.

## 2. Ingest Recent Notes Only
- Use `list_notes_recursive` on the relevant collection or project subtree.
- Restrict to a recent window such as the last 24 to 72 hours.
- Use `include_content=True` only for notes that matter to the current task.

## 3. Create Or Update Units
- Extract atomic facts, decisions, action items, and outcomes.
- Save them with `memory_create_item(mem_class="unit", ...)`.
- If a new note changes an older fact, prefer `memory_supersede`.
- If a note is historical but no longer actionable, consider `memory_archive_item`.

## 4. Check For Duplicate Or Overlapping Meaning
- Use `memory_recall` for the same project and recent time window.
- Use `memory_catalog_search` before introducing new concept names.
- If overlapping items describe the same reality, consolidate rather than adding parallel active units.

## 5. Propose Concept Synthesis
- Call `memory_consolidate_concepts(project=...)`.
- If the project has several active units around one topic, propose `memory_synthesize` into a `concept`.
- Use `supersede_sources=True` only when the source units are truly replaced by the synthesis.

## 6. Close The Loop
- Return a short maintenance summary:
- new units created
- items superseded or archived
- concept syntheses proposed or created
- unresolved contradictions or blind spots

## Exit Criteria
- Recent relevant notes are represented as structured units.
- No obvious duplicate active units remain unaddressed.
- Concept creation stays reviewable and deliberate.
