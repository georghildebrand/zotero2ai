# zotero2ai – Implementation Plan (MCP + local Vector Search)

## Zielbild
Ein **pip-installierbarer MCP-Server** für Zotero, konfiguriert ausschließlich über `ZOTERO_DATA_DIR`, der:
- Zotero lokal **read-only** über SQLite liest (Items, Notes, Tags, Collections, Relations)
- eine **aktive Collection** per Name/Pfad setzen kann (Key intern)
- **hybride Suche** (lexical + embeddings) anbietet
- mittelfristig **Writes** (Notes/Tags/Links/Collection-Adds) über einen **sicheren Write-Gateway** (nicht über SQLite) ermöglicht

---

## Nicht-Ziele (wichtig)
- **Keine** direkten Schreibzugriffe auf `zotero.sqlite`.
- PDF-Volltext-Extraktion ist **nicht** MVP (später, optional).

---

## Feste Architektur-Entscheidungen
1) **Single Config Input:** `ZOTERO_DATA_DIR` (enthält DB + Storage)
2) **SQLite Read-Only:** connect via URI `mode=ro`
3) **Vector DB lokal:** FAISS (in-process) + Embeddings via `sentence-transformers`
4) **Persistenz:** Index + Metadaten in User-Cache (platformdirs)
5) **MCP:** Python SDK (`mcp`) mit FastMCP

---

## Repo-Layout (empfohlen)

```text
zotero2ai/
  src/
    zotero2ai/
      __init__.py
      cli.py
      config.py
      logging.py

      zotero/
        db.py              # read-only sqlite access
        models.py          # Item/Note/Collection models
        collections.py     # list + fullPath + resolve
        items.py           # get item, notes, tags, relations
        text.py            # text assembly for indexing

      index/
        store.py           # faiss index IO + metadata store
        embedder.py        # sentence-transformers wrapper
        pipeline.py        # incremental indexing
        hybrid.py          # hybrid scoring + filtering

      mcp_server/
        server.py          # FastMCP init + tools/resources
        schemas.py         # tool IO schemas

  tests/
  pyproject.toml
  README.md
```

---

## Configuration
### Env var
- `ZOTERO_DATA_DIR`: **required**

### Resolution rules
- locate `zotero.sqlite` under `ZOTERO_DATA_DIR`
- locate `storage/` under `ZOTERO_DATA_DIR`
- if missing: fail fast with actionable error

### Local state
- Cache dir (platformdirs): `~/.cache/zotero2ai/` (OS-specific)
- Active collection: store in `~/.config/zotero2ai/config.json` (or in cache for session-only)

---

## MCP Surface (MVP)
### Tools
1) `list_collections(prefix: str | null = null, scope: "all"|"library" = "all")`
   - returns: list of `{key, name, fullPath, library}`

2) `set_active_collection(name_or_path: str)`
   - resolves by exact match first, then fuzzy
   - if ambiguous: returns candidates with indices
   - on success: stores `activeCollectionKey`

3) `get_active_collection()`
   - returns `{key, fullPath, library}`

4) `search(query: str, top_k: int = 10, scope: "active"|"all" = "active", mode: "lexical"|"vector"|"hybrid" = "hybrid")`
   - returns ranked results with lightweight “why” fields

5) `get_item(key: str, include_notes: bool = true, include_tags: bool = true)`
   - returns item metadata, notes (snippets), tags, relations

6) `index_update(scope: "active"|"all" = "active", force: bool = false)`
   - builds/updates embeddings index incrementally

7) `index_status()`
   - returns last build time, doc count, embedding model id

### Resources
- `zotero://active-collection`
- `zotero://collection/{key}/items`
- `zotero://item/{key}`

---

## Datenzugriff: SQLite Read Model
### Read-only connect
- `sqlite3.connect("file:{db}?mode=ro", uri=True)`
- short-lived transactions; avoid any write pragmas

### Collection fullPath
- fetch collections with `{key, name, parentKey, libraryID/groupID}`
- build `fullPath` by parent traversal

### Item text for indexing
Concatenate (weighted by ordering):
- title
- abstract
- creators (last names)
- year
- tags
- notes text

---

## Local Vector Index (FAISS)
### Doc types
- `item:{itemKey}`
- `note:{noteKey}`

