#!/bin/bash

# Test script for /items/search and /items/recent endpoints
# Tests Task 2.2 implementation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
HOST="127.0.0.1"
PORT="23119"
BASE_URL="http://${HOST}:${PORT}"

# Token should be passed as first argument or read from environment
TOKEN="${1:-$ZOTERO_MCP_TOKEN}"

if [ -z "$TOKEN" ]; then
    echo -e "${RED}ERROR: Token not provided${NC}"
    echo "Usage: $0 <token>"
    echo "   or: ZOTERO_MCP_TOKEN=<token> $0"
    echo ""
    echo "Get the token from Zotero Error Console:"
    echo "  Tools → Developer → Error Console"
    echo "  Look for: 'MCPServer: Auth token = <token>'"
    exit 1
fi

echo "Testing Items Endpoints - Task 2.2"
echo "=================================="
echo ""

# Test counter
PASSED=0
FAILED=0

# Helper function to run a test
run_test() {
    local name="$1"
    local expected_status="$2"
    shift 2
    local curl_args=("$@")
    
    echo -n "Testing: $name ... "
    
    # Run curl and capture status code
    response=$(curl -s -w "\n%{http_code}" "${curl_args[@]}")
    status_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | head -n -1)
    
    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP $status_code)"
        PASSED=$((PASSED + 1))
        if [ -n "$body" ]; then
            echo "  Response preview:"
            echo "$body" | python3 -m json.tool 2>/dev/null | head -n 20 || echo "$body" | head -c 200
            echo ""
        fi
    else
        echo -e "${RED}FAIL${NC} (Expected $expected_status, got $status_code)"
        FAILED=$((FAILED + 1))
        if [ -n "$body" ]; then
            echo "  Response: $body"
        fi
    fi
    echo ""
}

# Test 1: Search without query parameter (should fail)
echo "=== Test 1: Search Validation ==="
run_test "GET /items/search without 'q' parameter" "400" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/search"

# Test 2: Search with query parameter
echo "=== Test 2: Search Functionality ==="
run_test "GET /items/search?q=test" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/search?q=test"

# Test 3: Search with limit parameter
run_test "GET /items/search?q=the&limit=3" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/search?q=the&limit=3"

# Test 4: Recent items (default limit)
echo "=== Test 3: Recent Items ==="
run_test "GET /items/recent (default limit)" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/recent"

# Test 5: Recent items with custom limit
run_test "GET /items/recent?limit=10" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/recent?limit=10"

# Test 6: Recent items with limit=1
run_test "GET /items/recent?limit=1" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/recent?limit=1"

# Summary
echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="
echo -e "Passed: ${GREEN}${PASSED}${NC}"
echo -e "Failed: ${RED}${FAILED}${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed! ✗${NC}"
    exit 1
fi
