#!/bin/bash
# Test script for GET /notes/{key} endpoint
# Tests the individual note retrieval functionality

set -e

# Configuration
BASE_URL="http://localhost:23120"
TOKEN_FILE="$HOME/.zotero-mcp-token"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "Testing GET /notes/{key} Endpoint"
echo "========================================="
echo ""

# Check if token file exists
if [ ! -f "$TOKEN_FILE" ]; then
    echo -e "${RED}Error: Token file not found at $TOKEN_FILE${NC}"
    echo "Please ensure the Zotero plugin is running and has generated a token."
    exit 1
fi

# Read the token
TOKEN=$(cat "$TOKEN_FILE")
echo -e "${GREEN}✓ Token loaded from $TOKEN_FILE${NC}"
echo ""

# Test 1: Get list of notes first to find a valid key
echo "Test 1: Getting list of notes to find a valid key..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/notes")
echo "Response: $RESPONSE"

# Extract first note key (this is a simple extraction, might need jq for production)
NOTE_KEY=$(echo "$RESPONSE" | grep -o '"key":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$NOTE_KEY" ]; then
    echo -e "${YELLOW}Warning: No notes found in library. Creating a test note might be needed.${NC}"
    echo ""
    echo "You can create a test note in Zotero or use the POST /notes endpoint."
    exit 0
fi

echo -e "${GREEN}✓ Found note with key: $NOTE_KEY${NC}"
echo ""

# Test 2: Get individual note by key
echo "Test 2: Getting note with key $NOTE_KEY..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/notes/$NOTE_KEY")
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Check if response contains expected fields
if echo "$RESPONSE" | grep -q '"key"' && echo "$RESPONSE" | grep -q '"note"'; then
    echo -e "${GREEN}✓ Note retrieved successfully with full content${NC}"
else
    echo -e "${RED}✗ Failed to retrieve note or missing expected fields${NC}"
    exit 1
fi
echo ""

# Test 3: Try to get non-existent note
echo "Test 3: Testing with non-existent note key..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE_URL/notes/NONEXISTENT123")
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

if echo "$RESPONSE" | grep -q '"error".*"Not Found"'; then
    echo -e "${GREEN}✓ Correctly returns 404 for non-existent note${NC}"
else
    echo -e "${YELLOW}⚠ Unexpected response for non-existent note${NC}"
fi
echo ""

# Test 4: Test without authentication
echo "Test 4: Testing without authentication (should fail)..."
RESPONSE=$(curl -s "$BASE_URL/notes/$NOTE_KEY")
echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

if echo "$RESPONSE" | grep -q '"error".*"Unauthorized"'; then
    echo -e "${GREEN}✓ Correctly rejects unauthenticated request${NC}"
else
    echo -e "${RED}✗ Should have rejected unauthenticated request${NC}"
    exit 1
fi
echo ""

echo "========================================="
echo -e "${GREEN}All tests completed!${NC}"
echo "========================================="
