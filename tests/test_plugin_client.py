"""Tests for the Zotero plugin HTTP client."""

import pytest
import respx
from httpx import Response

from zotero2ai.zotero.plugin_client import (
    PluginAuthError,
    PluginClient,
    PluginConnectionError,
)


@pytest.fixture
def mock_plugin():
    """Mock the plugin HTTP server."""
    with respx.mock(base_url="http://127.0.0.1:23119") as respx_mock:
        yield respx_mock


@pytest.fixture
def client():
    """Create a plugin client with test token."""
    return PluginClient(auth_token="test-token-12345")


def test_client_initialization():
    """Test client initialization with default values."""
    client = PluginClient()
    assert client.base_url == "http://127.0.0.1:23119"
    assert client.auth_token is None
    assert client.timeout == 10.0


def test_client_initialization_with_custom_values():
    """Test client initialization with custom values."""
    client = PluginClient(
        base_url="http://localhost:8080",
        auth_token="custom-token",
        timeout=5.0,
    )
    assert client.base_url == "http://localhost:8080"
    assert client.auth_token == "custom-token"
    assert client.timeout == 5.0


def test_set_auth_token(client):
    """Test setting authentication token."""
    assert client.auth_token == "test-token-12345"
    client.set_auth_token("new-token")
    assert client.auth_token == "new-token"


def test_context_manager():
    """Test client as context manager."""
    with PluginClient(auth_token="test-token") as client:
        assert client.auth_token == "test-token"
    # Client should be closed after context exit
    assert client._client is None or client._client.is_closed


def test_health_check(client, mock_plugin):
    """Test health check endpoint."""
    mock_plugin.get("/health").mock(
        return_value=Response(
            200,
            json={
                "status": "ok",
                "version": "0.1.0",
                "timestamp": "2024-12-30T08:00:00Z",
            },
        )
    )

    result = client.health_check()
    assert result["status"] == "ok"
    assert result["version"] == "0.1.0"


def test_get_collections(client, mock_plugin):
    """Test getting collections."""
    mock_plugin.get("/collections").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "key": "ABC123",
                        "name": "Test Collection",
                        "parentKey": None,
                        "fullPath": "Test Collection",
                        "libraryID": 1,
                    }
                ]
            },
        )
    )

    collections = client.get_collections()
    assert len(collections) == 1
    assert collections[0]["key"] == "ABC123"
    assert collections[0]["name"] == "Test Collection"


def test_search_items(client, mock_plugin):
    """Test searching items."""
    mock_plugin.get("/items/search").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "key": "ITEM123",
                        "itemType": "journalArticle",
                        "title": "Test Article",
                        "creators": ["Smith, John"],
                        "date": "2024",
                        "tags": [],
                        "collections": [],
                    }
                ]
            },
        )
    )

    items = client.search_items("test", limit=10)
    assert len(items) == 1
    assert items[0]["title"] == "Test Article"


def test_get_recent_items(client, mock_plugin):
    """Test getting recent items."""
    mock_plugin.get("/items/recent").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "key": "RECENT1",
                        "title": "Recent Article",
                        "creators": ["Doe, Jane"],
                        "date": "2024",
                    }
                ]
            },
        )
    )

    items = client.get_recent_items(limit=5)
    assert len(items) == 1
    assert items[0]["key"] == "RECENT1"


def test_get_notes_with_collection_key(client, mock_plugin):
    """Test getting notes filtered by collection."""
    mock_plugin.get("/notes").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "key": "NOTE123",
                        "note": "<p>Test note content</p>",
                        "tags": ["tag1"],
                        "parentItemKey": None,
                        "collections": ["ABC123"],
                        "dateAdded": "2024-12-30 08:00:00",
                        "dateModified": "2024-12-30 08:00:00",
                    }
                ]
            },
        )
    )

    notes = client.get_notes(collection_key="ABC123")
    assert len(notes) == 1
    assert notes[0]["key"] == "NOTE123"


