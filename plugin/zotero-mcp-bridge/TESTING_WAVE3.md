# Testing: Wave 3 - Read Operations

## Overview

This document describes testing for Wave 3 read operations:
- **GET /collections** - List all collections
- **GET /items/search** - Search items by query
- **GET /items/recent** - Get recent items
- **GET /notes** - List notes (summaries)

## Prerequisites

1. Zotero 7 installed and running
2. Plugin loaded (see TESTING_WAVE2.md for installation)
3. Authentication token obtained from Zotero Error Console
4. Some test data in Zotero:
   - At least one collection
   - At least one item with notes
   - Some standalone notes in collections

## Setting Up Test Data

### Create Test Collection
1. In Zotero, create a new collection: "Test Collection"
2. Note the collection key (visible in the URL when selected)

### Create Test Items with Notes
1. Add a test item to the collection
2. Right-click the item → Add Note
3. Add some content to the note
4. Note the item key

### Create Standalone Notes
1. In the collection, click "New Note"
2. Add some content
3. Add tags if desired

## Testing GET /notes

### Test 1: List Notes by Collection

```bash
# Get your auth token from Zotero Error Console
TOKEN="your-64-char-token-here"

# Get collections to find a collection key
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:23119/collections

# Use a collection key from the response
COLLECTION_KEY="ABC123XYZ"

# List notes in that collection
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/notes?collectionKey=$COLLECTION_KEY"
```

**Expected Response:**
- Status: `200 OK`
- Body: JSON array of note objects
  ```json
  [
    {
      "key": "NOTEKEYABC",
      "note": "<p>Note content in HTML</p>",
      "tags": ["tag1", "tag2"],
      "parentItemKey": null,
      "collections": ["ABC123XYZ"],
      "dateAdded": "2025-12-30 08:00:00",
      "dateModified": "2025-12-30 09:00:00"
    }
  ]
  ```

### Test 2: List Notes by Parent Item

```bash
# Get items to find an item key
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/items/recent?limit=5"

# Use an item key from the response
ITEM_KEY="ITEMKEY123"

# List notes attached to that item
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/notes?parentItemKey=$ITEM_KEY"
```

**Expected Response:**
- Status: `200 OK`
- Body: JSON array of note objects with `parentItemKey` set
  ```json
  [
    {
      "key": "CHILDNOTE1",
      "note": "<p>Child note content</p>",
      "tags": [],
      "parentItemKey": "ITEMKEY123",
      "collections": [],
      "dateAdded": "2025-12-30 08:00:00",
      "dateModified": "2025-12-30 09:00:00"
    }
  ]
  ```

### Test 3: Error - Missing Parameters

```bash
# Try without any parameters
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:23119/notes
```

**Expected Response:**
- Status: `400 Bad Request`
- Body:
  ```json
  {
    "error": "Must provide collectionKey or parentItemKey"
  }
  ```

### Test 4: Error - Invalid Collection Key

```bash
# Try with non-existent collection key
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/notes?collectionKey=INVALID123"
```

**Expected Response:**
- Status: `400 Bad Request`
- Body:
  ```json
  {
    "error": "Collection not found: INVALID123"
  }
  ```

### Test 5: Error - Invalid Item Key

```bash
# Try with non-existent item key
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/notes?parentItemKey=INVALID456"
```

**Expected Response:**
- Status: `400 Bad Request`
- Body:
  ```json
  {
    "error": "Item not found: INVALID456"
  }
  ```

### Test 6: Empty Result

```bash
# Try with a collection that has no notes
# (Create an empty collection first in Zotero)
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/notes?collectionKey=EMPTYKEY"
```

**Expected Response:**
- Status: `200 OK`
- Body: Empty array
  ```json
  []
  ```

## Testing GET /collections

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:23119/collections
```

**Expected Response:**
- Status: `200 OK`
- Body: JSON array of collections
  ```json
  [
    {
      "key": "ABC123",
      "name": "My Collection",
      "parentKey": null,
      "fullPath": "My Collection",
      "libraryID": 1
    },
    {
      "key": "XYZ789",
      "name": "Subcollection",
      "parentKey": "ABC123",
      "fullPath": "My Collection / Subcollection",
      "libraryID": 1
    }
  ]
  ```

## Testing GET /items/search

```bash
# Search for items with "test" in the title
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/items/search?q=test&limit=5"
```

**Expected Response:**
- Status: `200 OK`
- Body: JSON array of items matching the query

## Testing GET /items/recent

```bash
# Get 5 most recent items
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:23119/items/recent?limit=5"
```

**Expected Response:**
- Status: `200 OK`
- Body: JSON array of recent items, sorted by dateAdded (newest first)

## Verification Checklist

- [ ] GET /notes with collectionKey returns notes in that collection
- [ ] GET /notes with parentItemKey returns child notes of that item
- [ ] GET /notes without parameters returns 400 error
- [ ] GET /notes with invalid collectionKey returns 400 error
- [ ] GET /notes with invalid parentItemKey returns 400 error
- [ ] GET /notes returns empty array for collection with no notes
- [ ] Note objects include all required fields (key, note, tags, parentItemKey, collections, dateAdded, dateModified)
- [ ] HTML content is properly returned in the "note" field
- [ ] Tags array is properly populated
- [ ] Collections array contains collection keys
- [ ] Dates are in proper format

## Troubleshooting

### "Collection not found" error
- Verify the collection key is correct
- Check that the collection exists in your user library (not a group library)
- Collection keys are case-sensitive

### "Item not found" error
- Verify the item key is correct
- Check that the item exists in your user library
- Item keys are case-sensitive

### Empty results when notes exist
- Verify you're using the correct collection/item key
- Check that notes are actually in that collection (not just the parent item)
- For child notes, ensure they're attached to the correct parent item

### Authentication errors
- See TESTING_WAVE2.md for authentication troubleshooting

## Next Steps (Wave 4)

Wave 4 will implement write operations:
- `POST /notes` - Create new note
- `PUT /notes/{key}` - Update existing note
- Human-readable note identifiers using coolname
- AI-generated content markers
