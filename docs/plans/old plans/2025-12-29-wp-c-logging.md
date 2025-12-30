# WP-C: Logging Module — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement logging.py with root logger configuration to ensure child loggers (zotero2ai.*) propagate correctly.

**Architecture:** Configure root logger using logging.basicConfig with force=True. Support debug, info (default), and quiet modes. All zotero2ai.* child loggers will propagate to root.

**Tech Stack:** Python 3.12+, standard library logging, sys.stderr

**Dependencies:** WP-A must be complete (package structure, pytest available)

---

## Task 1: Write Failing Test for setup_logging Function

**Files:**
- Create: `tests/test_logging.py`

**Step 1: Write test for default logging level**

Create `tests/test_logging.py`:
```python
"""Tests for logging configuration."""

import logging
import sys
from io import StringIO

from zotero2ai.logging import setup_logging


def test_setup_logging_default() -> None:
    """Test default logging setup (INFO level)."""
    setup_logging()
    root_logger = logging.getLogger()
    assert root_logger.level == logging.INFO
```

**Step 2: Run test to verify it fails**

Run:
```bash
uv run pytest tests/test_logging.py::test_setup_logging_default -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'zotero2ai.logging'"

**Step 3: Create minimal stub**

Create `src/zotero2ai/logging.py`:
```python
"""Logging configuration for zotero2ai."""


def setup_logging() -> None:
    """Stub."""
    pass
```

**Step 4: Run test again**

Run:
```bash
uv run pytest tests/test_logging.py::test_setup_logging_default -v
```

Expected: FAIL (root logger level not set correctly)

**Step 5: Commit**

```bash
git add src/zotero2ai/logging.py tests/test_logging.py
git commit -m "test(logging): add failing test for setup_logging"
```

---

## Task 2: Implement Root Logger Configuration

**Files:**
- Modify: `src/zotero2ai/logging.py`

**Step 1: Implement setup_logging with basicConfig**

Modify `src/zotero2ai/logging.py`:
```python
"""Logging configuration for zotero2ai."""

import logging
import sys


def setup_logging(debug: bool = False, quiet: bool = False) -> None:
    """
    Configure root logger for zotero2ai.

    Uses logging.basicConfig with force=True to ensure child loggers
    (zotero2ai.*) propagate correctly to stderr.

    Args:
        debug: Enable DEBUG level logging
        quiet: Only show WARNING and above
    """
    level = logging.DEBUG if debug else (logging.WARNING if quiet else logging.INFO)

    # Configure root logger - this ensures all child loggers propagate
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stderr)],
        format="[%(levelname)s] %(message)s",
        force=True,  # Critical: replace existing configuration
    )
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_logging.py::test_setup_logging_default -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add src/zotero2ai/logging.py
git commit -m "feat(logging): implement root logger configuration

- Use logging.basicConfig with force=True
- Configure stderr handler with clean format
- Default to INFO level"
```

---

## Task 3: Add Tests for Debug and Quiet Modes

**Files:**
- Modify: `tests/test_logging.py`

**Step 1: Add tests for debug and quiet modes**

Add to `tests/test_logging.py`:
```python
def test_setup_logging_debug() -> None:
    """Test debug logging setup."""
    setup_logging(debug=True)
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_setup_logging_quiet() -> None:
    """Test quiet logging setup (WARNING only)."""
    setup_logging(quiet=True)
    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING
