"""Contract tests for Zotero Bridge Plugin API responses."""

from typing import Any

import pytest
from pydantic import BaseModel, Field


class CollectionResponse(BaseModel):
    key: str
    name: str
    parentKey: str | None = None  # noqa: N815
    fullPath: str  # noqa: N815
    libraryID: int  # noqa: N815


class ItemResponse(BaseModel):
    key: str
    itemType: str  # noqa: N815
    title: str
    creators: list[str]
    date: str
    tags: list[str]
    collections: list[str]


class NoteResponse(BaseModel):
    key: str
    note: str
    tags: list[str]
    parentItemKey: str | None = None  # noqa: N815
    collections: list[str]
    dateAdded: str  # noqa: N815
    dateModified: str  # noqa: N815


class SuccessResponse(BaseModel):
    success: bool
    data: Any


def validate_collection(data: dict[str, Any]):
    return CollectionResponse(**data)


def validate_item(data: dict[str, Any]):
    return ItemResponse(**data)


class CreateNoteResponse(BaseModel):
    key: str
    item_type: str = Field(default="note", alias="itemType")
    note: str
    tags: list[str]
    parentItemKey: str | None = None  # noqa: N815
    collections: list[str]
    dateAdded: str  # noqa: N815
    dateModified: str  # noqa: N815


class UpdateNoteResponse(BaseModel):
    key: str
    note: str
    tags: list[str]
    parentItemKey: str | None = None  # noqa: N815
    collections: list[str]
    dateModified: str  # noqa: N815


def validate_note(data: dict[str, Any]):
    return NoteResponse(**data)


def validate_create_note(data: dict[str, Any]):
    return CreateNoteResponse(**data)


def validate_update_note(data: dict[str, Any]):
    return UpdateNoteResponse(**data)


def test_collection_contract():
    """Validate collection response structure."""
    data = {
        "key": "C1",
        "name": "Test",
        "parentKey": None,
        "fullPath": "Test",
        "libraryID": 1,
    }
    validate_collection(data)


def test_item_contract():
    """Validate item response structure."""
    data = {
        "key": "I1",
        "itemType": "journalArticle",
        "title": "Test Title",
        "creators": ["Doe, J"],
        "date": "2024",
        "tags": ["tag1"],
        "collections": ["C1"],
    }
    validate_item(data)


def test_note_contract():
    """Validate note response structure."""
    data = {
        "key": "N1",
        "note": "<p>Content</p>",
        "tags": ["tag1"],
        "parentItemKey": "I1",
        "collections": ["C1"],
        "dateAdded": "2024-01-01 00:00:00",
        "dateModified": "2024-01-01 00:00:00",
    }
    validate_note(data)


def test_create_note_contract():
    """Validate note creation response structure."""
    data = {
        "key": "N2",
        "itemType": "note",
        "note": "New Note",
        "tags": [],
        "parentItemKey": None,
        "collections": ["C1"],
        "dateAdded": "2024-01-02",
        "dateModified": "2024-01-02",
    }
    validate_create_note(data)


def test_update_note_contract():
    """Validate note update response structure."""
    data = {
        "key": "N1",
        "note": "Updated Content",
        "tags": [],
        "parentItemKey": "I1",
        "collections": ["C1"],
        "dateModified": "2024-01-03",
    }
    validate_update_note(data)


def test_invalid_note_contract():
    """Verify that invalid note structure raises error."""
    from pydantic import ValidationError

    data = {
        "key": "N1",
        # missing note field
        "tags": [],
    }
    with pytest.raises(ValidationError):
        validate_note(data)
