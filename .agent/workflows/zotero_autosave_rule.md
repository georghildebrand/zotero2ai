---
description: Zotero Agent Memory Autosave Trigger
---

When working on any project, you have access to the `zotero2ai` tools to update the user's Zotero agent memory pack.

**AUTOSAVE TRIGGER RULE**:
You MUST call `memory_create_item` automatically (without waiting for the user to ask) whenever:
1. You identify a bug and successfully resolve it (save as a `result` or `observation` unit).
2. The user makes a definitive architectural, design, or project-planning decision.
3. You reach the end of an experimental iteration or resolve a hypothesis.
4. The user drops a major piece of lore, context, or credentials that you will likely need later.

**How to auto-save:**
Use the `memory_create_item` tool. Set `mem_class` to `unit` and `role` to `observation` or `result`. Set `project` to the current active project, and derive an appropriate domain tag (e.g., `mem:domain:physics` or `mem:domain:software-development`). Make sure the title is a short, descriptive label and the `content` is highly detailed yet atomic.

> [!NOTE] 
> Creating 'concept' and 'synthesis' memories DOES require user confirmation. However, basic 'unit' items under this autosave rule do NOT require permission.
