# Testing GET /notes/{key} Endpoint

## Overview
This document describes how to test the `GET /notes/{key}` endpoint, which retrieves the full content of a single note by its key.

## Endpoint Details

**URL:** `GET /notes/{key}`

**Authentication:** Required (Bearer token)

**Path Parameters:**
- `key` - The Zotero item key for the note (e.g., `ABC123XYZ`)

**Response Format:**
```json
{
  "key": "ABC123XYZ",
  "note": "<p>Full HTML content of the note</p>",
  "tags": ["tag1", "tag2"],
  "parentItemKey": "PARENT123" or null,
  "collections": ["COLL123", "COLL456"],
  "dateAdded": "2024-12-30T08:42:01Z",
  "dateModified": "2024-12-30T09:15:23Z"
}
```

## Prerequisites

1. **Zotero Plugin Running:** The zotero-mcp-bridge plugin must be installed and running in Zotero 7
2. **Authentication Token:** Token file must exist at `~/.zotero-mcp-token`
3. **Test Data:** At least one note should exist in your Zotero library

## Automated Testing

Run the automated test script:

```bash
./plugin/zotero-mcp-bridge/test_note_detail_endpoint.sh
```

This script will:
1. Load the authentication token
2. Get a list of notes to find a valid key
3. Retrieve a specific note by key
4. Test error handling for non-existent notes
5. Test authentication enforcement

## Manual Testing

### 1. Get a Valid Note Key

First, get a list of notes to find a valid key:

```bash
TOKEN=$(cat ~/.zotero-mcp-token)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:23120/notes
```

Copy a note key from the response (e.g., `ABC123XYZ`).

### 2. Retrieve Note by Key

```bash
TOKEN=$(cat ~/.zotero-mcp-token)
NOTE_KEY="ABC123XYZ"  # Replace with actual key

curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:23120/notes/$NOTE_KEY
```

**Expected Response (200 OK):**
```json
{
  "key": "ABC123XYZ",
  "note": "<p>This is the full HTML content...</p>",
  "tags": ["ai-generated", "important"],
  "parentItemKey": null,
  "collections": ["COLLECTION123"],
  "dateAdded": "2024-12-30T08:42:01Z",
  "dateModified": "2024-12-30T09:15:23Z"
}
```

### 3. Test Error Cases

#### Non-existent Note (404)
```bash
TOKEN=$(cat ~/.zotero-mcp-token)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:23120/notes/NONEXISTENT123
```

**Expected Response (404 Not Found):**
```json
{
  "error": "Not Found",
  "message": "Note with key NONEXISTENT123 not found"
}
```

#### Missing Authentication (401)
```bash
curl http://localhost:23120/notes/ABC123XYZ
```

**Expected Response (401 Unauthorized):**
```json
{
  "error": "Unauthorized",
  "message": "Missing or invalid Bearer token"
}
```

#### Invalid Item Type (400)
If you try to retrieve an item that exists but is not a note:

```bash
TOKEN=$(cat ~/.zotero-mcp-token)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:23120/notes/ITEMKEY123
```

**Expected Response (400 Bad Request):**
```json
{
  "error": "Item ITEMKEY123 is not a note"
}
```

## Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `key` | string | Zotero item key for the note |
| `note` | string | Full HTML content of the note |
| `tags` | array | List of tag strings |
| `parentItemKey` | string or null | Key of parent item if this is a child note |
| `collections` | array | List of collection keys this note belongs to |
| `dateAdded` | string | ISO 8601 timestamp when note was created |
| `dateModified` | string | ISO 8601 timestamp when note was last modified |

## Common Issues

### Issue: "Token file not found"
**Solution:** Ensure the Zotero plugin is running. Check Zotero's debug output for the token location.

### Issue: "No notes found in library"
**Solution:** Create a note in Zotero or use the `POST /notes` endpoint to create one programmatically.

### Issue: "Connection refused"
**Solution:** Verify the plugin is running and listening on port 23120. Check Zotero's debug output.

## Integration with MCP Server

This endpoint is critical for the `read_note` tool in the MCP server. The tool will:

1. Accept a note key as input
2. Call `GET /notes/{key}` with authentication
3. Return the full note content to the AI agent

Example MCP tool usage:
```python
# In the MCP server
async def read_note(key: str) -> str:
    response = await http_client.get(
        f"http://localhost:23120/notes/{key}",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    return data["note"]  # Return HTML content
```

## Success Criteria

- ✅ Returns 200 OK with full note content for valid keys
- ✅ Returns 404 Not Found for non-existent keys
- ✅ Returns 401 Unauthorized without valid token
- ✅ Returns 400 Bad Request for non-note items
- ✅ Response includes all required fields (key, note, tags, etc.)
- ✅ HTML content is properly formatted and complete
- ✅ Handles UTF-8 content correctly (emoji, special characters)

## Next Steps

After successful testing:
1. Update the MCP server to implement the `read_note` tool using this endpoint
2. Test the full integration with an AI agent
3. Document the endpoint in the main API documentation
4. Commit the changes with appropriate test results
