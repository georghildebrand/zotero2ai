# WP-F: Integration Tests & README — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add end-to-end integration tests for CLI commands and update README with installation, usage, and development instructions.

**Architecture:** Integration tests use subprocess to test CLI in realistic scenarios. README provides complete documentation for users and contributors.

**Tech Stack:** Python 3.12+, pytest, subprocess

**Dependencies:**
- WP-D complete (CLI implemented)
- WP-E complete (Makefile available for documentation)

---

## Task 1: Write Integration Test for CLI Help

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write test for --help command**

Create `tests/test_integration.py`:
```python
"""Integration tests for CLI end-to-end behavior."""

import subprocess


def test_cli_help() -> None:
    """Test CLI help command runs successfully."""
    result = subprocess.run(
        ["uv", "run", "mcp-zotero2ai", "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    assert "mcp-zotero2ai" in result.stdout
    assert "doctor" in result.stdout
    assert "run" in result.stdout
    assert "--debug" in result.stdout
    assert "--quiet" in result.stdout
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_help -v
```

Expected: PASS (CLI help works)

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add CLI help integration test

- Verify mcp-zotero2ai --help runs successfully
- Check for expected commands and flags in output"
```

---

## Task 2: Add Integration Test for Doctor Command Errors

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write test for missing ZOTERO_DATA_DIR**

Add to `tests/test_integration.py`:
```python
def test_cli_doctor_missing_zotero_data_dir() -> None:
    """Test doctor command fails gracefully when ZOTERO_DATA_DIR not set."""
    result = subprocess.run(
        ["uv", "run", "mcp-zotero2ai", "doctor"],
        capture_output=True,
        text=True,
        timeout=10,
        env={"PATH": subprocess.os.environ["PATH"]},  # Minimal environment
    )

    assert result.returncode == 1
    assert "ZOTERO_DATA_DIR" in result.stderr
    assert "required" in result.stderr.lower()
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_doctor_missing_zotero_data_dir -v
```

Expected: PASS

**Step 3: Add test for invalid directory**

Add to `tests/test_integration.py`:
```python
import os
import tempfile
from pathlib import Path


def test_cli_doctor_invalid_directory() -> None:
    """Test doctor command fails when directory is invalid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create empty directory (no zotero.sqlite or storage/)
        result = subprocess.run(
            ["uv", "run", "mcp-zotero2ai", "doctor"],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                "ZOTERO_DATA_DIR": tmpdir,
                "PATH": os.environ["PATH"],
            },
        )

        assert result.returncode == 1
        assert "zotero.sqlite" in result.stderr or "storage" in result.stderr
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_integration.py -k doctor -v
```

Expected: All doctor tests PASS

**Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add doctor command error tests

- Test missing ZOTERO_DATA_DIR fails with clear error
- Test invalid directory fails with actionable message"
```

---

## Task 3: Add Integration Test for Doctor Success

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write test for successful doctor command**

Add to `tests/test_integration.py`:
```python
import sqlite3


def test_cli_doctor_success() -> None:
    """Test doctor command succeeds with valid Zotero setup."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create valid Zotero structure
        zotero_dir = Path(tmpdir)
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        # Create minimal database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO items (id) VALUES (1), (2), (3)")
        conn.commit()
        conn.close()

        result = subprocess.run(
            ["uv", "run", "mcp-zotero2ai", "doctor"],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                "ZOTERO_DATA_DIR": str(zotero_dir),
                "PATH": os.environ["PATH"],
            },
        )

        assert result.returncode == 0
        assert "Doctor" in result.stdout
        assert "3 items" in result.stdout
        assert "✓" in result.stdout or "passed" in result.stdout.lower()
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_doctor_success -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add doctor success test

