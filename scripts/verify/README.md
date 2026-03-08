# Verification scripts (manual / optional)

These scripts are **manual end-to-end checks** against a running Zotero instance with the Bridge plugin enabled.

They are intentionally **not** part of the default `pytest` suite because:
- they require a local Zotero runtime + plugin,
- they may create artifacts in your Zotero library unless you clean up manually,
- they are environment-dependent.

## Prerequisites

- Zotero is running
- Bridge plugin is installed and enabled
- `ZOTERO_MCP_TOKEN` is set in your environment

## Run

From the repo root:

- Smoke test (read-only): `uv run python scripts/verify/e2e_smoke.py`
- Collections traversal: `uv run python scripts/verify/collections_hierarchy.py`

Write tests (create memory items) are gated behind `--write` flags where applicable.

