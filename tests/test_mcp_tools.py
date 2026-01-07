"""Integration tests for MCP tools using mocked HTTP responses."""

from unittest.mock import patch

import httpx
import pytest
import respx

from zotero2ai.mcp_server.server import create_mcp_server


@pytest.fixture
def mcp():
    """Create the MCP server instance."""
    return create_mcp_server()


@pytest.fixture
def mock_token():
    return "test-token"


@pytest.fixture
def env_vars(mock_token):
    with patch.dict("os.environ", {"ZOTERO_MCP_TOKEN": mock_token}):
        yield


@respx.mock
@pytest.mark.asyncio
async def test_tool_list_collections(mcp, env_vars):
    """Test list_collections tool."""
    respx.get("http://127.0.0.1:23119/collections").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [{"key": "C1", "fullPath": "My Papers", "name": "My Papers", "libraryID": 1}],
            },
        )
    )

    # Call the tool via FastMCP (FastMCP tools are synchronous in our definition)
    # But FastMCP wraps them. Let's find the tool.
    result = await mcp.call_tool("list_collections", {})
    assert any("My Papers (key: C1)" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_search_papers(mcp, env_vars):
    """Test search_papers tool."""
    respx.get("http://127.0.0.1:23119/items/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "key": "I1",
                        "title": "Clean Code",
                        "itemType": "book",
                        "creators": ["Robert Martin"],
                        "date": "2008",
                    }
                ],
            },
        )
    )

    result = await mcp.call_tool("search_papers", {"query": "clean"})
    assert any("### Clean Code" in str(item) for item in result)
    assert any("- Key: I1" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_get_recent_papers(mcp, env_vars):
    """Test get_recent_papers tool."""
    respx.get("http://127.0.0.1:23119/items/recent").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "key": "I2",
                        "title": "Recent Paper",
                        "creators": ["Author X"],
                        "date": "2024",
                    }
                ],
            },
        )
    )

    result = await mcp.call_tool("get_recent_papers", {"limit": 1})
    assert any("### Recent Paper" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_list_notes(mcp, env_vars):
    """Test list_notes tool."""
    respx.get("http://127.0.0.1:23119/notes").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [
                    {
                        "key": "N1",
                        "note": "<p>This is a test note for list_notes</p>",
                        "tags": [],
                        "parentItemKey": "I1",
                        "collections": ["C1"],
                    }
                ],
            },
        )
    )

    result = await mcp.call_tool("list_notes", {"collection_key": "C1"})
    assert any("This is a test note for list_notes" in str(item) and "(N1)" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_read_note(mcp, env_vars):
    """Test read_note tool."""
    respx.get("http://127.0.0.1:23119/notes/N1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "key": "N1",
                    "note": "<p>Full note content here.</p>",
                },
            },
        )
    )

    result = await mcp.call_tool("read_note", {"key": "N1"})
    assert any("## Note N1" in str(item) for item in result)
    assert any("<p>Full note content here.</p>" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_create_note(mcp, env_vars):
    """Test create_or_extend_note tool (creation)."""
    respx.post("http://127.0.0.1:23119/notes").mock(
        return_value=httpx.Response(
            201,
            json={
                "success": True,
                "data": {"key": "N2"},
            },
        )
    )

    result = await mcp.call_tool("create_or_extend_note", {"content": "New content", "collection_key": "C1"})
    assert any("Successfully created new note" in str(item) and "N2" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_extend_note(mcp, env_vars):
    """Test create_or_extend_note tool (extension)."""
    # 1. Mock GET current note
    respx.get("http://127.0.0.1:23119/notes/N1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"key": "N1", "note": "Original"},
            },
        )
    )

    # 2. Mock PUT updated note
    respx.put("http://127.0.0.1:23119/notes/N1").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": {"key": "N1", "note": "Original\nExtended"},
            },
        )
    )

    result = await mcp.call_tool("create_or_extend_note", {"content": "Extended", "note_key": "N1", "extend": True})
    assert any("Successfully extended note" in str(item) and "N1" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_list_notes_active_collection(mcp, env_vars):
    """Test list_notes tool using active collection."""
    respx.get("http://127.0.0.1:23119/notes").mock(
        return_value=httpx.Response(
            200,
            json={
                "success": True,
                "data": [{"key": "N1", "note": "Active Note", "tags": [], "parentItemKey": "I1", "collections": ["C1"]}],
            },
        )
    )

    with patch("zotero2ai.mcp_server.server.ActiveCollectionManager") as MockManager:
        instance = MockManager.return_value
        instance.get_active_collection_key.return_value = "AC1"

        result = await mcp.call_tool("list_notes", {})

        # Check that the server was called with collectionKey=AC1
        request = respx.calls.last.request
        assert request.url.params["collectionKey"] == "AC1"
        assert any("Active Note" in str(item) for item in result)


@respx.mock
@pytest.mark.asyncio
async def test_tool_create_note_active_collection(mcp, env_vars):
    """Test create_or_extend_note tool using active collection (creation)."""
    respx.post("http://127.0.0.1:23119/notes").mock(
        return_value=httpx.Response(
            201,
            json={
                "success": True,
                "data": {"key": "N3"},
            },
        )
    )

    with patch("zotero2ai.mcp_server.server.ActiveCollectionManager") as MockManager:
        instance = MockManager.return_value
        instance.get_active_collection_key.return_value = "AC1"

        result = await mcp.call_tool("create_or_extend_note", {"content": "New Note in Active Collection"})

        request = respx.calls.last.request
        import json
        body = json.loads(request.content)
        assert body["collections"] == ["AC1"]
        assert any("Successfully created new note" in str(item) and "N3" in str(item) for item in result)