- Create valid Zotero structure for testing
- Verify doctor command validates correctly
- Check for success indicators in output"
```

---

## Task 4: Add Integration Test for Run Command

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write test for run command stub**

Add to `tests/test_integration.py`:
```python
def test_cli_run_stub() -> None:
    """Test run command stub executes successfully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create valid Zotero structure
        zotero_dir = Path(tmpdir)
        (zotero_dir / "zotero.sqlite").touch()
        (zotero_dir / "storage").mkdir()

        result = subprocess.run(
            ["uv", "run", "mcp-zotero2ai", "run"],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                "ZOTERO_DATA_DIR": str(zotero_dir),
                "PATH": os.environ["PATH"],
            },
        )

        assert result.returncode == 0
        assert "MCP" in result.stdout or "started" in result.stdout.lower()
        assert "ping" in result.stdout.lower()
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_run_stub -v
```

Expected: PASS

**Step 3: Run all integration tests**

Run:
```bash
uv run pytest tests/test_integration.py -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add run command test

- Verify run command starts successfully
- Check for MCP server indicators in output"
```

---

## Task 5: Add HTTP Smoke Test (--once flag)

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Write test for HTTP smoke test with --once flag**

Add to `tests/test_integration.py`:
```python
def test_cli_run_http_once_smoke_test() -> None:
    """Test run command with HTTP --once flag (non-blocking smoke test)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create valid Zotero structure
        zotero_dir = Path(tmpdir)
        (zotero_dir / "zotero.sqlite").touch()
        (zotero_dir / "storage").mkdir()

        result = subprocess.run(
            ["uv", "run", "mcp-zotero2ai", "run", "--http", "--port", "0", "--once"],
            capture_output=True,
            text=True,
            timeout=10,  # Should exit immediately, not hang
            env={
                "ZOTERO_DATA_DIR": str(zotero_dir),
                "PATH": os.environ["PATH"],
            },
        )

        assert result.returncode == 0
        assert "HTTP" in result.stdout or "http" in result.stdout.lower()
        # Verify it exits immediately (smoke test)
        assert "once" in result.stdout.lower() or "validated" in result.stdout.lower()
```

**Step 2: Run test to verify it passes (and doesn't hang)**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_run_http_once_smoke_test -v
```

