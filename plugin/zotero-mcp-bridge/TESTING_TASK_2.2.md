# Testing Task 2.2: Items Search and Recent Endpoints

## Overview

Task 2.2 implements two new endpoints for querying Zotero items:
- `GET /items/search` - Search items by title
- `GET /items/recent` - Get recently added items

## Installation

1. Build the plugin:
   ```bash
   cd plugin/zotero-mcp-bridge
   zip -r ../zotero-mcp-bridge.xpi *
   ```

2. Install in Zotero:
   - Open Zotero
   - Go to Tools → Add-ons
   - Click gear icon → Install Add-on From File
   - Select `zotero-mcp-bridge.xpi`
   - Restart Zotero

3. Get the authentication token:
   - Open Zotero Error Console: Tools → Developer → Error Console
   - Look for: `MCPServer: Auth token = <your-token>`
   - Copy the token for testing

## Manual Testing

### Test 1: Search Items

Search for items containing "test" in the title:

```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://127.0.0.1:23119/items/search?q=test"
```

Expected response (200 OK):
```json
[
  {
    "key": "ABC123XYZ",
    "itemType": "journalArticle",
    "title": "Test Article Title",
    "creators": ["Smith, John", "Doe, Jane"],
    "date": "2024",
    "tags": ["machine learning", "AI"],
    "collections": ["COLL123"]
  }
]
```

### Test 2: Search with Limit

Search with a custom limit:

```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://127.0.0.1:23119/items/search?q=the&limit=3"
```

Expected: Returns maximum 3 items

### Test 3: Search Validation

Test missing query parameter (should fail):

```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://127.0.0.1:23119/items/search"
```

Expected response (400 Bad Request):
```json
{
  "error": "Missing 'q' query parameter"
}
```

### Test 4: Recent Items

Get 5 most recent items (default):

```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://127.0.0.1:23119/items/recent"
```

Expected response (200 OK): Array of 5 most recently added items, sorted by dateAdded (newest first)

### Test 5: Recent Items with Custom Limit

Get 10 most recent items:

```bash
curl -H "Authorization: Bearer <your-token>" \
  "http://127.0.0.1:23119/items/recent?limit=10"
```

Expected: Returns maximum 10 items

## Automated Testing

Run the automated test script:

```bash
cd plugin/zotero-mcp-bridge
./test_items_endpoints.sh <your-token>
```

Or set the token as an environment variable:

```bash
export ZOTERO_MCP_TOKEN=<your-token>
./test_items_endpoints.sh
```

## API Specification

### GET /items/search

Search for items by title.

**Query Parameters:**
- `q` (required): Search query string
- `limit` (optional): Maximum number of results (default: 10)

**Response:**
- Status: 200 OK
- Body: Array of item objects

**Error Responses:**
- 400 Bad Request: Missing 'q' parameter
- 401 Unauthorized: Invalid or missing authentication token
- 500 Internal Server Error: Server error

### GET /items/recent

Get recently added items, sorted by dateAdded (newest first).

**Query Parameters:**
- `limit` (optional): Maximum number of results (default: 5)

**Response:**
- Status: 200 OK
- Body: Array of item objects

**Error Responses:**
- 401 Unauthorized: Invalid or missing authentication token
- 500 Internal Server Error: Server error

### Item Object Format

```json
{
  "key": "ABC123XYZ",           // Zotero item key
  "itemType": "journalArticle", // Type of item
  "title": "Article Title",     // Item title
  "creators": [                 // Array of creator names
    "Smith, John",
    "Doe, Jane"
  ],
  "date": "2024",              // Publication date
  "tags": [                    // Array of tag names
    "machine learning",
    "AI"
  ],
  "collections": [             // Array of collection keys
    "COLL123"
  ]
}
```

## Implementation Details

### Search Implementation

The search endpoint:
1. Validates that the `q` parameter is provided
2. Creates a Zotero.Search object
3. Adds conditions to search title field and exclude attachments/notes
4. Executes the search and limits results
5. Formats items using the `formatItems()` helper

### Recent Items Implementation

The recent items endpoint:
1. Creates a Zotero.Search object to get all items (excluding attachments/notes)
2. Retrieves all matching items
3. Sorts by dateAdded in descending order (newest first)
4. Limits results to requested number
5. Formats items using the `formatItems()` helper

### Helper Method: formatItems()

Shared formatting logic that:
1. Retrieves full item objects from IDs
2. Extracts creators, tags, and collections
3. Formats creators as "LastName, FirstName"
4. Returns structured JSON response

## Verification Checklist

- [ ] Plugin builds successfully
- [ ] Plugin installs in Zotero without errors
- [ ] Server starts and authentication token is displayed
- [ ] `/items/search` returns 400 when `q` parameter is missing
- [ ] `/items/search?q=test` returns matching items
- [ ] `/items/search?q=test&limit=3` respects the limit parameter
- [ ] `/items/recent` returns 5 items by default
- [ ] `/items/recent?limit=10` respects the limit parameter
- [ ] Items are sorted by dateAdded (newest first) in `/items/recent`
- [ ] All endpoints require authentication (401 without token)
- [ ] Response format matches specification
- [ ] Automated test script passes all tests

## Next Steps

After successful testing:
1. Commit the changes
2. Update the main test script to reflect new endpoint status
3. Proceed to Task 2.3: Implement Notes List Endpoint
