# WP-E: Makefile Workflow — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create/update Makefile with uv-based workflow for all development tasks (install, format, lint, test, doctor, run, build, check).

**Architecture:** GNU Make with uv as package manager. All commands use `uv run` for tool execution. Clean, minimal targets matching CI workflow.

**Tech Stack:** GNU Make 4.0+, uv, bash

**Dependencies:** WP-A must be complete (pyproject.toml with dependencies defined)

---

## Task 1: Write Makefile Header and Help Target

**Files:**
- Create/Replace: `Makefile`

**Step 1: Create basic Makefile structure**

Create `Makefile`:
```makefile
SHELL           := bash
.SHELLFLAGS     := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS      += --warn-undefined-variables
MAKEFLAGS      += --no-builtin-rules

ifeq ($(origin .RECIPEPREFIX), undefined)
  $(error This Make does not support .RECIPEPREFIX. Please use GNU Make 4.0 or later)
endif
.RECIPEPREFIX = >
.DEFAULT_GOAL := help

# =============================================================================
# GLOBAL CONTRACTS
# =============================================================================

UV := uv
PYTHON_SYSTEM ?= python3.12

# =============================================================================
# HELP
# =============================================================================

help:  ## Show this help message
> @echo "Available commands:"
> @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
> 	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'
```

**Step 2: Test help target**

Run:
```bash
make help
```

Expected: Shows "Available commands:" (empty for now)

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): add Makefile header and help target

- Configure bash with strict mode
- Set recipe prefix to >
- Add help target with auto-discovery"
```

---

## Task 2: Add Installation Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add install targets**

Add to `Makefile` (after HELP section):
```makefile
# =============================================================================
# SETUP & INSTALLATION
# =============================================================================

install:  ## Install dependencies with uv
> $(UV) sync --all-extras

setup: install  ## Alias for install (compatibility)
```

**Step 2: Test install target**

Run:
```bash
make install
```

Expected: Runs `uv sync --all-extras`, installs dependencies

**Step 3: Test help shows new targets**

Run:
```bash
make help
```

Expected: Shows install and setup targets

**Step 4: Commit**

```bash
git add Makefile
git commit -m "build(make): add install targets

- make install: uv sync --all-extras
- make setup: alias for install"
```

---

## Task 3: Add Code Quality Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add format and lint targets**

Add to `Makefile`:
```makefile
# =============================================================================
# CODE QUALITY
# =============================================================================

format:  ## Auto-format code with ruff
> $(UV) run ruff format src/ tests/

format-check:  ## Check formatting without changes
> $(UV) run ruff format --check src/ tests/

lint:  ## Lint and type-check
> $(UV) run ruff check src/ tests/
> $(UV) run mypy src/zotero2ai/ --strict
```

**Step 2: Test format target**

Run:
```bash
make format
```

Expected: Runs ruff format on src/ and tests/

**Step 3: Test lint target**

Run:
```bash
make lint
```

Expected: Runs ruff check and mypy

**Step 4: Commit**

```bash
git add Makefile
git commit -m "build(make): add code quality targets

- make format: auto-format with ruff
- make format-check: check formatting
- make lint: ruff check + mypy strict"
```

---

## Task 4: Add Testing Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add test targets**

Add to `Makefile`:
```makefile
# =============================================================================
# TESTING
# =============================================================================

test:  ## Run tests with pytest
> $(UV) run pytest tests/ -v

test-cov:  ## Run tests with coverage
> $(UV) run pytest tests/ -v \
>   --cov=src/zotero2ai --cov-report=html --cov-report=term-missing
```

**Step 2: Test test target**

Run:
```bash
make test
```

Expected: Runs pytest on tests/ directory

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): add testing targets

- make test: run pytest
- make test-cov: run pytest with coverage"
```

---

## Task 5: Add CLI Convenience Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add doctor and run targets**

Add to `Makefile`:
```makefile
# =============================================================================
# RUNNING CLI
# =============================================================================

doctor:  ## Run doctor command
> $(UV) run mcp-zotero2ai doctor

run:  ## Run MCP server (stdio mode)
> $(UV) run mcp-zotero2ai run --stdio

run-http:  ## Run MCP server (HTTP mode for ChatGPT integration)
> $(UV) run mcp-zotero2ai run --http --host 127.0.0.1 --port 8787

run-http-once:  ## Run HTTP smoke test (start, bind, exit)
> $(UV) run mcp-zotero2ai run --http --port 0 --once

run-help:  ## Show CLI help
> $(UV) run mcp-zotero2ai --help
```

**Step 2: Test doctor target (will fail without ZOTERO_DATA_DIR)**

Run:
```bash
make doctor
```

Expected: Shows error about missing ZOTERO_DATA_DIR (correct behavior)

**Step 3: Test run target**

Run:
```bash
make run
```

Expected: Shows MCP server started with stdio mode (stub)

**Step 4: Test run-http-once target**

Run:
```bash
make run-http-once
```

Expected: HTTP smoke test exits immediately with success

**Step 5: Test run-help target**

Run:
```bash
make run-help
```

Expected: Shows CLI help text with transport mode options

**Step 6: Commit**

```bash
git add Makefile
git commit -m "build(make): add CLI convenience targets with HTTP support

- make doctor: run doctor command
- make run: run MCP server (stdio mode)
- make run-http: run HTTP server for ChatGPT integration
- make run-http-once: HTTP smoke test (non-blocking)
- make run-help: show CLI help"
```

