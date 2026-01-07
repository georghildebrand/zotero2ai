#!/bin/bash

# Test script to verify query parameter fixes
# Tests all endpoints that use query parameters

echo "=== Testing Query Parameter Fixes ==="
echo ""

# Get auth token from Zotero preferences
TOKEN=$(sqlite3 ~/Zotero/zotero.sqlite "SELECT value FROM settings WHERE setting='extensions.zotero-mcp-bridge.authToken' AND key='value';" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "❌ ERROR: Could not find auth token in Zotero database"
    echo "Please ensure the plugin is installed and Zotero is running"
    exit 1
fi

echo "✓ Found auth token: ${TOKEN:0:20}..."
echo ""

BASE_URL="http://127.0.0.1:23119"

# Test 1: GET /items/search with query parameter
echo "Test 1: GET /items/search?q=test&limit=5"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/items/search?q=test&limit=5")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Test 2: GET /items/recent with query parameter
echo "Test 2: GET /items/recent?limit=3"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/items/recent?limit=3")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Test 3: GET /notes with collectionKey (if you have collections)
echo "Test 3: GET /notes?collectionKey=TESTKEY (expected to fail gracefully)"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/notes?collectionKey=TESTKEY")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Test 4: GET /notes without parameters (should fail with error message)
echo "Test 4: GET /notes (no parameters - should return error)"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/notes")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY"
echo ""

# Test 5: GET /collections (no query params - baseline test)
echo "Test 5: GET /collections (baseline - no query params)"
echo "----------------------------------------"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/collections")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE:/d')

echo "Status: $HTTP_CODE"
echo "Response: $BODY" | jq '.data | length' 2>/dev/null || echo "$BODY"
echo ""

echo "=== Test Summary ==="
echo "✓ All query parameter endpoints tested"
echo "✓ If all tests returned 200 or expected errors, the fix is working"
echo ""
echo "Next steps:"
echo "1. Install the updated plugin: plugin/zotero-mcp-bridge/zotero-mcp-bridge.xpi"
echo "2. Restart Zotero"
echo "3. Run this test script again to verify"