```

**Step 2: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_logging.py -v
```

Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_logging.py
git commit -m "test(logging): add tests for debug and quiet modes"
```

---

## Task 4: Test Child Logger Propagation

**Files:**
- Modify: `tests/test_logging.py`

**Step 1: Write test for child logger emission**

Add to `tests/test_logging.py`:
```python
def test_child_logger_propagates(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that child loggers propagate to root and emit to stderr."""
    setup_logging()

    # Get a child logger
    logger = logging.getLogger("zotero2ai.config")
    logger.info("Test message from child logger")

    # Check stderr output
    captured = capsys.readouterr()
    assert "[INFO] Test message from child logger" in captured.err


def test_child_logger_respects_level(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that child loggers respect root level."""
    setup_logging(quiet=True)

    logger = logging.getLogger("zotero2ai.cli")
    logger.info("This should not appear")
    logger.warning("This should appear")

    captured = capsys.readouterr()
    assert "This should not appear" not in captured.err
    assert "[WARNING] This should appear" in captured.err


def test_debug_mode_shows_debug_messages(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that debug mode shows DEBUG level messages."""
    setup_logging(debug=True)

    logger = logging.getLogger("zotero2ai.test")
    logger.debug("Debug message")

    captured = capsys.readouterr()
    assert "[DEBUG] Debug message" in captured.err
```

**Step 2: Add pytest import at top of file**

Update imports in `tests/test_logging.py`:
```python
"""Tests for logging configuration."""

import logging
import sys
from io import StringIO

import pytest

from zotero2ai.logging import setup_logging
```

**Step 3: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/test_logging.py -v
```

Expected: All tests PASS (implementation already handles this via root logger config)

**Step 4: Commit**

```bash
git add tests/test_logging.py
git commit -m "test(logging): verify child logger propagation works

- Test child loggers emit to stderr
- Test child loggers respect root level
- Test debug mode shows debug messages"
```

---

## Task 5: Add Type Checking with MyPy

**Files:**
- Run mypy on logging module

**Step 1: Run mypy**

Run:
```bash
uv run mypy src/zotero2ai/logging.py --strict
```

Expected: PASS (no type errors)

**Step 2: Verify full package**

Run:
```bash
uv run mypy src/zotero2ai/ --strict
```

Expected: PASS (config + logging both pass)

---

## Task 6: Test Multiple setup_logging Calls

**Files:**
- Modify: `tests/test_logging.py`

**Step 1: Write test for force=True behavior**

Add to `tests/test_logging.py`:
```python
def test_setup_logging_can_be_called_multiple_times(capsys: pytest.CaptureFixture[str]) -> None:
    """Test that setup_logging can be called multiple times (force=True)."""
    # First call - INFO level
    setup_logging()
    logger1 = logging.getLogger("zotero2ai.test1")
    logger1.debug("Should not appear")
    logger1.info("Should appear first")

    # Second call - DEBUG level
    setup_logging(debug=True)
    logger2 = logging.getLogger("zotero2ai.test2")
    logger2.debug("Should appear second")

    captured = capsys.readouterr()
    assert "Should not appear" not in captured.err
    assert "Should appear first" in captured.err
    assert "Should appear second" in captured.err
```

**Step 2: Run test to verify it passes**

Run:
```bash
uv run pytest tests/test_logging.py::test_setup_logging_can_be_called_multiple_times -v
```

Expected: PASS (force=True allows reconfiguration)

**Step 3: Run all logging tests**

Run:
```bash
uv run pytest tests/test_logging.py -v
```

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_logging.py
git commit -m "test(logging): verify force=True allows reconfiguration"
```

---

## Definition of Done (WP-C)

✅ `src/zotero2ai/logging.py` exists with:
  - `setup_logging(debug=False, quiet=False)` function
  - Configures ROOT logger using `logging.basicConfig` with `force=True`
  - Outputs to sys.stderr
  - Format: `[LEVEL] message`
  - Supports debug (DEBUG), default (INFO), quiet (WARNING) modes

✅ `tests/test_logging.py` with full coverage:
  - Test default INFO level
  - Test debug mode (DEBUG level)
  - Test quiet mode (WARNING level)
  - Test child logger propagation to stderr
  - Test child loggers respect root level
  - Test debug messages appear in debug mode
  - Test multiple setup_logging calls work (force=True)

✅ `uv run pytest tests/test_logging.py -v` passes all tests

✅ `uv run mypy src/zotero2ai/logging.py --strict` passes

✅ Child loggers (e.g., `zotero2ai.cli`, `zotero2ai.config`) emit correctly to stderr

---

## Handoff to WP-D (CLI)

**Outputs:**
- ✅ `setup_logging(debug, quiet)` function available for import
- ✅ Root logger configured correctly
- ✅ Child loggers will propagate and emit without additional configuration
- ✅ Tests can capture stderr output with capsys fixture
- ✅ Type-safe implementation (mypy strict mode)
