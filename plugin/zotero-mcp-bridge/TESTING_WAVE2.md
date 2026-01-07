# Testing: HTTP Server & Authentication

## Overview

This document describes testing for the HTTP server and authentication system:
- **Authentication System**: 256-bit token generation and Bearer token validation
- **Production HTTP Server**: Proper UTF-8 handling, Content-Length, Connection: close, CORS
- **Request Handlers**: Route handling with authentication enforcement

## What Was Implemented

### 1. Authentication System (`auth.js`)
- ✅ Cryptographically secure 256-bit token generation using `crypto.getRandomValues`
- ✅ Token storage in Zotero preferences (`extensions.zotero-mcp-bridge.authToken`)
- ✅ Bearer token validation
- ✅ Token retrieval for display in UI

### 2. Production HTTP Server (`server.js`)
- ✅ Binds to `127.0.0.1:23119` (loopback only)
- ✅ Proper UTF-8 body reading using Content-Length (NOT `available()`)
- ✅ UTF-8 Content-Length calculation using byte length
- ✅ `Connection: close` header on all responses
- ✅ OPTIONS method support for CORS preflight
- ✅ CORS headers on all responses
- ✅ Error handling with proper status codes

### 3. Request Handlers (`handlers.js`)
- ✅ Authentication enforcement on all routes
- ✅ Route definitions for all planned endpoints:
  - `GET /health` - Health check (implemented)
  - `GET /collections` - List collections (stub)
  - `GET /items/search` - Search items (stub)
  - `GET /items/recent` - Recent items (stub)
  - `GET /notes` - List notes (stub)
  - `GET /notes/{key}` - Get note detail (stub)
  - `POST /notes` - Create note (stub)
  - `PUT /notes/{key}` - Update note (stub)
- ✅ Proper 401 Unauthorized responses for missing/invalid tokens
- ✅ Proper 404 Not Found for unknown routes
- ✅ Proper 501 Not Implemented for stub endpoints

## Testing the Implementation

### Prerequisites
1. Zotero 7 installed
2. Plugin loaded in Zotero

### Manual Testing Steps

#### 1. Check Plugin Loads
1. Open Zotero
2. Check Error Console (Tools → Developer → Error Console)
3. Look for:
   ```
   MCP Bridge: Starting...
   AuthManager: Initializing...
   AuthManager: Generated new token (or Loaded existing token)
   AuthManager: Token = <64-character-hex-token>
   MCPServer: Listening on 127.0.0.1:23119
   MCPServer: Auth token = <64-character-hex-token>
   MCP Bridge: Started successfully
   ```

#### 2. Test OPTIONS (CORS Preflight)
```bash
curl -v -X OPTIONS http://127.0.0.1:23119/health
```

**Expected Response:**
- Status: `204 No Content`
- Headers:
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, Authorization`
  - `Allow: GET, POST, PUT, DELETE, OPTIONS`
  - `Connection: close`

#### 3. Test Authentication Enforcement
```bash
# Without token (should fail)
curl -v http://127.0.0.1:23119/health
```

**Expected Response:**
- Status: `401 Unauthorized`
- Body:
  ```json
  {
    "error": "Unauthorized",
    "message": "Missing or invalid Bearer token"
  }
  ```

#### 4. Test Health Endpoint with Valid Token
```bash
# Get token from Zotero Error Console output
TOKEN="<your-64-char-token-here>"

curl -v -H "Authorization: Bearer $TOKEN" http://127.0.0.1:23119/health
```

**Expected Response:**
- Status: `200 OK`
- Headers:
  - `Content-Type: application/json; charset=utf-8`
  - `Connection: close`
  - `Content-Length: <byte-length>`
- Body:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "timestamp": "2025-12-30T08:29:06.123Z"
  }
  ```

#### 5. Test UTF-8 Handling (POST with emoji)
```bash
curl -v -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test 🚀 Note","content":"Hello 世界"}' \
  http://127.0.0.1:23119/notes
```

**Expected Response:**
- Status: `501 Not Implemented`
- Body confirms UTF-8 was handled correctly (no encoding errors)

#### 6. Test 404 for Unknown Routes
```bash
curl -v -H "Authorization: Bearer $TOKEN" http://127.0.0.1:23119/unknown
```

**Expected Response:**
- Status: `404 Not Found`
- Body:
  ```json
  {
    "error": "Not Found",
    "message": "No handler for GET /unknown"
  }
  ```

## Security Verification

### ✅ Loopback Only
The server binds to `127.0.0.1` only, preventing external access.

**Verify:**
```bash
# From another machine on the network (should fail)
curl http://<your-ip>:23119/health
```

### ✅ Token Security
- Token is 256 bits (64 hex characters)
- Generated using `crypto.getRandomValues` (cryptographically secure)
- Stored in Zotero preferences (not in code/version control)
- Required on all endpoints except OPTIONS

### ✅ HTTP Security
- `Connection: close` prevents connection reuse attacks
- CORS headers allow cross-origin requests (needed for MCP)
- Content-Length calculated from UTF-8 byte length (prevents truncation)

## Known Limitations (By Design)

1. **Stub Endpoints**: All endpoints except `/health` return `501 Not Implemented`
   - This is intentional - they will be implemented in Waves 3-4

2. **No HTTPS**: Server uses HTTP, not HTTPS
   - Acceptable because it's localhost-only
   - Token provides authentication

3. **Single Token**: One token for all clients
   - Acceptable for localhost-only use case
   - Can be reset by clearing preferences

## Next Steps (Wave 3)

Wave 3 will implement the read operations:
- `GET /collections` - List all collections
- `GET /items/search` - Search items by query
- `GET /items/recent` - Get recent items
- `GET /notes` - List notes with summaries
- `GET /notes/{key}` - Get full note content

## Troubleshooting

### Server doesn't start
- Check Zotero Error Console for errors
- Verify port 23119 is not in use: `lsof -i :23119`

### Token not showing in logs
- Check preferences: Tools → Preferences → Advanced → Config Editor
- Search for `extensions.zotero-mcp-bridge.authToken`

### Authentication always fails
- Verify token matches exactly (copy from logs)
- Check for extra spaces in `Authorization` header
- Ensure format is `Bearer <token>` (note the space)

### UTF-8 characters corrupted
- Check Content-Type header includes `charset=utf-8`
- Verify Content-Length matches byte length, not character length
