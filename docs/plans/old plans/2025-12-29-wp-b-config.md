# WP-B: Config Module — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement config.py with ZOTERO_DATA_DIR resolution (required env var), validation, and ZoteroConfig dataclass.

**Architecture:** Single config module with resolve function and dataclass for validated paths. ZOTERO_DATA_DIR is required (no autodiscovery fallback per updated spec).

**Tech Stack:** Python 3.12+, pathlib, platformdirs, dataclasses

**Dependencies:** WP-A must be complete (package structure, dependencies installed)

---

## Task 1: Write Failing Test for Required ZOTERO_DATA_DIR

**Files:**
- Create: `tests/test_config.py`

**Step 1: Write test for missing env var**

Create `tests/test_config.py`:
```python
"""Tests for config module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from zotero2ai.config import resolve_zotero_data_dir


def test_resolve_requires_zotero_data_dir() -> None:
    """Test that ZOTERO_DATA_DIR is required."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="ZOTERO_DATA_DIR"):
            resolve_zotero_data_dir()
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_config.py::test_resolve_requires_zotero_data_dir -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'zotero2ai.config'"

**Step 3: Create minimal stub to get ImportError gone**

Create `src/zotero2ai/config.py`:
```python
"""Configuration resolution for zotero2ai."""


def resolve_zotero_data_dir() -> None:
    """Stub."""
    pass
```

**Step 4: Run test again**

Run:
```bash
uv run pytest tests/test_config.py::test_resolve_requires_zotero_data_dir -v
```

Expected: FAIL with test assertion error (function doesn't raise ValueError)

**Step 5: Commit**

```bash
git add src/zotero2ai/config.py tests/test_config.py
git commit -m "test(config): add failing test for required ZOTERO_DATA_DIR"
```

---

## Task 2: Implement Basic ZOTERO_DATA_DIR Resolution

**Files:**
- Modify: `src/zotero2ai/config.py`

**Step 1: Implement resolution logic**

Modify `src/zotero2ai/config.py`:
```python
"""Configuration resolution for zotero2ai."""

import os
from pathlib import Path


def resolve_zotero_data_dir() -> Path:
    """
    Resolve ZOTERO_DATA_DIR from environment variable.

    ZOTERO_DATA_DIR is required - no autodiscovery fallback.

    Returns:
        Path: Resolved Zotero data directory

    Raises:
        ValueError: If ZOTERO_DATA_DIR is not set
    """
    env_dir = os.environ.get("ZOTERO_DATA_DIR")
    if not env_dir:
        raise ValueError(
            "ZOTERO_DATA_DIR environment variable is required.\n"
            "Set it to your Zotero data directory path.\n"
            "Example: export ZOTERO_DATA_DIR=~/Zotero"
        )

    return Path(env_dir)
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_config.py::test_resolve_requires_zotero_data_dir -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/zotero2ai/config.py
git commit -m "feat(config): implement ZOTERO_DATA_DIR resolution

- Require ZOTERO_DATA_DIR env var (no autodiscovery)
- Fail with actionable error if not set"
```

---

## Task 3: Add Validation for zotero.sqlite and storage/

**Files:**
- Modify: `tests/test_config.py`
- Modify: `src/zotero2ai/config.py`

**Step 1: Write test for valid directory structure**

Add to `tests/test_config.py`:
```python
def test_resolve_validates_directory_structure(tmp_path: Path) -> None:
    """Test that directory must contain zotero.sqlite and storage/."""
    zotero_dir = tmp_path / "Zotero"
    zotero_dir.mkdir()

    # Missing both files
    with patch.dict(os.environ, {"ZOTERO_DATA_DIR": str(zotero_dir)}):
        with pytest.raises(FileNotFoundError, match="zotero.sqlite"):
            resolve_zotero_data_dir()


