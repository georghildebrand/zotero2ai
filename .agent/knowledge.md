# Agent Knowledge: zotero2ai

## Project Overview
`zotero2ai` is a **Model Context Protocol (MCP)** server that connects AI agents to a local Zotero library.
It allows agents to search papers, list collections, and perform full CRUD operations on notes.

### Architecture
It uses a **Hybrid Architecture**:
1.  **Python MCP Server** (`src/zotero2ai`): Runs locally, handles MCP requests from the AI.
2.  **Zotero Plugin** (`plugin/zotero-mcp-bridge`): A JavaScript plugin running *inside* Zotero.
    *   This plugin exposes a local HTTP server (default port `23119` or `23120`).
    *   The Python MCP server talks to this plugin via HTTP to perform actions.
    *   This bypasses direct SQLite DB access, preventing lock errors.

### Key File Locations
*   **MCP Server Code**: `src/zotero2ai/`
    *   `server.py`: Main entry point and tool definitions.
*   **Zotero Plugin Code**: `plugin/zotero-mcp-bridge/content/`
    *   `handlers.js`: Main request handling logic (API endpoints).
    *   `utils.js`: Helper functions.
*   **Docs & Plans**: `docs/plans/`

### Build & Run Instructions
*   **Dependency Management**: Uses `uv`.
*   **Setup**: `make install`
*   **Check Status**: `make doctor`
*   **Run Server**: `make run`
*   **Build Plugin**: `cd plugin && ./build.sh` (builds `.xpi` file)

---

- **get_collection_tree(depth)**: Returns nested JSON tree of collections + items.
- **read_item_content(key)**: Returns full text constraint of PDF/Note/Snapshot.
- **open_item(key)**: Opens attachment in local OS viewer.
- **search_papers(query, collection_key)**: Supports filtering by collection.
- **export_collection_to_markdown(key)**: Dumps collection to MD file.

### Active Plans
- **Status**: Regression Fixed. Improvements 1-4 implemented.
- **Next**: Verify user restart of MCP server.

## Active Initiative: Bridge Improvements (Jan 2026)
We are currently implementing 5 major improvements to the Zotero MCP Bridge.
**Master Plan**: `docs/plans/agentic-workflow-improvements.md`
**Status**: Ready for Implementation (Parallel Jobs Initiated).

### The 5 Targeted Improvements
1.  **list_collection_children (Job 3)**: New tool to list immediate children only (saves 70% tokens).
2.  **Pagination (Job 1)**: Fix "Missing Folder" bug by implementing `limit`/`start` in `handlers.js`.
3.  **Fuzzy Search (Job 2)**: Improve search scoring for partial matches.
4.  **Error Handling (Job 2)**: Prevent 500 errors on bad metadata (Graceful Degradation).
5.  **Caching (Job 4)**: In-memory cache to prevent connection resets (Run LAST).

### Execution Strategy
The work is split into **Parallel Job Packets** located in `docs/plans/agent_prompts/`:
*   `job_1_pagination.md` -> **Run Now**
*   `job_2_error_handling.md` -> **Run Now**
*   `job_3_search_scoring.md` -> **Run Now**
*   *Caching (No prompt yet)* -> **Run After Above Complete**

---

## Antigravity Config
The global MCP configuration for Antigravity is at: `~/.gemini/antigravity/mcp_config.json`
To register `zotero2ai` with Claude/Antigravity:
```bash
claude mcp add zotero2ai --scope user -e ZOTERO_MCP_TOKEN="your_token" -- $(which uv) --directory $(pwd) run mcp-zotero2ai run
```
