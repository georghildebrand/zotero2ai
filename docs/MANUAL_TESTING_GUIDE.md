# Manual Testing Guide: Zotero MCP Bridge

This guide walks through manual testing of the Zotero MCP Bridge plugin and MCP server integration.

## Prerequisites

- Zotero 7 installed
- Python 3.11+ with `uv` installed
- Terminal access
- `curl` command available

## Part 1: Plugin Installation and Setup

### 1.1 Build the Plugin

```bash
./pluging/build.sh
```

Expected: `zotero-mcp-bridge.xpi` file created.

### 1.2 Install Plugin in Zotero 7

1. Open Zotero 7
2. Go to **Tools → Add-ons**
3. Click the gear icon (⚙️) → **Install Add-on From File...**
4. Select `zotero-mcp-bridge.xpi`
5. Click **Install Now** if prompted
6. Restart Zotero if required
azZXz
Expected: Plugin loads without errors.

### 1.3 Retrieve Authentication Token

1. In Zotero, go to **Help → Debug Output Logging → View Output**
2. Look for lines containing "MCPServer" or "AuthManager"
3. Find the line: `AuthManager: Token = <64-character-hex-string>`

Example:
```
AuthManager: Token = a1b2c3d4e5f6...
MCPServer: Listening on 127.0.0.1:23120
MCPServer: Auth token = a1b2c3d4e5f6...
```

**Save this token** - you'll need it for all API requests.

### 1.4 Verify Server is Running

Check that the HTTP server is listening:

```bash
lsof -i :23120
```

Expected output:
```
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
zotero    123 user   10u  IPv4 0x...      0t0  TCP localhost:23120 (LISTEN)
```

If nothing appears, check Zotero's debug logs for errors.

## Part 2: API Endpoint Testing

Export your auth token for convenience:

```bash
export AUTH_TOKEN="your-64-character-token-here"
```

### 2.1 Test Health Check (No Auth Required)

```bash
curl -X GET http://127.0.0.1:23120/health \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "timestamp": "2024-12-30T12:34:56.789Z"
}
```

### 2.2 Test Authentication

**Missing token:**
```bash
curl -X GET http://127.0.0.1:23120/collections
```

Expected: `401 Unauthorized`
```json
{
  "error": "Unauthorized",
  "message": "Missing or invalid Bearer token"
}
```

**Invalid token:**
```bash
curl -X GET http://127.0.0.1:23120/collections \
  -H "Authorization: Bearer invalid-token-123"
```

Expected: `401 Unauthorized`

**Valid token:**
```bash
curl -X GET http://127.0.0.1:23120/collections \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: `200 OK` with collections data.

### 2.3 Test Host Header Validation (DNS Rebinding Protection)

**Invalid Host header:**
```bash
curl -X GET http://127.0.0.1:23120/health \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Host: evil.com:23120"
```

Expected: `403 Forbidden`
```json
{
  "error": "Forbidden: Invalid Host header"
}
```

**Valid Host headers:**
```bash
# localhost
curl -X GET http://localhost:23120/health \
  -H "Authorization: Bearer $AUTH_TOKEN"

# 127.0.0.1
curl -X GET http://127.0.0.1:23120/health \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: Both return `200 OK`.

### 2.4 Test Collections Endpoint

```bash
curl -X GET http://127.0.0.1:23120/collections \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "success": true,
  "data": [
    {
      "key": "ABC123XYZ",
      "name": "My Research",
      "parentKey": null,
      "fullPath": "My Research",
      "libraryID": 1
    }
  ]
}
```

### 2.5 Test Item Search

```bash
curl -X GET "http://127.0.0.1:23120/items/search?q=machine+learning&limit=5" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: Returns matching items (or empty array if no matches).

### 2.6 Test Recent Items

```bash
curl -X GET "http://127.0.0.1:23120/items/recent?limit=3" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: Returns 3 most recently added items.