def test_resolve_validates_storage_directory(tmp_path: Path) -> None:
    """Test that storage/ directory must exist."""
    zotero_dir = tmp_path / "Zotero"
    zotero_dir.mkdir()
    (zotero_dir / "zotero.sqlite").touch()

    # Missing storage/
    with patch.dict(os.environ, {"ZOTERO_DATA_DIR": str(zotero_dir)}):
        with pytest.raises(FileNotFoundError, match="storage"):
            resolve_zotero_data_dir()


def test_resolve_success(tmp_path: Path) -> None:
    """Test successful resolution with valid structure."""
    zotero_dir = tmp_path / "Zotero"
    zotero_dir.mkdir()
    (zotero_dir / "zotero.sqlite").touch()
    (zotero_dir / "storage").mkdir()

    with patch.dict(os.environ, {"ZOTERO_DATA_DIR": str(zotero_dir)}):
        result = resolve_zotero_data_dir()

    assert result == zotero_dir
```

**Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/test_config.py -v
```

Expected: New tests FAIL (no validation implemented)

**Step 3: Implement validation**

Modify `src/zotero2ai/config.py`:
```python
"""Configuration resolution for zotero2ai."""

import os
from pathlib import Path


def resolve_zotero_data_dir() -> Path:
    """
    Resolve ZOTERO_DATA_DIR from environment variable.

    ZOTERO_DATA_DIR is required - no autodiscovery fallback.

    Returns:
        Path: Resolved Zotero data directory

    Raises:
        ValueError: If ZOTERO_DATA_DIR is not set
        FileNotFoundError: If directory structure is invalid
    """
    env_dir = os.environ.get("ZOTERO_DATA_DIR")
    if not env_dir:
        raise ValueError(
            "ZOTERO_DATA_DIR environment variable is required.\n"
            "Set it to your Zotero data directory path.\n"
            "Example: export ZOTERO_DATA_DIR=~/Zotero"
        )

    path = Path(env_dir).expanduser().resolve()

    # Validate directory exists
    if not path.exists():
        raise FileNotFoundError(
            f"ZOTERO_DATA_DIR path does not exist: {path}\n"
            "Ensure the directory exists and is accessible."
        )

    if not path.is_dir():
        raise FileNotFoundError(
            f"ZOTERO_DATA_DIR is not a directory: {path}"
        )

    # Validate required structure
    db_path = path / "zotero.sqlite"
    storage_path = path / "storage"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Missing zotero.sqlite in ZOTERO_DATA_DIR: {path}\n"
            "Expected to find: {db_path}"
        )

    if not storage_path.is_dir():
        raise FileNotFoundError(
            f"Missing storage/ directory in ZOTERO_DATA_DIR: {path}\n"
            "Expected to find: {storage_path}"
        )

    return path
```

**Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_config.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/zotero2ai/config.py tests/test_config.py
git commit -m "feat(config): validate zotero.sqlite and storage/ exist

- Check for zotero.sqlite file
- Check for storage/ directory
- Fail fast with actionable errors"
```

---

## Task 4: Add ZoteroConfig Dataclass

**Files:**
- Modify: `src/zotero2ai/config.py`
- Modify: `tests/test_config.py`

**Step 1: Write test for ZoteroConfig**

Add to `tests/test_config.py`:
```python
from zotero2ai.config import ZoteroConfig


