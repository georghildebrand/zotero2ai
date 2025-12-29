# WP-A: Packaging & pyproject — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create pyproject.toml with Python 3.12, uv-based dependencies, dev tooling config, and mcp-zotero2ai console script.

**Architecture:** Standard Python package structure with hatchling build backend, uv for dependency management.

**Tech Stack:** Python 3.12+, uv, hatchling, ruff, mypy, pytest

**Dependencies:** None (this is the foundation work package)

---

## Task 1: Initialize uv Project

**Files:**
- Create: `pyproject.toml`

**Step 1: Check current directory structure**

Run:
```bash
ls -la
```

Expected: Should see LICENSE, README.md, .gitignore, src/, tests/ directories

**Step 2: Initialize with uv**

Run:
```bash
uv init --no-readme --no-workspace
```

Expected: Creates basic pyproject.toml (we'll replace it)

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: initialize uv project structure"
```

---

## Task 2: Create Complete pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1: Write complete pyproject.toml**

Replace content of `pyproject.toml`:
```toml
[project]
name = "zotero2ai"
version = "0.1.0"
description = "MCP server for Zotero with hybrid search"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [
    { name = "Georg Hildebrand", email = "georghildebrand@users.noreply.github.com" }
]

dependencies = [
    "platformdirs>=4.0.0",
    "mcp[cli]>=0.9.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.7.0",
]

[project.scripts]
mcp-zotero2ai = "zotero2ai.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 180
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

**Step 2: Verify format**

Run:
```bash
cat pyproject.toml
```

Expected: Shows complete TOML configuration

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: configure pyproject.toml with Python 3.12 and MCP

- Set requires-python >= 3.12
- Add platformdirs and mcp[cli] dependencies
- Configure ruff (py312 target, 180 char line length)
- Configure mypy (strict mode, python 3.12)
- Add dev dependencies (pytest, ruff, mypy)
- Define mcp-zotero2ai console script"
```

---

## Task 3: Create Package Structure

**Files:**
- Create: `src/zotero2ai/__init__.py`

**Step 1: Create package directory**

Run:
```bash
mkdir -p src/zotero2ai
touch src/zotero2ai/__init__.py
```

Expected: Directory created with __init__.py

**Step 2: Add package metadata to __init__.py**

Write to `src/zotero2ai/__init__.py`:
```python
"""zotero2ai - MCP server for Zotero with hybrid search."""

__version__ = "0.1.0"
```

**Step 3: Verify package is importable (will fail, need to sync first)**

Run:
```bash
python3.12 -c "import sys; sys.path.insert(0, 'src'); import zotero2ai; print(zotero2ai.__version__)"
```

Expected: Prints "0.1.0"

**Step 4: Commit**

```bash
git add src/zotero2ai/__init__.py
git commit -m "feat: create zotero2ai package structure

- Add __init__.py with version
- Package ready for module imports"
```

---

## Task 4: Install Dependencies with uv

**Files:**
- Creates: `uv.lock`, `.venv/`

**Step 1: Sync all dependencies**

Run:
```bash
uv sync --all-extras
```

Expected: Creates uv.lock, installs all dependencies including dev extras

**Step 2: Verify installation**

Run:
```bash
uv run python -c "import zotero2ai; print(zotero2ai.__version__)"
```

Expected: Prints "0.1.0"

**Step 3: Verify MCP is available**

Run:
```bash
uv run python -c "import mcp; print('MCP installed')"
```

Expected: Prints "MCP installed"

**Step 4: Verify dev tools**

Run:
```bash
uv run ruff --version
uv run mypy --version
uv run pytest --version
```

Expected: All tools print their versions

**Step 5: Commit lock file**

```bash
git add uv.lock
git commit -m "build: lock dependencies with uv

- Add uv.lock with pinned versions
- Verify all dependencies install correctly"
```

---

## Task 5: Verify Package Import

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_package.py`

**Step 1: Create tests directory structure**

Run:
```bash
mkdir -p tests
touch tests/__init__.py
```

Expected: tests/ directory with __init__.py

**Step 2: Write package import test**

Create `tests/test_package.py`:
```python
"""Test package imports and metadata."""

import zotero2ai


def test_package_has_version() -> None:
    """Test that package has __version__ attribute."""
    assert hasattr(zotero2ai, "__version__")
    assert isinstance(zotero2ai.__version__, str)
    assert zotero2ai.__version__ == "0.1.0"
```

**Step 3: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_package.py -v
```

Expected: PASS - test_package_has_version

**Step 4: Commit**

```bash
git add tests/__init__.py tests/test_package.py
git commit -m "test: add package import verification test

- Verify zotero2ai imports correctly
- Verify __version__ is set"
```

---

## Task 6: Create .python-version for uv

**Files:**
- Create: `.python-version`

**Step 1: Create .python-version**

Run:
```bash
echo "3.12" > .python-version
```

Expected: File created with "3.12"

**Step 2: Verify uv respects it**

Run:
```bash
uv run python --version
```

Expected: Shows Python 3.12.x

**Step 3: Commit**

```bash
git add .python-version
git commit -m "build: pin Python 3.12 with .python-version

- Ensure uv uses Python 3.12
- Consistent across environments"
```

---

## Definition of Done (WP-A)

✅ `pyproject.toml` exists with:
  - `requires-python = ">=3.12"`
  - `mcp[cli]>=0.9.0` dependency
  - `platformdirs>=4.0.0` dependency
  - Dev dependencies (pytest, ruff, mypy)
  - Console script: `mcp-zotero2ai`
  - Ruff configured for py312, 180 char lines
  - MyPy configured for strict mode, python 3.12

✅ `src/zotero2ai/__init__.py` exists with `__version__ = "0.1.0"`

✅ `uv.lock` committed with locked dependencies

✅ `.python-version` pins Python 3.12

✅ `uv sync --all-extras` succeeds

✅ `uv run python -c "import zotero2ai"` succeeds

✅ Basic package import test passes

---

## Handoff to Next Work Package

**Outputs for WP-B (Config) and WP-C (Logging):**
- ✅ Package structure in place (`src/zotero2ai/`)
- ✅ Dependencies installed (`platformdirs`, test framework)
- ✅ `uv sync --all-extras` works
- ✅ Can run tests with `uv run pytest`

**Outputs for WP-E (Makefile):**
- ✅ `uv` is the package manager
- ✅ All dependencies defined in pyproject.toml