### Metadata
- library
- collectionPaths[]
- tags[]
- year
- source keys

### Incremental update
- compute `content_hash = sha256(index_text)`
- embed only if hash changed

### Storage
- `index.faiss`
- `meta.sqlite` (recommended) or `meta.jsonl`

---

## Hybrid Search
### Scoring
- lexical score (initial: simple ranking; later: SQLite FTS5 / BM25)
- vector score (cosine / inner product)
- normalized weighted sum

### Filtering
- `scope=active` → filter by `collectionPaths` or collection membership
- tags include/exclude
- optional year range

### Output fields (for agent usability)
- `title`, `year`, `creators`
- `key`
- `score_total`, `score_lexical`, `score_vector`
- `snippets`: short note/abstract excerpts
- `matched_fields`: e.g. `["title","notes"]`

---

## Writes (Phase 2+; bewusst getrennt)
### Rationale
- No SQLite writes. Mutations must go through Zotero-sanctioned path.

### Recommended approach
- **Write Queue + Zotero Add-on consumer**
  - MCP tools: `enqueue_create_note`, `enqueue_add_to_collection`, `enqueue_link_relations`, `enqueue_tag`
  - Add-on reads queue files, executes inside Zotero, writes status receipts

### Planned tool stubs (return “not enabled” until gateway exists)
- `create_note_in_active_collection(title_prefix, tags[], markdown, link_item_keys[])`
- `add_items_to_active_collection(item_keys[])`
- `link_relations(source_key, target_key, relation_type)`

---

## Milestones / Releases

### Milestone 0.1.0 — CLI skeleton (parallelizable)

**Goal:** pip-installierbares Paket mit `mcp-zotero2ai` CLI, inkl. `doctor` und `run` (MCP stub), plus saubere Config-Resolution über `ZOTERO_DATA_DIR`.

#### Hard requirements (apply now)
- **Python 3.12 everywhere:** `requires-python = ">=3.12"`, Ruff target `py312`, Mypy `python_version = "3.12"`.
- **MCP dependency:** use official `mcp[cli]` (includes `FastMCP`). Pin a minimum version to avoid API drift.
- **Logging must affect child loggers:** configure root logging once; ensure `zotero2ai.*` loggers emit to stderr and tests can assert on stderr.
- **Make-based workflow:** `make test`, `make lint`, `make check`, `make run`, `make doctor`.
- **Subagents compatibility:** tasks are structured as *independent work packages* with explicit inputs/outputs and merge points.

#### Progress Tracking

**Status as of 2025-12-29:**

| WP | Name | Status | Completed | Notes |
|----|------|--------|-----------|-------|
| WP-A | Packaging & pyproject | ✅ DONE | 2025-12-29 | pyproject.toml configured, all deps installed, package importable |
| WP-B | Config module + tests | ✅ DONE | 2025-12-29 | 12 tests, 100% coverage, mypy strict passing |
| WP-C | Logging module + tests | ✅ DONE | 2025-12-29 | Root logger configured, child loggers propagate correctly |
| WP-D | CLI skeleton + tests | ✅ DONE | 2025-12-29 | doctor and run commands implemented with FastMCP stub |
| WP-E | Makefile workflow | ✅ DONE | 2025-12-29 | Standard dev targets implemented and verified |
| WP-F | Integration tests + README | ✅ DONE | 2025-12-29 | CLI behavior verified, README updated with setup instructions |

**Next:** Milestone 0.1.0 is complete. Proceed to Milestone 0.2.0 (SQLite Read Model).

#### Work packages (can be done in parallel)


##### WP-A — Packaging & pyproject ✅ DONE
**Owns:** `pyproject.toml`, dev tooling config.

Deliverables:
- `pyproject.toml`:
  - `requires-python = ">=3.12"`
  - dependencies: `platformdirs>=4`, `mcp[cli]>=<min>`
  - dev extras: `pytest`, `pytest-cov`, `ruff`, `mypy`
  - `project.scripts`: `mcp-zotero2ai = "zotero2ai.cli:main"`
  - ruff target: `py312`
  - mypy python_version: `3.12`

Acceptance:
- `uv sync --all-extras` succeeds.
- `uv run python -c "import zotero2ai"` succeeds.