def test_zotero_config_properties(tmp_path: Path) -> None:
    """Test ZoteroConfig provides db_path and storage_path."""
    zotero_dir = tmp_path / "Zotero"
    zotero_dir.mkdir()
    (zotero_dir / "zotero.sqlite").touch()
    (zotero_dir / "storage").mkdir()

    config = ZoteroConfig(data_dir=zotero_dir)

    assert config.data_dir == zotero_dir
    assert config.db_path == zotero_dir / "zotero.sqlite"
    assert config.storage_path == zotero_dir / "storage"
    assert config.db_path.exists()
    assert config.storage_path.is_dir()
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_config.py::test_zotero_config_properties -v
```

Expected: FAIL with "ImportError: cannot import name 'ZoteroConfig'"

**Step 3: Implement ZoteroConfig dataclass**

Modify `src/zotero2ai/config.py`:
```python
"""Configuration resolution for zotero2ai."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ZoteroConfig:
    """Zotero configuration with resolved paths."""

    data_dir: Path

    @property
    def db_path(self) -> Path:
        """Path to zotero.sqlite database."""
        return self.data_dir / "zotero.sqlite"

    @property
    def storage_path(self) -> Path:
        """Path to storage directory."""
        return self.data_dir / "storage"


def resolve_zotero_data_dir() -> Path:
    """
    Resolve ZOTERO_DATA_DIR from environment variable.

    ZOTERO_DATA_DIR is required - no autodiscovery fallback.

    Returns:
        Path: Resolved Zotero data directory

    Raises:
        ValueError: If ZOTERO_DATA_DIR is not set
        FileNotFoundError: If directory structure is invalid
    """
    env_dir = os.environ.get("ZOTERO_DATA_DIR")
    if not env_dir:
        raise ValueError(
            "ZOTERO_DATA_DIR environment variable is required.\n"
            "Set it to your Zotero data directory path.\n"
            "Example: export ZOTERO_DATA_DIR=~/Zotero"
        )

    path = Path(env_dir).expanduser().resolve()

    # Validate directory exists
    if not path.exists():
        raise FileNotFoundError(
            f"ZOTERO_DATA_DIR path does not exist: {path}\n"
            "Ensure the directory exists and is accessible."
        )

    if not path.is_dir():
        raise FileNotFoundError(
            f"ZOTERO_DATA_DIR is not a directory: {path}"
        )

    # Validate required structure
    db_path = path / "zotero.sqlite"
    storage_path = path / "storage"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Missing zotero.sqlite in ZOTERO_DATA_DIR: {path}\n"
            f"Expected to find: {db_path}"
        )

    if not storage_path.is_dir():
        raise FileNotFoundError(
            f"Missing storage/ directory in ZOTERO_DATA_DIR: {path}\n"
            f"Expected to find: {storage_path}"
        )

    return path
```

**Step 4: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_config.py::test_zotero_config_properties -v
```

Expected: PASS

**Step 5: Run all config tests**

Run:
```bash
uv run pytest tests/test_config.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add src/zotero2ai/config.py tests/test_config.py
git commit -m "feat(config): add ZoteroConfig dataclass

- Provide db_path and storage_path properties
- Clean interface for accessing Zotero paths"
```

---

## Task 5: Add Type Checking with MyPy

**Files:**
- Run mypy on config module

**Step 1: Run mypy**

Run:
```bash
uv run mypy src/zotero2ai/config.py --strict
```

Expected: PASS (no type errors)

**Step 2: Verify in CI style**

Run:
```bash
uv run mypy src/zotero2ai/ --strict
```

Expected: PASS

---

## Definition of Done (WP-B)

✅ `src/zotero2ai/config.py` exists with:
  - `resolve_zotero_data_dir()` function
  - Requires ZOTERO_DATA_DIR env var (no autodiscovery)
  - Validates zotero.sqlite exists
  - Validates storage/ directory exists
  - Fails with actionable FileNotFoundError
  - `ZoteroConfig` dataclass with data_dir, db_path, storage_path properties

✅ `tests/test_config.py` with full coverage:
  - Test missing ZOTERO_DATA_DIR raises ValueError
  - Test missing zotero.sqlite raises FileNotFoundError
  - Test missing storage/ raises FileNotFoundError
  - Test successful resolution returns Path
  - Test ZoteroConfig properties work correctly

✅ `uv run pytest tests/test_config.py -v` passes all tests

✅ `uv run mypy src/zotero2ai/config.py --strict` passes

---

## Handoff to WP-D (CLI)

**Outputs:**
- ✅ `resolve_zotero_data_dir()` function available for import
- ✅ `ZoteroConfig` dataclass available for import
- ✅ Clear error messages for missing/invalid configuration
- ✅ Type-safe implementation (mypy strict mode)
