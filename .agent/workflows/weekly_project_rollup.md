---
description: Weekly rollup for consolidating project concepts into a project-level state-of-play
workflow_type: task_sop
status: active
schedule_hint: weekly
---

# Weekly Project Rollup

Use this workflow once per week for a project-level synthesis. This is the right place to roll concepts upward into a `project` memory item.

## 1. Establish Project Scope
- Call `memory_inspect` and confirm the target project.
- Use one weekly window, usually the last 7 days.

## 2. Gather The Current Concept Layer
- Call `memory_recall(project=..., limit=...)` and focus on recent concept-level memories.
- Use `memory_overview(project_slug=...)` if you need graph and timeline context before writing.
- If concept duplication is visible, run `memory_consolidate_concepts(project=...)` first.

## 3. Resolve Concept-Level Drift Before Rollup
- If two concepts clearly represent the same topic, propose or perform a concept synthesis first.
- Do not write a project rollup on top of unresolved concept drift unless you explicitly note the uncertainty.

## 4. Write The Weekly Project Summary
- Use `memory_synthesize(..., mem_class="project")` or `memory_create_item(mem_class="project", ...)`.
- The project-level item should capture:
- current state of play
- major decisions
- strategic changes
- open risks
- next likely actions

## 5. Keep The Project Layer Sparse
- Create at most one canonical weekly rollup for the time window.
- If an earlier rollup for the same week exists and is wrong or incomplete, use `memory_supersede` instead of writing another active parallel version.

## Exit Criteria
- The project has a current weekly state-of-play item.
- Concept drift that materially affects the summary is either resolved or explicitly called out.
- The rollup helps a future agent onboard quickly without scanning all raw units.