##### WP-B — Config module + tests ✅ DONE
**Owns:** `src/zotero2ai/config.py`, `tests/test_config.py`.

Requirements:
- `resolve_zotero_data_dir()` resolution order:
  1) `ZOTERO_DATA_DIR`
  2) `~/Zotero`
  3) `~/zotero`
- validation: must contain `zotero.sqlite` and `storage/`.
- actionable `FileNotFoundError` mentioning `ZOTERO_DATA_DIR`.

Acceptance:
- `uv run pytest tests/test_config.py -v` passes.

##### WP-C — Logging module + tests (Agent C)
**Owns:** `src/zotero2ai/logging.py`, `tests/test_logging.py`.

Logging fix (key):
- Implement `setup_logging(debug=False, quiet=False)` using **root logger** configuration:
  - use `logging.basicConfig(level=..., handlers=[StreamHandler(sys.stderr)], format="[%(levelname)s] %(message)s", force=True)`
  - then set `logging.getLogger("zotero2ai").setLevel(level)` (optional), but root config is the point.
- Ensure child loggers (e.g. `zotero2ai.cli`) propagate and emit.

Acceptance:
- tests pass and stderr capture works.

##### WP-D — CLI skeleton + tests (Agent D)
**Owns:** `src/zotero2ai/cli.py`, `tests/test_cli.py`.

Requirements:
- `parse_args(args=None)` supports `doctor` and `run`, plus `--debug`, `--quiet`.
- `doctor`:
  - resolves config via `resolve_zotero_data_dir()`
  - opens sqlite read-only and runs a simple sanity query
  - returns exit code 0/1
- `run`:
  - starts **MCP server stub** using official SDK (`FastMCP`) with at least one trivial tool (e.g. `ping`).
  - for 0.1.0, it may run and immediately exit (stub) **or** start stdio server; choose the simplest that still validates import/wiring.

Acceptance:
- `uv run pytest tests/test_cli.py -v` passes.

##### WP-E — Makefile workflow (Agent E)
**Owns:** `Makefile` (create if absent) + ensures reproducible targets.

Minimum targets:
- `make install` → `uv sync --all-extras`
- `make format` / `make format-check` → `ruff format`
- `make lint` → `ruff check` + `mypy`
- `make test` / `make test-cov`
- `make check` → format-check + lint + test
- `make doctor` → `uv run mcp-zotero2ai doctor`
- `make run` → `uv run mcp-zotero2ai run`
- `make test-install` → build wheel + venv install + `--help`

Note:
- remove `pre-commit` line unless you add it to dev deps.

Acceptance:
- `make check` passes on a fresh clone after `make install`.

##### WP-F — Integration tests + README (Agent F)
**Owns:** `tests/test_integration.py`, `README.md`.

Requirements:
- Integration tests:
  - `uv run mcp-zotero2ai --help` returns 0 and includes command list.
  - `doctor` with missing Zotero returns 1 and error mentions `ZOTERO_DATA_DIR`.
- README:
  - installation via `uv`
  - `ZOTERO_DATA_DIR` config
  - documented make targets (`make install`, `make test`, `make check`, `make doctor`, `make run`).

Acceptance:
- `uv run pytest tests/test_integration.py -v` passes.

#### Merge/sequence constraints
1) WP-A should land first (pyproject + deps) so others can run `uv sync`.
2) WP-B and WP-C are independent.
3) WP-D depends on WP-B + WP-C (imports).
4) WP-E can be done anytime after WP-A (uses uv).
5) WP-F depends on WP-D (CLI exists) and WP-E (document targets).

#### Release checklist (0.1.0)
- `make check`
- `make test-install`
- tag `v0.1.0`

### Subsequent milestones (unchanged)
- 0.2.0 — SQLite read model
- 0.3.0 — MCP tools/resources + active collection state
- 0.4.0 — local vector index MVP
- 0.5.0 — hybrid search + filters
- 0.6.0+ — writes via gateway

---

## Risiken / kritische Punkte
- Collection names not unique → always show `fullPath` + library; internal state uses `key`.
- Vector search easy; quality depends on text assembly + incremental indexing.
- Writes are the real complexity → keep them behind a gateway, not SQL.

