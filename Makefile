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


# =============================================================================
# SETUP & INSTALLATION (DEV)
# =============================================================================

setup:  ## Set up development environment
> $(UV) sync --all-extras

install:  ## Install dependencies with dev extras
> $(UV) sync --all-extras

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
> $(UV) run mcp-zotero2ai doctor

run:  ## Run MCP server
> $(UV) run mcp-zotero2ai run

run-help:  ## Show CLI help
> $(UV) run mcp-zotero2ai --help

# =============================================================================
# SYSTEM INSTALL (DEV-ONLY)
# =============================================================================

install-system: build  ## Install built wheel into user site-packages (dev-only)
> $(PYTHON_SYSTEM) -m pip install --user dist/*.whl --force-reinstall --break-system-packages

uninstall-system:  ## Remove system installation
> $(PYTHON_SYSTEM) -m pip uninstall -y zotero2ai || true

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
        test-install doctor run run-help validate check ci all \
        install-system uninstall-system
