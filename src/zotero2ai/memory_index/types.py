from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

@dataclass(frozen=True)
class CatalogConcept:
    """Global concept in the sidecar catalog."""
    catalog_concept_id: str
    title: str
    concept_label: str = ""
    summary: str = ""
    state: str = "stable"  # stable | candidate | seed
    created_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    updated_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

@dataclass(frozen=True)
class ProjectConceptUsage:
    """Tracking which projects use which global concept."""
    project: str
    catalog_concept_id: str
    local_item_key: str  # The Zotero item key in this project

@dataclass(frozen=True)
class UnitSupport:
    """Linking units to the concepts they support."""
    unit_item_key: str
    catalog_concept_id: str
    project: str
