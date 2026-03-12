# AGENTS.md

This file defines repository-local agent behavior for Codex and similar coding hosts.

## Project Scope

When the user asks to summarize a project or a time period, default to the `zotero2ai` MCP / memory system context unless the user clearly means a different project.

Point out blind spots and missing perspectives when they materially affect the result.

## Runtime Commands

Use the repository-local `uv` environment and prefer the source tree explicitly:

```bash
uv run python -m zotero2ai.cli doctor
uv run python -m zotero2ai.cli run
uv run python -m zotero2ai.cli rebuild-memory-index
```

If mobile sync is needed, run it via the main server:

```bash
uv run python -m zotero2ai.cli run --mobile-sync-dir ~/ZoteroQueue
```

## Host Prompt Conventions

Treat the following user shorthands as explicit workflow triggers.

### `@zotero/init`

If the user starts with `@zotero/init`, interpret it as a coding or research session bootstrap request.

Expected behavior:
- infer or confirm the active project
- call `memory_seed_session(project=..., task=..., depth="adaptive")`
- summarize the returned `project_brief`, relevant concepts, relevant repos, ticket IDs, architecture references, implementation instructions, and open questions
- decide whether additional concept or unit-level recall is needed before starting implementation

Preferred follow-up behavior:
- if context is still thin, use `memory_catalog_search`, `memory_recall`, or `memory_overview`
- keep retrieval project-first, not global-first

### `@zotero/commit`

If the user starts with `@zotero/commit`, interpret it as an end-of-episode memory update.

Expected behavior:
- collect the task summary, key learnings, important decisions, changes made, and open questions from the just-finished episode
- call `memory_commit_episode(...)`
- report what was written and whether concept synthesis is now recommended

Important boundary:
- `@zotero/commit` should write unit-level learnings automatically
- concept and project syntheses should remain deliberate and reviewable unless the user clearly asks for them

### `@zotero/overview`

If the user starts with `@zotero/overview`, interpret it as a request for a compact project-first status snapshot.

Expected behavior:
- infer or confirm the active project
- call `memory_overview(project_slug=...)`
- summarize the current project context, recent timeline signals, and notable blind spots

### `@zotero/find`

If the user starts with `@zotero/find`, interpret it as a targeted retrieval request across the current Zotero/project context.

Expected behavior:
- infer whether the user is looking for a paper, a concept, a note, or a collection
- prefer `search_papers` for bibliography-like requests
- prefer `memory_catalog_search` or `memory_recall` for memory/concept retrieval
- prefer `search_collections` when the user is trying to locate the right Zotero collection
- keep retrieval project-first, not global-first

### `@zotero/recall`

If the user starts with `@zotero/recall`, interpret it as a project-scoped memory recall request.

Expected behavior:
- infer or confirm the active project
- call `memory_recall(project=...)`
- use tags, dates, and content inclusion deliberately based on the user request
- summarize retrieved items and highlight uncertainty or missing perspectives

### `@zotero/timeline`

If the user starts with `@zotero/timeline`, interpret it as a request for recent project evolution.

Expected behavior:
- infer or confirm the active project
- call `memory_timeline(project=...)`
- summarize recent developments, transitions, and unresolved threads

### `@zotero/note`

If the user starts with `@zotero/note`, interpret it as a request to write or extend a Zotero note in the relevant collection or item.

Expected behavior:
- identify the best matching collection or parent item before writing
- use `create_or_extend_note(...)`
- keep notes concise, action-oriented, and contextualized
- if collection choice is ambiguous, make a reasonable assumption and state it

### `@zotero/workflows`

If the user starts with `@zotero/workflows`, interpret it as a request to inspect available memory workflows.

Expected behavior:
- call `memory_list_workflows`
- if the user wants details for a specific workflow, call `memory_get_workflow_instructions`
- explain when a workflow is preferable to direct tool use

## Workflow Selection

Workflow layers are:
- `general`
- `daily_memory_maintenance`
- `weekly_project_rollup`

Use `memory_list_workflows` and `memory_get_workflow_instructions` when a task calls for a workflow rather than direct tool use.

## Memory System Rules

- Concepts are agent-authored syntheses, not silently auto-generated system facts.
- The system may propose consolidation or synthesis, but explicit tool calls create concepts and project rollups.
- Prefer `memory_seed_session` at session start and `memory_commit_episode` at session close for coding-heavy work.
- When `project` or `project_slug` is provided for recall-style operations, treat it as a hard boundary. Do not widen retrieval across sibling Agent Memory projects.
