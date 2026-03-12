import sqlite3
import logging
import re
import hashlib
import unicodedata
from pathlib import Path
from typing import Any, Optional, Dict, List
from datetime import datetime
from difflib import SequenceMatcher

from zotero2ai.memory_index.types import CatalogConcept, ProjectConceptUsage, UnitSupport

logger = logging.getLogger(__name__)

GERMAN_STOP_WORDS = {
    "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einen", "einem", "einer",
    "und", "oder", "mit", "ohne", "fuer", "für",
    "zur", "zum", "von", "im", "in", "am", "an",
    "vs", "v", "the", "a", "of",
}

TOKEN_SYNONYMS = {
    "idee": "idea",
    "buchband": "bookband",
    "erstellen": "create",
    "optimierung": "optimize",
    "optimierunge": "optimize",
    "konflikt": "conflict",
    "global": "global",
    "lokal": "local",
    "local": "local",
}

class MemoryIndexStore:
    """SQLite store for the sidecar memory index."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS catalog_concepts (
                    catalog_concept_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    concept_label TEXT,
                    summary TEXT,
                    state TEXT DEFAULT 'stable', -- stable | candidate | seed
                    created_at TEXT,
                    updated_at TEXT
                );

                CREATE TABLE IF NOT EXISTS project_concept_usage (
                    project TEXT,
                    catalog_concept_id TEXT,
                    local_item_key TEXT,
                    PRIMARY KEY (project, catalog_concept_id),
                    FOREIGN KEY (catalog_concept_id) REFERENCES catalog_concepts(catalog_concept_id)
                );

                CREATE TABLE IF NOT EXISTS project_concept_edges (
                    project TEXT,
                    source_concept_id TEXT,
                    target_concept_id TEXT,
                    relation_type TEXT,
                    PRIMARY KEY (project, source_concept_id, target_concept_id),
                    FOREIGN KEY (source_concept_id) REFERENCES catalog_concepts(catalog_concept_id),
                    FOREIGN KEY (target_concept_id) REFERENCES catalog_concepts(catalog_concept_id)
                );

                CREATE TABLE IF NOT EXISTS unit_support (
                    unit_item_key TEXT,
                    catalog_concept_id TEXT,
                    project TEXT,
                    PRIMARY KEY (unit_item_key, catalog_concept_id),
                    FOREIGN KEY (catalog_concept_id) REFERENCES catalog_concepts(catalog_concept_id)
                );

                CREATE TABLE IF NOT EXISTS candidate_concepts (
                    candidate_id TEXT PRIMARY KEY,
                    suggested_title TEXT,
                    normalized_label TEXT,
                    project TEXT,
                    evidence_unit_count INTEGER,
                    last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS index_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            self._ensure_column(conn, "catalog_concepts", "concept_label", "TEXT")
            self._ensure_column(conn, "candidate_concepts", "normalized_label", "TEXT")
            self._ensure_column(conn, "candidate_concepts", "project", "TEXT")
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def extract_concept_label(title: str) -> str:
        """Strip the memory prefix from a concept title."""
        match = re.match(r"^\[MEM\]\[[^\]]+\]\[[^\]]+\]\s*(.*)$", title)
        if match:
            return match.group(1).strip()
        return title.strip()

    @classmethod
    def normalize_concept_label(cls, label: str) -> str:
        """Collapse minor spelling/format variants into a stable comparison key."""
        base = cls.extract_concept_label(label).lower()
        base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
        base = re.sub(r"[^a-z0-9\s]+", " ", base)
        base = re.sub(r"\s+", " ", base).strip()
        return base

    @classmethod
    def concept_tokens(cls, label: str) -> List[str]:
        normalized = cls.normalize_concept_label(label)
        tokens = []
        for token in normalized.split():
            token = TOKEN_SYNONYMS.get(token, token)
            if len(token) <= 2:
                continue
            if token in GERMAN_STOP_WORDS:
                continue
            tokens.append(token)
        return tokens

    @classmethod
    def make_catalog_concept_id(cls, label: str) -> str:
        normalized = cls.normalize_concept_label(label)
        if normalized:
            slug = normalized.replace(" ", "-")
            return f"concept.{slug}"
        digest = hashlib.sha1(label.encode("utf-8")).hexdigest()[:12]
        return f"concept.{digest}"

    @classmethod
    def make_candidate_id(cls, project: str, label: str) -> str:
        normalized = cls.normalize_concept_label(label)
        if normalized:
            slug = normalized.replace(" ", "-")
        else:
            slug = hashlib.sha1(label.encode("utf-8")).hexdigest()[:12]
        return f"candidate.{project}.{slug}"

    def clear_all(self):
        """Wipe all data from the sidecar index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM catalog_concepts")
            conn.execute("DELETE FROM project_concept_usage")
            conn.execute("DELETE FROM project_concept_edges")
            conn.execute("DELETE FROM unit_support")
            conn.execute("DELETE FROM candidate_concepts")
            conn.execute("DELETE FROM index_state")
            conn.commit()

    def update_index_state(self, key: str, value: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO index_state (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_index_state(self, key: str) -> Optional[str]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM index_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def add_concept(self, concept: CatalogConcept):
        concept_label = concept.concept_label or self.extract_concept_label(concept.title)
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO catalog_concepts 
                   (catalog_concept_id, title, concept_label, summary, state, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (concept.catalog_concept_id, concept.title, concept_label, concept.summary, 
                 concept.state, concept.created_at, concept.updated_at)
            )
            conn.commit()

    def register_usage(self, project: str, catalog_concept_id: str, local_item_key: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO project_concept_usage (project, catalog_concept_id, local_item_key) VALUES (?, ?, ?)",
                (project, catalog_concept_id, local_item_key)
            )
            conn.commit()

    def register_unit_support(self, unit_item_key: str, catalog_concept_id: str, project: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO unit_support (unit_item_key, catalog_concept_id, project) VALUES (?, ?, ?)",
                (unit_item_key, catalog_concept_id, project)
            )
            conn.commit()
    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            stats = {
                "stable_concepts": conn.execute("SELECT COUNT(*) FROM catalog_concepts WHERE state = 'stable'").fetchone()[0],
                "candidate_concepts": conn.execute("SELECT COUNT(*) FROM candidate_concepts").fetchone()[0],
                "indexed_projects": conn.execute("SELECT COUNT(DISTINCT project) FROM project_concept_usage").fetchone()[0],
                "bound_units": conn.execute("SELECT COUNT(*) FROM unit_support").fetchone()[0],
                "last_rebuild": self.get_index_state("last_rebuild_at")
            }
            return stats

    def search_concepts(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search concepts by title or summary using prefix match."""
        with self._get_connection() as conn:
            # Simple LIKE based search for now
            search_pattern = f"%{query}%"
            rows = conn.execute(
                """SELECT * FROM catalog_concepts 
                   WHERE title LIKE ? OR concept_label LIKE ? OR summary LIKE ? 
                   ORDER BY title ASC LIMIT ?""",
                (search_pattern, search_pattern, search_pattern, limit)
            ).fetchall()
            return [dict(row) for row in rows]

    def get_concept(self, catalog_concept_id: str) -> Optional[Dict[str, Any]]:
        """Get a single concept by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM catalog_concepts WHERE catalog_concept_id = ?",
                (catalog_concept_id,)
            ).fetchone()
            if not row:
                return None
            
            concept = dict(row)
            # Add usage info
            usages = conn.execute(
                "SELECT project, local_item_key FROM project_concept_usage WHERE catalog_concept_id = ?",
                (catalog_concept_id,)
            ).fetchall()
            concept["usages"] = [dict(u) for u in usages]
            
            return concept

    def list_concepts(self, state: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """List concepts by state."""
        with self._get_connection() as conn:
            if state:
                rows = conn.execute(
                    "SELECT * FROM catalog_concepts WHERE state = ? ORDER BY title ASC LIMIT ?",
                    (state, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM catalog_concepts ORDER BY title ASC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(row) for row in rows]

    def add_candidate(self, candidate_id: str, title: str, evidence_count: int = 1, project: str | None = None):
        """Add or update a candidate concept."""
        normalized = self.normalize_concept_label(title)
        with self._get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO candidate_concepts 
                   (candidate_id, suggested_title, normalized_label, project, evidence_unit_count, last_updated) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (candidate_id, title, normalized, project, evidence_count, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
            )
            conn.commit()

    def get_candidates(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List all current candidates."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM candidate_concepts ORDER BY evidence_unit_count DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_candidates_for_project(self, project: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM candidate_concepts WHERE project = ?", (project,))
            conn.commit()

    def list_project_concept_labels(self, project: str) -> set[str]:
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT c.concept_label, c.title
                FROM catalog_concepts c
                JOIN project_concept_usage u ON u.catalog_concept_id = c.catalog_concept_id
                WHERE u.project = ?
                """,
                (project,),
            ).fetchall()
        labels = set()
        for row in rows:
            label = row["concept_label"] or self.extract_concept_label(row["title"])
            normalized = self.normalize_concept_label(label)
            if normalized:
                labels.add(normalized)
        return labels

    def get_consolidation_candidates(self, project: str | None = None, limit: int = 20, min_similarity: float = 0.72) -> List[Dict[str, Any]]:
        """Return human-reviewable concept/candidate clusters that look mergeable."""
        with self._get_connection() as conn:
            params: list[Any] = []
            project_sql = ""
            if project:
                project_sql = "WHERE u.project = ?"
                params.append(project)

            concept_rows = conn.execute(
                f"""
                SELECT c.catalog_concept_id,
                       c.title,
                       c.concept_label,
                       c.summary,
                       c.state,
                       u.project,
                       COUNT(us.unit_item_key) AS evidence_unit_count
                FROM catalog_concepts c
                JOIN project_concept_usage u ON u.catalog_concept_id = c.catalog_concept_id
                LEFT JOIN unit_support us
                    ON us.catalog_concept_id = c.catalog_concept_id AND us.project = u.project
                {project_sql}
                GROUP BY c.catalog_concept_id, c.title, c.concept_label, c.summary, c.state, u.project
                ORDER BY evidence_unit_count DESC, c.title ASC
                LIMIT ?
                """,
                (*params, max(limit * 4, 40)),
            ).fetchall()

            candidate_params: list[Any] = []
            candidate_sql = ""
            if project:
                candidate_sql = "WHERE project = ? OR project IS NULL"
                candidate_params.append(project)
            candidate_rows = conn.execute(
                f"""
                SELECT candidate_id,
                       suggested_title,
                       normalized_label,
                       project,
                       evidence_unit_count
                FROM candidate_concepts
                {candidate_sql}
                ORDER BY evidence_unit_count DESC, suggested_title ASC
                LIMIT ?
                """,
                (*candidate_params, max(limit * 4, 40)),
            ).fetchall()

        entries: List[Dict[str, Any]] = []
        for row in concept_rows:
            label = row["concept_label"] or self.extract_concept_label(row["title"])
            entries.append({
                "entry_type": "stable_concept",
                "id": row["catalog_concept_id"],
                "title": row["title"],
                "concept_label": label,
                "normalized_label": self.normalize_concept_label(label),
                "project": row["project"],
                "summary": row["summary"],
                "state": row["state"],
                "evidence_unit_count": row["evidence_unit_count"],
            })

        for row in candidate_rows:
            label = row["suggested_title"]
            entries.append({
                "entry_type": "candidate_concept",
                "id": row["candidate_id"],
                "title": row["suggested_title"],
                "concept_label": label,
                "normalized_label": row["normalized_label"] or self.normalize_concept_label(label),
                "project": row["project"],
                "summary": "",
                "state": "candidate",
                "evidence_unit_count": row["evidence_unit_count"],
            })

        used_ids: set[str] = set()
        clusters: List[Dict[str, Any]] = []
        for i, left in enumerate(entries):
            if left["id"] in used_ids:
                continue

            cluster = [left]
            for right in entries[i + 1:]:
                if right["id"] in used_ids:
                    continue
                if self._looks_mergeable(left, right, min_similarity=min_similarity):
                    cluster.append(right)

            if len(cluster) < 2:
                continue

            for entry in cluster:
                used_ids.add(entry["id"])

            cluster_sorted = sorted(
                cluster,
                key=lambda item: (item["entry_type"] != "stable_concept", -int(item["evidence_unit_count"] or 0), item["title"]),
            )
            labels = sorted({item["concept_label"] for item in cluster_sorted})
            projects = sorted({item["project"] for item in cluster_sorted if item["project"]})
            clusters.append({
                "canonical_hint": cluster_sorted[0]["concept_label"],
                "reason": self._cluster_reason(cluster_sorted),
                "projects": projects,
                "entries": cluster_sorted,
                "label_variants": labels,
            })

        clusters.sort(key=lambda cluster: (-len(cluster["entries"]), cluster["canonical_hint"]))
        return clusters[:limit]

    def _looks_mergeable(self, left: Dict[str, Any], right: Dict[str, Any], min_similarity: float) -> bool:
        left_norm = left["normalized_label"]
        right_norm = right["normalized_label"]
        if not left_norm or not right_norm:
            return False
        if left["id"] == right["id"]:
            return False
        if left_norm == right_norm:
            return True
        if left_norm in right_norm or right_norm in left_norm:
            return True

        left_tokens = set(self.concept_tokens(left["concept_label"]))
        right_tokens = set(self.concept_tokens(right["concept_label"]))
        if not left_tokens or not right_tokens:
            return False
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
        containment = len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens))
        similarity = SequenceMatcher(None, left_norm, right_norm).ratio()
        return overlap >= 0.45 or containment >= 0.6 or similarity >= min_similarity

    def _cluster_reason(self, entries: List[Dict[str, Any]]) -> str:
        normalized = {entry["normalized_label"] for entry in entries}
        if len(normalized) == 1:
            return "Exact normalized label match"
        return "High lexical similarity across concept labels"

    def delete_candidate(self, candidate_id: str):
        """Remove a candidate (e.g. after promotion)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM candidate_concepts WHERE candidate_id = ?", (candidate_id,))
            conn.commit()
