# Testing Notes CRUD Endpoints

This document provides examples for testing the Notes CRUD endpoints implemented in Wave 4.

## Prerequisites

1. Zotero plugin must be installed and running
2. Authentication token must be set in environment variable:
   ```bash
   export ZOTERO_MCP_TOKEN="your-token-here"
   ```

## Endpoint Examples

### 1. Create a New Note (POST /notes)

Create a standalone note:
```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>This is a test note with <strong>HTML</strong> content</p>",
    "tags": ["test", "api"]
  }'
```

Create a note attached to an item:
```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>This note is attached to a parent item</p>",
    "parentItemKey": "ABCD1234",
    "tags": ["child-note"]
  }'
```

Create a note in specific collections:
```bash
curl -X POST http://127.0.0.1:23120/notes \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>This note belongs to collections</p>",
    "collections": ["COLL1234", "COLL5678"],
    "tags": ["organized"]
  }'
```

### 2. Update an Existing Note (PUT /notes/{key})

Update note content only:
```bash
curl -X PUT http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>Updated content with <em>new</em> information</p>"
  }'
```

Update tags:
```bash
curl -X PUT http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tags": ["updated", "modified", "new-tag"]
  }'
```

Update multiple fields:
```bash
curl -X PUT http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "<p>Completely updated note</p>",
    "tags": ["final", "version"],
    "collections": ["COLL9999"]
  }'
```

Change parent item:
```bash
curl -X PUT http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "parentItemKey": "NEWPARENT123"
  }'
```

Remove parent (make standalone):
```bash
curl -X PUT http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "parentItemKey": null
  }'
```

### 3. Read Note (GET /notes/{key})

Get full note content:
```bash
curl -X GET http://127.0.0.1:23120/notes/NOTEXYZ123 \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN"
```

### 4. List Notes (GET /notes)

List notes in a collection:
```bash
curl -X GET "http://127.0.0.1:23120/notes?collectionKey=COLL1234" \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN"
```

List notes attached to an item:
```bash
curl -X GET "http://127.0.0.1:23120/notes?parentItemKey=ITEM5678" \
  -H "Authorization: Bearer $ZOTERO_MCP_TOKEN"
```

## Response Formats

### Success Response (200/201)
```json
{
  "success": true,
  "data": {
    "key": "NOTEXYZ123",
    "note": "<p>HTML content</p>",
    "tags": ["tag1", "tag2"],
    "parentItemKey": "PARENT123",
    "collections": ["COLL1", "COLL2"],
    "dateAdded": "2025-12-30 08:00:00",
    "dateModified": "2025-12-30 09:00:00"
  }
}
```

### Error Response (400/404/500)
```json
{
  "error": "Error Type",
  "message": "Detailed error message"
}
```

## Testing Workflow

1. **Get a collection key** to test with:
   ```bash
   curl -X GET http://127.0.0.1:23120/collections \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" | jq '.data[0].key'
   ```

2. **Create a test note**:
   ```bash
   NOTE_KEY=$(curl -X POST http://127.0.0.1:23120/notes \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"note": "<p>Test note</p>", "tags": ["test"]}' | jq -r '.data.key')
   echo "Created note: $NOTE_KEY"
   ```

3. **Update the note**:
   ```bash
   curl -X PUT http://127.0.0.1:23120/notes/$NOTE_KEY \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"note": "<p>Updated test note</p>", "tags": ["test", "updated"]}'
   ```

4. **Read the note back**:
   ```bash
   curl -X GET http://127.0.0.1:23120/notes/$NOTE_KEY \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" | jq
   ```

## Error Cases to Test

1. **Missing authentication**:
   ```bash
   curl -X POST http://127.0.0.1:23120/notes \
     -H "Content-Type: application/json" \
     -d '{"note": "<p>Test</p>"}'
   # Expected: 401 Unauthorized
   ```

2. **Invalid note key**:
   ```bash
   curl -X GET http://127.0.0.1:23120/notes/INVALID \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN"
   # Expected: 404 Not Found
   ```

3. **Missing required field**:
   ```bash
   curl -X POST http://127.0.0.1:23120/notes \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"tags": ["test"]}'
   # Expected: 400 Bad Request - Missing required field: note
   ```

4. **Invalid parent item**:
   ```bash
   curl -X POST http://127.0.0.1:23120/notes \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"note": "<p>Test</p>", "parentItemKey": "INVALID"}'
   # Expected: 400 Bad Request - Parent item not found
   ```

5. **Invalid collection**:
   ```bash
   curl -X POST http://127.0.0.1:23120/notes \
     -H "Authorization: Bearer $ZOTERO_MCP_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"note": "<p>Test</p>", "collections": ["INVALID"]}'
   # Expected: 400 Bad Request - Collection not found
   ```
