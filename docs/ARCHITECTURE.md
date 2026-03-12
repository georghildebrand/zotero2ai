# Architecture

zotero2ai follows a modular architecture designed for local-first, read-only integration with Zotero and AI services via the Model Context Protocol (MCP).

## System Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Researcher  │───▶│  AI Client   │───▶│ zotero2ai   │
└─────────────┘    └──────────────┘    └─────────────┘
                          │                   │
                          │                   ▼
                          │           ┌──────────────┐
                          │           │ Zotero SQLite │
                          │           └──────────────┘
                          │                   │
                          ▼                   ▼
                  ┌──────────────┐    ┌──────────────┐
                  │ FTS5 Index   │    │ Zotero Storage│
                  └──────────────┘    └──────────────┘
```

## Core Modules

```
src/zotero2ai/
├── cli.py             # Entry point, argument parsing, orchestration
├── config.py          # ZOTERO_DATA_DIR resolution and validation
├── logging.py         # Root logging configuration
│
├── zotero/            # Zotero-specific logic
│   ├── db.py          # Read-only SQLite access
│   ├── models.py      # Item, Note, Collection data models
│   ├── collections.py # Collection hierarchy and path resolution
│   ├── items.py       # Metadata fetching
│   └── text.py        # Text assembly for indexing
│
└── mcp_server/        # MCP Interface
    ├── server.py      # FastMCP initialization and tool definitions
    └── schemas.py     # MCP tool input/output schemas
```

### Module Responsibilities

- **CLI Module** (`cli.py`): Command-line interface with `doctor` (diagnostic) and `run` (MCP server) commands.
- **Config Module** (`config.py`): Handles environment variable resolution and path validation for the Zotero data directory.
- **Zotero Module** (`zotero/`): Encapsulates all direct interactions with the Zotero database. It uses a read-only SQLite connection to ensure data integrity.
- **Search Layer** (in `zotero/search_index.py`): Implements a single-file SQLite FTS5 index (BM25) for titles, abstracts, notes, tags, and collections. Rebuilds when Zotero DB mtime changes.
- **MCP Server Module** (`mcp_server/`): Bridges the core logic to the AI Client using the Model Context Protocol, allowing tools like `search` or `get_item` to be used by LLMs.

## Data Flow

1. **Initialization**: CLI resolves `ZOTERO_DATA_DIR` → Configures Logging → Starts MCP Server.
2. **Indexing**: On-demand process scans Zotero DB → flattens collections/items/notes → writes to SQLite FTS5 sidecar (`search_index.db`) with BM25 ranking.
3. **Querying**: AI Client sends `search` tool call → MCP Server uses FTS5 (lexical BM25) to rank results → returns titles/keys/tags.

## Architecture Diagrams

The project includes comprehensive C4 model diagrams in `/docs/architecture/c4/`:

- **01-system-context**: High-level system interactions and external boundaries.
- **02-container-diagram**: Internal module architecture and technology choices.
- **03-component-diagram**: Detailed relationships between internal components.
- **04-dev-workflow**: Development process, testing, and tooling.

Generate/view diagrams using PlantUML or compatible viewers.