def test_get_notes_with_parent_item_key(client, mock_plugin):
    """Test getting notes filtered by parent item."""
    mock_plugin.get("/notes").mock(
        return_value=Response(
            200,
            json={
                "data": [
                    {
                        "key": "NOTE456",
                        "note": "<p>Child note</p>",
                        "tags": [],
                        "parentItemKey": "ITEM123",
                        "collections": [],
                        "dateAdded": "2024-12-30 08:00:00",
                        "dateModified": "2024-12-30 08:00:00",
                    }
                ]
            },
        )
    )

    notes = client.get_notes(parent_item_key="ITEM123")
    assert len(notes) == 1
    assert notes[0]["parentItemKey"] == "ITEM123"


def test_get_notes_without_filter_raises_error(client):
    """Test that get_notes raises error without filter."""
    with pytest.raises(ValueError, match="Must provide either collection_key or parent_item_key"):
        client.get_notes()


def test_get_note(client, mock_plugin):
    """Test getting a single note by key."""
    mock_plugin.get("/notes/NOTE123").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "key": "NOTE123",
                    "note": "<p>Full note content</p>",
                    "tags": ["important"],
                    "parentItemKey": None,
                    "collections": ["ABC123"],
                    "dateAdded": "2024-12-30 08:00:00",
                    "dateModified": "2024-12-30 08:00:00",
                }
            },
        )
    )

    note = client.get_note("NOTE123")
    assert note["key"] == "NOTE123"
    assert note["note"] == "<p>Full note content</p>"


def test_create_note(client, mock_plugin):
    """Test creating a new note."""
    mock_plugin.post("/notes").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "key": "NEWNOTE",
                    "note": "<p>New note</p>",
                    "tags": ["new"],
                    "parentItemKey": None,
                    "collections": ["ABC123"],
                    "dateAdded": "2024-12-30 08:00:00",
                    "dateModified": "2024-12-30 08:00:00",
                }
            },
        )
    )

    note = client.create_note(
        content="<p>New note</p>",
        tags=["new"],
        collections=["ABC123"],
    )
    assert note["key"] == "NEWNOTE"


def test_update_note(client, mock_plugin):
    """Test updating an existing note."""
    mock_plugin.put("/notes/NOTE123").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "key": "NOTE123",
                    "note": "<p>Updated content</p>",
                    "tags": ["updated"],
                    "parentItemKey": None,
                    "collections": ["ABC123"],
                    "dateAdded": "2024-12-30 08:00:00",
                    "dateModified": "2024-12-30 09:00:00",
                }
            },
        )
    )

    note = client.update_note(
        key="NOTE123",
        content="<p>Updated content</p>",
        tags=["updated"],
    )
    assert note["note"] == "<p>Updated content</p>"
    assert note["tags"] == ["updated"]


def test_authentication_error(client, mock_plugin):
    """Test handling of authentication errors."""
    mock_plugin.get("/health").mock(
        return_value=Response(
            401,
            json={"error": "Unauthorized", "message": "Invalid token"},
        )
    )

    with pytest.raises(PluginAuthError, match="Authentication failed"):
        client.health_check()


def test_no_auth_token_error():
    """Test error when no auth token is configured."""
    client = PluginClient()  # No token

    with pytest.raises(PluginAuthError, match="No authentication token configured"):
        client.health_check()


def test_connection_error(client, mock_plugin):
    """Test handling of connection errors."""
    import httpx

    mock_plugin.get("/health").mock(side_effect=httpx.ConnectError("Connection refused"))

    with pytest.raises(PluginConnectionError, match="Failed to connect to plugin"):
        client.health_check()


def test_note_not_found(client, mock_plugin):
    """Test handling of 404 errors."""
    import httpx

    mock_plugin.get("/notes/NOTFOUND").mock(
        return_value=Response(
            404,
            json={"error": "Not Found", "message": "Note not found"},
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.get_note("NOTFOUND")


def test_base_url_trailing_slash_removed():
    """Test that trailing slash is removed from base URL."""
    client = PluginClient(base_url="http://127.0.0.1:23119/")
    assert client.base_url == "http://127.0.0.1:23119"
