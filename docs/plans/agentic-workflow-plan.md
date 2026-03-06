# Implementation Plan: JIT Workflow Architecture for zotero2ai

## Objective
Reduce "Token-Spam" in the MCP context and enable complex Agentic Workflows by using a "Just-In-Time" (JIT) approach. Instead of pushing all tool definitions and logic into the system prompt, we provide a discovery mechanism for Markdown-based workflow templates.

## Architecture Change
- **MCP Server (Infrastructure):** Provides basic CRUD tools and discovery tools for workflows.
- **Markdown Templates (Logic):** Stored in the filesystem, providing step-by-step instructions for the AI on how to solve complex Zotero tasks.

## Implementation Steps

### 1. Infrastructure Setup
- [ ] Create directory: `src/zotero2ai/workflows/`
- [ ] Add `__init__.py` to make it a package (optional, for resource loading).

### 2. MCP Server Enhancements (`src/zotero2ai/mcp_server/server.py`)
- [ ] Implement `list_workflow_templates` tool:
    - Scans the `workflows/` directory.
    - Returns a list of available workflows with a short 1-sentence description (extracted from the MD frontmatter or first line).
- [ ] Implement `get_workflow_template` tool:
    - Takes a `workflow_name` as input.
    - Reads the corresponding `.md` file.
    - Returns the full content to the AI.

### 3. Core Workflow Templates
- [ ] **`literature_review.md`**: Guide for searching, reading, and synthesizing multiple papers into a note.
- [ ] **`smart_tagging.md`**: Strategy for analyzing abstracts and suggesting taxonomy-compliant tags.
- [ ] **`collection_cleanup.md`**: Steps for finding duplicates or misplaced items in the collection tree.

### 4. Optimization (Context Trimming)
- [ ] Review all existing tools in `server.py`.
- [ ] Shorten descriptions to the bare minimum.
- [ ] Remove redundant fields from tool outputs (e.g., unnecessary Zotero metadata).

### 5. Documentation & Prompting
- [ ] Add a "Meta-Instruction" to the MCP Server's info or a separate resource.
- [ ] Tell the AI to prefer checking `list_workflow_templates` for complex tasks instead of guessing sequences of atomic tools.

## Success Criteria
- [ ] Initial MCP context size is reduced.
- [ ] AI can successfully discover and follow a multi-step workflow from an MD file.
- [ ] Workflow logic can be edited without restarting the MCP server or changing Python code.
