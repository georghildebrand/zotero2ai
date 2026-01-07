#!/bin/bash
# Test script for Wave 4: Plugin Write Operations
# Tests POST /notes and PUT /notes/{key} endpoints

set -e

# Configuration
BASE_URL="http://127.0.0.1:23119"
TOKEN="${ZOTERO_MCP_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo "Error: ZOTERO_MCP_TOKEN environment variable is not set"
    exit 1
fi

echo "=== Wave 4: Testing Plugin Write Operations ==="
echo ""

# Helper function to make authenticated requests
auth_request() {
    curl -s -H "Authorization: Bearer $TOKEN" "$@"
}

# Test 1: Create a new note (minimal)
echo "Test 1: Create new note (minimal)"
RESPONSE=$(auth_request -X POST "$BASE_URL/notes" \
    -H "Content-Type: application/json" \
    -d '{"note": "<p>Test note created by Wave 4 test script</p>"}')

echo "Response: $RESPONSE"
NOTE_KEY=$(echo "$RESPONSE" | grep -o '"key":"[^"]*"' | cut -d'"' -f4)
echo "Created note key: $NOTE_KEY"
echo ""

# Test 2: Create a note with tags and collections
echo "Test 2: Create note with tags"
RESPONSE=$(auth_request -X POST "$BASE_URL/notes" \
    -H "Content-Type: application/json" \
    -d '{"note": "<p>Note with tags</p>", "tags": ["test", "wave4"]}')

echo "Response: $RESPONSE"
NOTE_KEY_2=$(echo "$RESPONSE" | grep -o '"key":"[^"]*"' | cut -d'"' -f4)
echo "Created note key: $NOTE_KEY_2"
echo ""

# Test 3: Update the first note
echo "Test 3: Update note content"
RESPONSE=$(auth_request -X PUT "$BASE_URL/notes/$NOTE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"note": "<p>Updated content for test note</p><p>This was modified by the test script</p>"}')

echo "Response: $RESPONSE"
echo ""

# Test 4: Update note tags
echo "Test 4: Update note tags"
RESPONSE=$(auth_request -X PUT "$BASE_URL/notes/$NOTE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"tags": ["updated", "wave4", "test-complete"]}')

echo "Response: $RESPONSE"
echo ""

# Test 5: Extend note (simulate append)
echo "Test 5: Get note, then extend it"
CURRENT_NOTE=$(auth_request -X GET "$BASE_URL/notes/$NOTE_KEY")
echo "Current note: $CURRENT_NOTE"

# Extract current content (simplified - in real use, parse JSON properly)
RESPONSE=$(auth_request -X PUT "$BASE_URL/notes/$NOTE_KEY" \
    -H "Content-Type: application/json" \
    -d '{"note": "<p>Updated content for test note</p><p>This was modified by the test script</p><p>Additional content appended</p>"}')

echo "Extended note response: $RESPONSE"
echo ""

# Test 6: Verify the updates
echo "Test 6: Verify note updates"
RESPONSE=$(auth_request -X GET "$BASE_URL/notes/$NOTE_KEY")
echo "Final note state: $RESPONSE"
echo ""

# Test 7: Error handling - create note without required field
echo "Test 7: Error handling - missing required field"
RESPONSE=$(auth_request -X POST "$BASE_URL/notes" \
    -H "Content-Type: application/json" \
    -d '{"tags": ["test"]}')

echo "Response (should be error): $RESPONSE"
echo ""

# Test 8: Error handling - update non-existent note
echo "Test 8: Error handling - update non-existent note"
RESPONSE=$(auth_request -X PUT "$BASE_URL/notes/NONEXISTENT" \
    -H "Content-Type: application/json" \
    -d '{"note": "<p>This should fail</p>"}')

echo "Response (should be 404): $RESPONSE"
echo ""

echo "=== Wave 4 Tests Complete ==="
echo ""
echo "Created notes:"
echo "  - $NOTE_KEY (updated)"
echo "  - $NOTE_KEY_2 (with tags)"
echo ""
echo "You can verify these notes in Zotero."
