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
# .ENV LOADING
# =============================================================================

# Automatically load .env if it exists (silently skip if missing)
-include .env
export

# SSE server defaults (can be overridden in .env or on the command line)
SSE_HOST ?= 127.0.0.1
SSE_PORT ?= 8765

# =============================================================================
# HELP
# =============================================================================

help:  ## Show this help message
> @echo "Available commands:"
> @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
> 	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'


# =============================================================================
# SETUP & INSTALLATION (DEV)
# =============================================================================

setup:  ## Set up development environment
> $(UV) sync --all-extras

install:  ## Install dependencies with dev extras
> $(UV) sync --all-extras

build-plugin:  ## Build the Zotero plugin (.xpi)
> cd plugin && ./build.sh

# =============================================================================
# BUILD & PACKAGING
# =============================================================================

build:  ## Build wheel and sdist
> rm -rf dist/
> $(UV) build

clean:  ## Remove build artifacts and caches
> rm -rf build/ dist/ *.egg-info/ .pytest_cache/ htmlcov/ .coverage .test_env .venv
> find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
> find . -type f -name "*.pyc" -delete

distclean: clean  ## Deep clean including virtualenv
> rm -rf .venv

# =============================================================================
# CODE QUALITY
# =============================================================================

format:  ## Auto-format code
> $(UV) run ruff format src/ tests/

format-check:  ## Check formatting
> $(UV) run ruff format --check src/ tests/

lint:  ## Lint and type-check
> $(UV) run ruff check src/ tests/
> $(UV) run mypy src/zotero2ai/

# =============================================================================
# TESTING
# =============================================================================

test:  ## Run tests
> $(UV) run pytest tests/ -v

test-cov:  ## Run tests with coverage
> $(UV) run pytest tests/ -v \
>   --cov=src/zotero2ai --cov-report=html --cov-report=term-missing

test-install: build ## Test wheel install in isolated virtualenv
> $(PYTHON_SYSTEM) -m venv .test_env
> .test_env/bin/pip install dist/*.whl
> .test_env/bin/mcp-zotero2ai --help
> rm -rf .test_env

# =============================================================================
# RUNNING & DEMOS
# =============================================================================

doctor:  ## Run diagnostics to check Zotero configuration
> $(UV) run python -m zotero2ai.cli doctor

run:  ## Run MCP server (stdio, managed by MCP host — loads .env)
> $(UV) run python -m zotero2ai.cli run

serve-sse:  ## Run MCP server in SSE mode (self-hosted, loads .env) — use with zotero2ai-sse config
> @echo "Starting MCP server in SSE mode on http://$(SSE_HOST):$(SSE_PORT)/sse"
> @echo "  Set ZOTERO_MCP_TOKEN in .env before running."
> $(UV) run python -m zotero2ai.cli run --transport sse --host $(SSE_HOST) --port $(SSE_PORT)

run-help:  ## Show CLI help
> $(UV) run python -m zotero2ai.cli --help

# =============================================================================
# SYSTEM INSTALL (DEV-ONLY)
# =============================================================================

install-system:  ## Install CLI commands globally with uv tool (user-level, editable)
> $(UV) tool install --force --editable .

uninstall-system:  ## Remove system installation
> $(UV) tool uninstall zotero2ai || true

# =============================================================================
# VALIDATION & CI
# =============================================================================

validate:  ## Validate GitHub Actions workflows (requires actionlint)
> actionlint .github/workflows/*.yml

check:  ## Canonical quality gate (format-check + lint + test)
> make format-check
> make lint
> make test

ci: check  ## Alias for CI systems

all: check build ## Full pipeline (check + build)

.PHONY: help setup install build clean distclean format format-check lint test test-cov \
        test-install doctor run run-help serve-sse validate check ci all \
        install-system uninstall-system build-plugin