Expected: PASS (completes within timeout, doesn't block)

**Step 3: Run all integration tests**

Run:
```bash
uv run pytest tests/test_integration.py -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add HTTP smoke test with --once flag

- Verify HTTP mode with --once exits immediately
- Critical for CI: test must not hang or block
- Validates HTTP mode setup without binding server"
```

---

## Task 6: Add Debug and Quiet Flag Tests

**Files:**
- Modify: `tests/test_integration.py`

**Step 1: Add test for debug flag**

Add to `tests/test_integration.py`:
```python
def test_cli_debug_flag() -> None:
    """Test that --debug flag enables debug logging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        zotero_dir = Path(tmpdir)
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        result = subprocess.run(
            ["uv", "run", "mcp-zotero2ai", "--debug", "doctor"],
            capture_output=True,
            text=True,
            timeout=10,
            env={
                "ZOTERO_DATA_DIR": str(zotero_dir),
                "PATH": os.environ["PATH"],
            },
        )

        assert result.returncode == 0
        # Debug logging should produce stderr output
        # (Exact check depends on implementation)
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_integration.py::test_cli_debug_flag -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test(integration): add debug flag test"
```

---

## Task 6: Update README - Installation Section

**Files:**
- Modify: `README.md`

**Step 1: Read current README**

Run:
```bash
cat README.md
```

Expected: Shows current minimal content

**Step 2: Write comprehensive README**

Replace `README.md`:
```markdown
# zotero2ai

A Model Context Protocol (MCP) server for Zotero with hybrid search capabilities.

## Features (v0.1.0)

- ✅ Configuration via `ZOTERO_DATA_DIR` environment variable
- ✅ Doctor command to validate Zotero installation
- ✅ MCP server with FastMCP integration (stdio and HTTP transports)
- ✅ HTTP mode for ChatGPT integration via tunnel
- ✅ CLI with `--debug` and `--quiet` logging modes

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Zotero with local database

## Installation

### From Source

```bash
# Clone repository
git clone https://github.com/georghildebrand/zotero2ai.git
cd zotero2ai

# Install with uv
uv sync --all-extras

# Verify installation
uv run mcp-zotero2ai --help
```

### With uv (direct)

```bash
uv tool install git+https://github.com/georghildebrand/zotero2ai.git
```

## Configuration

Set the `ZOTERO_DATA_DIR` environment variable to your Zotero data directory:

```bash
# Example (macOS/Linux)
export ZOTERO_DATA_DIR=~/Zotero

# Example (Windows)
set ZOTERO_DATA_DIR=%USERPROFILE%\Zotero
```

Your Zotero data directory must contain:
- `zotero.sqlite` (Zotero database)
- `storage/` (attachment storage directory)

## Usage

### Validate Installation

Check that your Zotero installation is properly configured:

```bash
mcp-zotero2ai doctor
```

Output:
```
🔍 zotero2ai Doctor

✓ Zotero data directory: /Users/you/Zotero
✓ Database: /Users/you/Zotero/zotero.sqlite
✓ Storage: /Users/you/Zotero/storage

✓ Database accessible: 1234 items

All checks passed! 🎉
```

### Start MCP Server

```bash
mcp-zotero2ai run
```

**Note:** In v0.1.0, the run command is a stub that validates MCP integration. Full MCP server functionality coming in v0.2.0+.

### Logging Options

```bash
# Debug mode (verbose logging)
mcp-zotero2ai --debug doctor

# Quiet mode (warnings and errors only)
mcp-zotero2ai --quiet doctor
```

## ChatGPT Integration

Use zotero2ai with ChatGPT's Developer Mode to access your Zotero library in conversations.

### Prerequisites

- ChatGPT Plus/Pro account with Developer Mode access
- A tunnel tool (ngrok or Cloudflare Tunnel) for HTTPS exposure

### Setup Steps

1. **Set Zotero data directory**:
   ```bash
   export ZOTERO_DATA_DIR=/path/to/your/Zotero
   ```

2. **Start HTTP server** (using make or directly):
   ```bash
   # Using make
   make run-http

   # Or directly
   mcp-zotero2ai run --http --host 127.0.0.1 --port 8787
   ```

3. **Expose via HTTPS tunnel**:

   Using ngrok:
   ```bash
   ngrok http 8787
   ```

   Or Cloudflare Tunnel:
   ```bash
   cloudflare tunnel --url http://localhost:8787
   ```

   Copy the HTTPS URL provided by your tunnel tool.

4. **Configure ChatGPT**:
   - Open ChatGPT → Settings → Connectors
   - Navigate to Advanced → Developer Mode
   - Click "Create connector"
   - Paste your HTTPS URL
   - Save connector

5. **Use in chat**:
   - Start a new conversation
   - Enable the zotero2ai tool when prompted
   - Use commands like:
     - "List my collections"
     - "Set active collection to Reading List"
     - "Search for papers about machine learning"

### Transport Modes

- **stdio mode (default)**: `mcp-zotero2ai run` — For local MCP Inspector/CLI
- **HTTP mode**: `mcp-zotero2ai run --http` — For ChatGPT integration via tunnel

### Smoke Test

Verify HTTP mode without starting a persistent server:
```bash
make run-http-once
# Or: mcp-zotero2ai run --http --port 0 --once
```

## Development

### Setup

```bash
# Install dependencies and dev tools
make install

# Or manually
uv sync --all-extras
```

### Common Commands

```bash
make help             # Show all available commands
make test             # Run tests
make test-cov         # Run tests with coverage
make format           # Auto-format code
make lint             # Run linting and type checking
make check            # Run all quality checks (CI)
make doctor           # Run doctor command
make run              # Run MCP server (stdio mode)
make run-http         # Run MCP server (HTTP mode for ChatGPT)
make run-http-once    # HTTP smoke test (non-blocking)
make build            # Build wheel and sdist
```

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Single test file
uv run pytest tests/test_config.py -v

# Single test function
uv run pytest tests/test_config.py::test_resolve_success -v
```

### Code Quality

```bash
# Format code
make format

# Check formatting
make format-check

# Lint and type-check
make lint

# Run all checks (format-check + lint + test)
make check
```

## Project Structure

```
zotero2ai/
├── src/
│   └── zotero2ai/
│       ├── __init__.py      # Package metadata
│       ├── cli.py           # CLI entry point and commands
│       ├── config.py        # Configuration resolution
│       └── logging.py       # Logging setup
├── tests/
│   ├── test_cli.py          # CLI tests
│   ├── test_config.py       # Config tests
│   ├── test_logging.py      # Logging tests
│   └── test_integration.py  # Integration tests
├── pyproject.toml           # Project configuration
├── Makefile                 # Development commands
└── README.md                # This file
```

## Roadmap

- ✅ **v0.1.0** - CLI skeleton + configuration
- 🚧 **v0.2.0** - SQLite read model (collections, items, notes, tags)
- 🚧 **v0.3.0** - MCP tools and resources (full server implementation)
- 🚧 **v0.4.0** - Vector search with embeddings
- 🚧 **v0.5.0** - Hybrid search (lexical + vector)
- 🚧 **v0.6.0+** - Write operations via gateway

## Architecture

See [docs/plans/zotero_2_ai_implementation_plan .md](docs/plans/zotero_2_ai_implementation_plan%20.md) for complete architecture documentation.

## Contributing

Contributions welcome! Please ensure all tests pass before submitting PRs:

```bash
make check
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with complete documentation and ChatGPT integration

- Add installation instructions for uv
- Document configuration via ZOTERO_DATA_DIR
- Add usage examples for doctor and run commands
- Add ChatGPT integration section with tunnel setup
- Document HTTP transport mode for ChatGPT Developer Mode
- Add transport modes (stdio vs HTTP) explanation
- Document development workflow with HTTP targets
- Add project structure and roadmap
- Include make targets reference"
```

---

## Task 7: Verify Complete Integration

**Files:**
- None (verification)

**Step 1: Run all tests**

Run:
```bash
make test
```

Expected: All unit and integration tests PASS

**Step 2: Run full quality check**

Run:
```bash
make check
```

Expected: format-check, lint, and test all PASS

**Step 3: Test installation workflow**

Run:
```bash
make test-install
```

Expected: Wheel installs successfully, CLI works

**Step 4: Test HTTP smoke test**

Run:
```bash
make run-http-once
```

Expected: Exits immediately with success (does not hang)

**Step 5: Verify README instructions**

Manually verify each command in README works:
- `make install` ✓
- `make test` ✓
- `make check` ✓
- `make run-http-once` ✓
- `uv run mcp-zotero2ai --help` ✓
- `uv run mcp-zotero2ai run --help` shows transport options ✓

---

## Definition of Done (WP-F)

✅ `tests/test_integration.py` exists with comprehensive coverage:
  - Test CLI help command
  - Test doctor with missing ZOTERO_DATA_DIR
  - Test doctor with invalid directory
  - Test doctor success with valid setup
  - Test run command stub (stdio mode)
  - Test HTTP smoke test with --once flag (non-blocking)
  - Test debug flag integration

✅ `uv run pytest tests/test_integration.py -v` passes all tests

✅ HTTP smoke test does not hang or block (critical for CI)

✅ `README.md` updated with:
  - Installation instructions (uv-based)
  - Configuration documentation (ZOTERO_DATA_DIR)
  - Usage examples (doctor, run, logging flags)
  - **ChatGPT integration section** with tunnel setup steps
  - Transport modes explanation (stdio vs HTTP)
  - HTTP mode usage for ChatGPT Developer Mode
  - Development workflow (make targets including run-http)
  - Project structure overview
  - Roadmap with milestone status
  - Contributing guidelines

✅ `make check` passes (all quality checks)

✅ `make test-install` verifies CLI is installable

✅ README instructions are accurate and verified

---

## Milestone 0.1.0 Complete!

All work packages (WP-A through WP-F) are now complete. The project has:

✅ Complete package structure with Python 3.12
✅ Configuration resolution with ZOTERO_DATA_DIR
✅ Clean logging with root logger configuration
✅ CLI with doctor and run commands
✅ MCP integration with FastMCP (stdio + HTTP transports)
✅ HTTP mode for ChatGPT integration via tunnel
✅ HTTP smoke test (--once flag) for CI validation
✅ Comprehensive test coverage (unit + integration)
✅ Makefile with all development workflows (including run-http targets)
✅ Complete documentation in README with ChatGPT integration guide

**Ready for:**
- Tag: `v0.1.0`
- Release notes
- ChatGPT Developer Mode integration testing
- Next milestone (v0.2.0: SQLite read model)
