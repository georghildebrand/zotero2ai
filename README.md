# zotero2ai

A Model Context Protocol (MCP) server for Zotero with local hybrid search (lexical + vector).

## Overview

`zotero2ai` allows AI agents to interact with your local Zotero library. It provides tools for searching items, notes, and collections, and serves as a bridge between your research data and LLMs.

### Key Features (Milestone 0.1.0)

- **Read-only SQLite Access**: Safely reads Zotero data without modifying your database.
- **Configurable**: Simple setup via `ZOTERO_DATA_DIR`.
- **CLI Diagnostics**: Built-in `doctor` command to verify your environment.
- **MCP Server**: FastMCP-based server implementation.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone https://github.com/georghildebrand/zotero2ai.git
cd zotero2ai

# Install dependencies and set up virtual environment
make install
```

## Configuration

The only required configuration is the path to your Zotero data directory.

```bash
export ZOTERO_DATA_DIR="/Users/yourname/Zotero"
```

If not provided, the application will attempt to find it at `~/Zotero` or `~/zotero`.

## Usage

### Diagnostics

Check if your Zotero setup is compatible and accessible:

```bash
make doctor
```

### Run MCP Server

Start the MCP server:

```bash
make run
```

### ChatGPT Desktop Integration

To integrate with ChatGPT Desktop, run the automated setup script:

```bash
./scripts/setup-chatgpt-desktop.sh
```

This will:
- Auto-detect your Zotero data directory
- Generate the MCP configuration
- Install it in the correct location for ChatGPT Desktop

For manual setup or troubleshooting, see [ChatGPT Desktop Integration Guide](docs/CHATGPT_DESKTOP_INTEGRATION.md).

### Command Line Interface

You can also use the CLI directly:

```bash
uv run mcp-zotero2ai --help
```

## Development

The `Makefile` provides several utility targets for development and quality assurance:

| Target | Description |
|--------|-------------|
| `make install` | Set up development environment and install dependencies. |
| `make doctor` | Run diagnostics to check Zotero configuration. |
| `make run` | Start the MCP server. |
| `make test` | Run the test suite. |
| `make check` | Canonical quality gate (format-check + lint + test). |
| `make lint` | Run Ruff linter and Mypy type checker. |
| `make format` | Auto-format code using Ruff. |
| `make build` | Build the wheel and source distribution. |
| `make test-install` | Verify the built wheel installs and runs correctly in an isolated environment. |
| `make clean` | Remove build artifacts and caches. |

## License

MIT