### 2.7 Test Notes CRUD

#### List Notes (requires collection or parent item)

First, get a collection key from the collections endpoint, then:

```bash
curl -X GET "http://127.0.0.1:23120/notes?collectionKey=ABC123XYZ" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: Returns note summaries.

#### Create Note

```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>This is a test note from curl</p>",
    "tags": ["test", "curl"],
    "collections": ["ABC123XYZ"]
  }'
```

Expected: `201 Created` with note data including the new note's key.

**Save the returned key** for the next steps.

#### Read Full Note

```bash
curl -X GET http://127.0.0.1:23120/notes/YOUR_NOTE_KEY \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: `200 OK` with full note content.

#### Update Note

```bash
curl -X PUT http://127.0.0.1:23120/notes/YOUR_NOTE_KEY \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>This is the UPDATED test note</p>",
    "tags": ["test", "curl", "updated"]
  }'
```

Expected: `200 OK` with updated note data.

#### Verify Update in Zotero UI

1. Open Zotero
2. Navigate to the collection you used
3. Find the note you created
4. Verify the content matches your update

## Part 3: MCP Server Integration

### 3.1 Configure Environment

```bash
export ZOTERO_MCP_TOKEN="$AUTH_TOKEN"
export ZOTERO_DATA_DIR="/path/to/your/Zotero/data"  # Usually ~/Zotero
```

Verify:
```bash
echo $ZOTERO_MCP_TOKEN
echo $ZOTERO_DATA_DIR
```

### 3.2 Test MCP Server Startup

```bash
cd [PATH_TO_REPO]
uv run zotero2ai
```

Expected: Server starts without errors. You should see:
```
INFO: MCP server initialized
INFO: Connected to plugin at http://127.0.0.1:23120
```

### 3.3 Test MCP Tools via CLI

In a new terminal, test the MCP tools:

```bash
# List collections
uv run zotero2ai --tool list_collections

# Search items
uv run zotero2ai --tool search_items --args '{"query": "machine learning"}'

# List notes (use a collection key from list_collections)
uv run zotero2ai --tool list_notes --args '{"collection_key": "ABC123XYZ"}'
```

Expected: Each command returns formatted results with friendly names.

### 3.4 Verify Friendly Names

When listing notes, verify the format shows both friendly name AND key:

```
1. **lucky-chicken (NOTE001)**: "Test note about machine learning"
2. **brave-tiger (NOTE002)**: "Summary of paper XYZ"
```

### 3.5 Test Note CRUD via MCP Tools

```bash
# Create a note
uv run zotero2ai --tool create_or_extend_note --args '{
  "note_identifier": "new",
  "content": "# Test Section\nThis is a test note created via MCP",
  "collection_key": "ABC123XYZ"
}'

# Read the note (use the friendly name or key returned)
uv run zotero2ai --tool read_note --args '{"note_identifier": "lucky-chicken"}'

# Extend the note
uv run zotero2ai --tool create_or_extend_note --args '{
  "note_identifier": "lucky-chicken",
  "content": "# Additional Section\nMore content here"
}'

# Read again to verify extension
uv run zotero2ai --tool read_note --args '{"note_identifier": "lucky-chicken"}'
```

Expected: All operations succeed, note shows both sections.

## Part 4: Security Verification

### 4.1 Verify Localhost-Only Binding

```bash
netstat -an | grep 23120
```

Expected output should show `127.0.0.1:23120` or `localhost:23120`, NOT `0.0.0.0:23120`.

Example:
```
tcp4       0      0  127.0.0.1.23120        *.*                    LISTEN
```

If you see `0.0.0.0`, the server is exposed to the network - THIS IS A SECURITY ISSUE.

### 4.2 Test from Another Machine (Should Fail)

If you have another machine on your network, try:

```bash
# From another machine
curl -X GET http://<your-ip>:23120/health \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: **Connection refused** or **timeout**. The server should NOT be reachable from other machines.

### 4.3 Verify Token Strength

Your auth token should be:
- Exactly 64 hexadecimal characters (256 bits)
- Cryptographically random
- Different each time the plugin generates a new token

Example valid token: `a1b2c3d4e5f6789012345678901234567890abcdefabcdefabcdefabcdefabcd`

### 4.4 Test Token Persistence

1. Restart Zotero
2. Check debug logs for the auth token
3. Verify it's the **same token** as before (stored in prefs)

Expected: Token persists across Zotero restarts.

## Part 5: Error Handling

### 5.1 Test Invalid Requests

**Missing required field:**
```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tags": ["test"]}'
```

Expected: `400 Bad Request` - "Missing required field: note"

**Invalid note key:**
```bash
curl -X GET http://127.0.0.1:23120/notes/INVALID_KEY \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected: `404 Not Found`

**Invalid collection key:**
```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>Test</p>",
    "collections": ["INVALID_KEY"]
  }'
```

Expected: `400 Bad Request` - "Collection not found: INVALID_KEY"

### 5.2 Test UTF-8 Handling

```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json; charset=utf-8" \
  -d '{
    "note": "<p>Testing UTF-8: 日本語 Русский العربية 🎉</p>",
    "tags": ["utf8-test"]
  }'
```

Expected: `201 Created` with correct UTF-8 content. Verify in Zotero UI that special characters display correctly.

## Part 6: Integration Testing

### 6.1 Test with ChatGPT Desktop (Optional)

If you have ChatGPT Desktop with MCP support:

1. Configure MCP server in ChatGPT settings
2. Ask: "List my Zotero collections"
3. Ask: "Show me notes in collection X"
4. Ask: "Create a note about machine learning in collection X"
5. Ask: "Read the note 'lucky-chicken'"

Expected: All operations work through natural language.

### 6.2 Test Full Workflow

1. Create a new paper/book entry in Zotero
2. Via API: Create a note attached to that item
3. Via API: Read the note back
4. Via API: Extend the note with additional content
5. Via MCP: List notes and verify friendly name appears
6. Via Zotero UI: Verify all changes are visible

## Troubleshooting

### Plugin Not Loading

- Check Zotero debug logs for errors
- Verify `install.rdf` or `manifest.json` is correct
- Ensure all files are in the .xpi

### Server Not Starting

- Check Zotero debug logs: `MCPServer: Starting...`
- Verify port 23120 is not in use: `lsof -i :23120`
- Try restarting Zotero

### Authentication Failing

- Verify token is copied correctly (64 hex characters)
- Check for whitespace in token
- Ensure `Authorization: Bearer <token>` format is correct

### 404 on All Endpoints

- Plugin may not be fully loaded
- Check Zotero debug logs for errors during startup
- Verify HttpServer started: `MCPServer: Listening on 127.0.0.1:23120`

### UTF-8 Content Corrupted

- Ensure Content-Type includes `charset=utf-8`
- Check server logs for UTF-8 conversion errors
- Verify Content-Length calculation in `server.js`

## Success Criteria

All tests pass if:

- ✅ Plugin loads in Zotero 7 without errors
- ✅ Auth token is generated and persists
- ✅ All API endpoints return correct responses
- ✅ Authentication is required for all protected endpoints
- ✅ Host header validation blocks invalid hosts
- ✅ Server is only accessible on localhost (127.0.0.1)
- ✅ CRUD operations work for notes
- ✅ UTF-8 content is handled correctly
- ✅ MCP server connects and tools work
- ✅ Friendly names display with keys in listings
- ✅ Error handling is fail-closed (rejects on security failures)

## Next Steps

Once all manual tests pass:

1. Update main README with installation instructions
2. Tag release v2.0.0
3. Consider adding plugin to Zotero add-ons repository
4. Document MCP server configuration for AI assistants
