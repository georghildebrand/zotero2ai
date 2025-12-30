Revised Execution DAG (Waves)

  Wave 1: Foundation

  PARALLEL:
  ├─ 1.1: Plugin Directory Structure
  └─ 4.1: Python Dependencies
  Duration: ~5 mins

  ---
  Wave 2: Security + HTTP Foundation (CRITICAL)

  SEQUENTIAL:
  ├─ 1.2: Authentication System (token generation, storage)
  ├─ 1.3: Production HTTP Server (body reading, UTF-8, Connection: close, OPTIONS)
  └─ 1.4: Request Handlers with Auth Enforcement
  Duration: ~40-50 mins
  Critical: Must be rock-solid before any endpoints

  ---
  Wave 3: Plugin Read Ops (Complete CRUD)

  PARALLEL:
  ├─ 2.1: GET /collections
  ├─ 2.2: GET /items/search, /items/recent
  ├─ 2.3: GET /notes (summaries)
  ├─ 2.4: GET /notes/{key} (full content) ⬅️ CRITICAL for CRUD
  └─ 5.2: Plugin Installation Guide (docs in parallel)
  Duration: ~20 mins

  ---
  Wave 4: Plugin Write Ops + Python Client

  PARALLEL:
  ├─ 3.1: POST /notes (create)
  ├─ 3.2: PUT /notes/{key} (update)
  └─ 4.2: Plugin HTTP Client with Auth
  Duration: ~20 mins

  ---
  Wave 5: MCP Integration

  SEQUENTIAL:
  ├─ 4.3: Friendly Name Generation (display-only)
  ├─ 4.4: Update MCP Server
  ├─ 4.5: list_notes Tool
  ├─ 4.6: read_note Tool (uses GET /notes/{key})
  └─ 4.7: create_or_extend_note Tool
  Duration: ~25 mins

  ---
  Wave 6: Testing

  PARALLEL:
  ├─ 5.1: Integration Tests
  └─ 5.1b: Contract Testing with JSON Schema
  Duration: ~20 mins

  ---
  Wave 7: Release

  5.3: Update README → 6.1: Build XPI → 6.2: CHANGELOG → 6.3: Tag Release
  Duration: ~10 mins

  ---
  Risk Register

  Risk 1: HTTP Body Reading Failures

  Impact: High
  Probability: Medium
  Mitigation:
  - Use Content-Length, NOT available()
  - Test with UTF-8 edge cases (emoji, non-ASCII)
  - Test with large payloads (>1KB)
  - Dedicated test in Wave 2 before any endpoints

  Risk 2: Authentication Token Exposure

  Impact: Critical
  Probability: Low
  Mitigation:
  - Bind to 127.0.0.1 only (loopback)
  - Token in environment variable, not config file
  - 256-bit cryptographically secure token
  - Clear docs about not committing tokens

  Risk 3: Resource Loading Breaks in Zotero 7

  Impact: High
  Probability: Medium
  Mitigation:
  - Use rootURI from bootstrap, NOT chrome:// URLs
  - Test plugin loads in actual Zotero 7
  - Explicit test in Wave 1

  Risk 4: Friendly Name Collisions

  Impact: Medium
  Probability: Low
  Mitigation:
  - Detect and report collisions in cache
  - Always show both friendly name AND key in listings
  - Require key for write operations if collision
  - Clear "display-only" documentation

  Risk 5: UTF-8 String Length vs Byte Length

  Impact: High
  Probability: Medium
  Mitigation:
  - Always use ConvertToByteArray for Content-Length
  - Test with multi-byte characters
  - Dedicated test in Wave 2
  - Use nsIScriptableUnicodeConverter for all conversions

  ---
  Definition of Done

  Plugin

  - Loads in Zotero 7 using rootURI (no chrome:// URLs)
  - Binds to 127.0.0.1 only (verified in logs)
  - Generates and stores 256-bit auth token
  - Token visible in Zotero UI
  - All endpoints require Bearer token auth
  - HTTP body reading uses Content-Length correctly
  - Content-Length calculated from UTF-8 byte length
  - Connection: close sent in all responses
  - OPTIONS returns 204 with CORS headers
  - GET /collections works
  - GET /items/search works
  - GET /items/recent works
  - GET /notes returns summaries (title, preview, metadata)
  - GET /notes/{key} returns full HTML content
  - POST /notes creates note
  - PUT /notes/{key} updates note
  - All endpoints tested with curl
  - Plugin builds as .xpi

  MCP Server

  - Reads ZOTERO_MCP_TOKEN from environment
  - Sends Bearer token in Authorization header
  - list_collections tool works
  - search_papers tool works
  - get_recent_papers tool works
  - list_notes shows friendly names + keys
  - read_note uses GET /notes/{key} endpoint
  - create_or_extend_note creates new notes
  - create_or_extend_note extends existing notes
  - Friendly names documented as display-only
  - Contract tests validate all plugin responses
  - Integration tests pass
  - No direct SQLite access (all via plugin)

  Documentation

  - Plugin installation guide complete
  - Auth token setup documented
  - Security model explained (localhost-only + token)
  - README updated with plugin requirement
  - CHANGELOG documents breaking changes
  - API endpoint documentation complete

  Security

  - Plugin binds loopback only (verified)
  - Auth token required on all endpoints (tested)
  - Token not in version control
  - Token generation uses crypto.getRandomValues
  - No SSRF vulnerabilities
  - No path traversal vulnerabilities