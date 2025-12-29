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
                  │ Vector Index │    │ Zotero Storage│
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
├── index/             # Local search logic
│   ├── store.py       # FAISS index IO and metadata storage
│   ├── embedder.py    # Sentence-transformers wrapper
│   ├── pipeline.py    # Incremental indexing logic
│   └── hybrid.py      # Hybrid (lexical + vector) scoring
│
└── mcp_server/        # MCP Interface
    ├── server.py      # FastMCP initialization and tool definitions
    └── schemas.py     # MCP tool input/output schemas
```

### Module Responsibilities

- **CLI Module** (`cli.py`): Command-line interface with `doctor` (diagnostic) and `run` (MCP server) commands.
- **Config Module** (`config.py`): Handles environment variable resolution and path validation for the Zotero data directory.
- **Zotero Module** (`zotero/`): Encapsulates all direct interactions with the Zotero database. It uses a read-only SQLite connection to ensure data integrity.
- **Index Module** (`index/`): Implements a local vector database using FAISS. It handles the transformation of Zotero items into searchable embeddings.
- **MCP Server Module** (`mcp_server/`): Bridges the core logic to the AI Client using the Model Context Protocol, allowing tools like `search` or `get_item` to be used by LLMs.

## Data Flow

1. **Initialization**: CLI resolves `ZOTERO_DATA_DIR` → Configures Logging → Starts MCP Server.
2. **Indexing**: Background or on-demand process scans Zotero DB → Assembles text → Generates embeddings via Embedder → Updates FAISS Store.
3. **Querying**: AI Client sends `search` tool call → MCP Server calls Hybrid Search → Hybrid Search combines FAISS results with metadata lookups → Ranked results returned to AI.

## Architecture Diagrams

The project includes comprehensive C4 model diagrams in `/docs/architecture/c4/`:

- **01-system-context**: High-level system interactions and external boundaries.
- **02-container-diagram**: Internal module architecture and technology choices.
- **03-component-diagram**: Detailed relationships between internal components.
- **04-dev-workflow**: Development process, testing, and tooling.

Generate/view diagrams using PlantUML or compatible viewers.
