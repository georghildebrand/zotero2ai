#!/bin/bash

# Wave 2 Test Script
# Tests authentication, HTTP server, and request handlers

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

echo "Testing Zotero MCP Bridge - Wave 2"
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
            echo "  Response: $body" | head -c 100
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

# Test 1: OPTIONS (CORS preflight)
echo "=== Test 1: CORS Preflight ==="
run_test "OPTIONS /health" "204" \
    -X OPTIONS \
    "${BASE_URL}/health"

# Test 2: No authentication (should fail)
echo "=== Test 2: Authentication Enforcement ==="
run_test "GET /health without token" "401" \
    "${BASE_URL}/health"

# Test 3: Invalid token (should fail)
run_test "GET /health with invalid token" "401" \
    -H "Authorization: Bearer invalid-token-12345" \
    "${BASE_URL}/health"

# Test 4: Valid authentication
echo "=== Test 3: Valid Authentication ==="
run_test "GET /health with valid token" "200" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/health"

# Test 5: Unknown route (should 404)
echo "=== Test 4: Unknown Routes ==="
run_test "GET /unknown" "404" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/unknown"

# Test 6: Stub endpoints (should 501)
echo "=== Test 5: Stub Endpoints ==="
run_test "GET /collections" "501" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/collections"

run_test "GET /items/search" "501" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/search?q=test"

run_test "GET /items/recent" "501" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/items/recent"

run_test "GET /notes" "501" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/notes"

run_test "GET /notes/ABC123" "501" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${BASE_URL}/notes/ABC123"

# Test 7: UTF-8 handling
echo "=== Test 6: UTF-8 Handling ==="
run_test "POST /notes with UTF-8 (emoji + CJK)" "501" \
    -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"title":"Test 🚀 Note","content":"Hello 世界 مرحبا"}' \
    "${BASE_URL}/notes"

# Test 8: Large payload
echo "=== Test 7: Large Payload ==="
large_payload=$(printf '{"content":"%s"}' "$(head -c 2000 /dev/urandom | base64)")
run_test "POST /notes with large payload (>1KB)" "501" \
    -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$large_payload" \
    "${BASE_URL}/notes"

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