---

## Task 6: Add Build and Clean Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add build targets**

Add to `Makefile`:
```makefile
# =============================================================================
# BUILD & PACKAGING
# =============================================================================

build:  ## Build wheel and sdist
> rm -rf dist/
> $(UV) build

clean:  ## Remove build artifacts and caches
> rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage .test_env
> find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
> find . -type f -name "*.pyc" -delete

distclean: clean  ## Deep clean including virtualenv
> rm -rf .venv uv.lock
```

**Step 2: Test build target**

Run:
```bash
make build
```

Expected: Creates dist/ with wheel and sdist

**Step 3: Test clean target**

Run:
```bash
make clean
```

Expected: Removes build artifacts

**Step 4: Commit**

```bash
git add Makefile
git commit -m "build(make): add build and clean targets

- make build: uv build (wheel + sdist)
- make clean: remove build artifacts
- make distclean: clean + remove .venv"
```

---

## Task 7: Add Quality Gate and CI Targets

**Files:**
- Modify: `Makefile`

**Step 1: Add check and ci targets**

Add to `Makefile`:
```makefile
# =============================================================================
# VALIDATION & CI
# =============================================================================

check:  ## Canonical quality gate (format-check + lint + test)
> @echo "Running quality checks..."
> $(MAKE) format-check
> $(MAKE) lint
> $(MAKE) test
> @echo "✓ All checks passed!"

ci: check  ## Alias for CI systems
```

**Step 2: Test check target**

Run:
```bash
make check
```

Expected: Runs format-check, lint, and test in sequence, all pass

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): add quality gate and CI targets

- make check: run format-check + lint + test
- make ci: alias for check"
```

---

## Task 8: Add Test-Install Target

**Files:**
- Modify: `Makefile`

**Step 1: Add test-install target**

Add to `Makefile` (in TESTING section):
```makefile
test-install:  ## Test wheel install in isolated virtualenv
> $(MAKE) build
> $(PYTHON_SYSTEM) -m venv .test_env
> .test_env/bin/pip install dist/*.whl
> .test_env/bin/mcp-zotero2ai --help
> @echo "✓ Wheel installation successful"
> rm -rf .test_env
```

**Step 2: Test test-install target**

Run:
```bash
make test-install
```

Expected: Builds wheel, installs in isolated venv, runs --help, cleans up

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): add test-install target

- Build wheel in isolated venv
- Install and verify CLI works
- Clean up test environment"
```

---

## Task 9: Add .PHONY Declaration

**Files:**
- Modify: `Makefile`

**Step 1: Add .PHONY at end**

Add to end of `Makefile`:
```makefile
# =============================================================================
# PHONY TARGETS
# =============================================================================

.PHONY: help install setup format format-check lint test test-cov test-install \
        doctor run run-http run-http-once run-help build clean distclean check ci
```

**Step 2: Verify all targets work**

Run:
```bash
make help
```

Expected: Shows all targets with descriptions

**Step 3: Commit**

```bash
git add Makefile
git commit -m "build(make): add .PHONY declaration for all targets"
```

---

## Task 10: Test Complete Makefile

**Files:**
- None (verification)

**Step 1: Test clean build from scratch**

Run:
```bash
make distclean
make install
make check
```

Expected: Clean install and all checks pass

**Step 2: Test individual targets**

Run each target to verify:
```bash
make help           # Shows all commands
make format         # Formats code
make lint           # Passes
make test           # All tests pass
make doctor         # Shows config error (expected without ZOTERO_DATA_DIR)
make run-help       # Shows help with transport options
make run-http-once  # HTTP smoke test exits successfully
make build          # Creates dist/
make clean          # Removes artifacts
```

**Step 3: Document verification**

All targets work correctly (no commit needed).

---

## Definition of Done (WP-E)

✅ `Makefile` exists with uv-based workflow

✅ Targets implemented:
  - `help`: Show available commands
  - `install` / `setup`: Install dependencies with uv
  - `format`: Auto-format with ruff
  - `format-check`: Check formatting
  - `lint`: Run ruff check + mypy
  - `test`: Run pytest
  - `test-cov`: Run pytest with coverage
  - `test-install`: Test wheel installation
  - `doctor`: Run doctor command
  - `run`: Run MCP server (stdio mode)
  - `run-http`: Run MCP server (HTTP mode for ChatGPT)
  - `run-http-once`: Run HTTP smoke test (non-blocking)
  - `run-help`: Show CLI help
  - `build`: Build wheel and sdist
  - `clean`: Remove build artifacts
  - `distclean`: Deep clean with .venv
  - `check`: Quality gate (format-check + lint + test)
  - `ci`: Alias for check

✅ All targets use `uv run` for tool execution

✅ `make help` shows all targets with descriptions

✅ `make check` passes on fresh install

✅ No pre-commit targets (not in dev dependencies)

---

## Handoff to WP-F (Integration Tests)

**Outputs:**
- ✅ Complete Makefile with all development commands
- ✅ `make install`: reproducible dependency installation
- ✅ `make check`: canonical quality gate for CI
- ✅ `make doctor`, `make run`, `make run-http`: convenience commands
- ✅ `make run-http-once`: HTTP smoke test for CI (non-blocking)
- ✅ Documentation-ready (README can reference targets including ChatGPT integration)
