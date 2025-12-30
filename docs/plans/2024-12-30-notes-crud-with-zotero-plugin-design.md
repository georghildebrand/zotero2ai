# Zotero Notes CRUD with Plugin Architecture - Design Document

**Date:** 2024-12-30
**Status:** Approved
**Version:** 1.0

## Overview

This design adds full CRUD (Create, Read, Update, Delete) capabilities for Zotero notes to the `zotero2ai` MCP server by building a Zotero 7 plugin that exposes a local HTTP API. This architectural shift moves all Zotero interactions through the plugin's native JavaScript APIs, eliminating the need for web API keys for basic operations and providing a cleaner, more maintainable foundation.

### Key Features

1. **Full Note Operations:** Create, read, update, and delete notes via AI agents
2. **Human-Readable Identifiers:** Notes get friendly names like "lucky-chicken" for natural conversation
3. **Smart Note Extension:** AI automatically generates semantic section headers when extending notes
4. **AI-Generated Marking:** Notes are tagged and structured to indicate AI authorship
5. **Plugin Architecture:** Single source of truth using Zotero's internal APIs

### User Experience

Users can interact with notes naturally:
- "List notes in my ML collection"
- "Extend lucky-chicken with these findings"
- "Create a new note about this paper's methodology"

Each note has:
- A clear first line acting as a title/descriptor
- Semantic sections with auto-generated headers
- `ai-generated` tag in Zotero for filtering

---

## Architecture

### System Components

**1. Zotero Plugin (`zotero-mcp-bridge`)**
- Minimal JavaScript plugin for Zotero 7
- Starts HTTP server on `http://localhost:23120` when Zotero launches
- Uses Zotero's internal JavaScript APIs (`Zotero.Items`, `Zotero.Collections`, etc.)
- Stateless: each request is independent
- Single responsibility: bridge between MCP and Zotero internals

**2. MCP Server (`zotero2ai`)**
- Existing Python codebase
- Exposes tools to AI agents (ChatGPT, Claude, etc.)
- Communicates with plugin via HTTP client
- Handles: human-readable ID generation, prompt formatting, error messages
- No direct Zotero database/API access anymore

**3. Communication Protocol**
- Plugin exposes REST endpoints: `/collections`, `/items/search`, `/notes/list`, `/notes/create`, `/notes/update`
- JSON request/response format
- Simple error handling: HTTP status codes + error messages
- Connection check: MCP server pings plugin on startup

### Architecture Diagram

```
┌─────────────┐      stdio      ┌──────────────┐   HTTP/JSON   ┌─────────────────┐
│ AI Agent    │ ◄──────────────► │ MCP Server   │ ◄────────────► │ Zotero Plugin   │
│ (ChatGPT)   │                  │ (Python)     │  :23120       │ (JavaScript)    │
└─────────────┘                  └──────────────┘                └────────┬────────┘
                                                                          │
                                                                   ┌──────▼──────┐
                                                                   │  Zotero 7   │
                                                                   │  Internal   │
                                                                   │  APIs       │
                                                                   └─────────────┘
```

### Future Enhancement

WebSocket support (post-v1) for:
- Real-time updates when notes change in Zotero
- Bidirectional communication
- Push notifications to MCP server

---

## Plugin REST API

### Endpoints

#### Collections

```http
GET /collections

Response: [
  {
    "key": "ABC123",
    "name": "Machine Learning",
    "parentKey": null,
    "fullPath": "Papers / Machine Learning",
    "libraryID": 1
  }
]
```

#### Items/Papers

```http
GET /items/search?q=transformer&limit=10
GET /items/recent?limit=5

Response: [
  {
    "key": "XYZ789",
    "itemType": "journalArticle",
    "title": "Attention Is All You Need",
    "creators": ["Vaswani, Ashish", ...],
    "date": "2017",
    "tags": ["deep-learning"],
    "collections": ["ABC123"]
  }
]
```

#### Notes - List/Read

```http
GET /notes?collectionKey=ABC123
GET /notes?parentItemKey=XYZ789

Response: [
  {
    "key": "NOTE001",
    "note": "Critical analysis of methodology\n\n## Key findings\n...",
    "tags": ["ai-generated"],
    "parentItemKey": "XYZ789",  // null if standalone
    "collections": ["ABC123"],
    "dateAdded": "2024-12-30T10:00:00Z",
    "dateModified": "2024-12-30T15:30:00Z"
  }
]
```

#### Notes - Create/Update

```http
POST /notes/create
Content-Type: application/json

Body: {
  "note": "First line descriptor\n\nContent here",
  "tags": ["ai-generated"],
  "parentItemKey": "XYZ789",  // optional
  "collections": ["ABC123"]    // optional
}

Response: {
  "key": "NOTE002",
  "success": true
}
```

```http
PUT /notes/update
Content-Type: application/json

Body: {
  "key": "NOTE001",
  "note": "Updated content..."  // full content, not delta
}

Response: {
  "success": true
}
```

#### Health Check

```http
GET /health

Response: {
  "status": "ok",
  "zoteroVersion": "7.0.0"
}
```

---

## MCP Server Implementation

### Human-Readable ID Generation

Use `coolname` library to generate deterministic names from note keys:

```python
from coolname import generate_slug
import hashlib

def get_friendly_name(note_key: str) -> str:
    """Generate deterministic friendly name from note key.

    Same key always produces same name (e.g., "lucky-chicken").
    """
    seed = int(hashlib.md5(note_key.encode()).hexdigest()[:8], 16)
    return generate_slug(2, seed=seed)
```

### MCP Tools

#### Existing Tools (Updated)

These now call the plugin instead of SQLite/Local HTTP API:
- `list_collections()` → `GET /collections`
- `search_papers(query)` → `GET /items/search`
- `get_recent_papers(limit)` → `GET /items/recent`

#### New Note Tools

**1. `list_notes(collection_key=None, parent_item_key=None)`**

Fetches notes from plugin and presents them with friendly names:

```
Found 2 notes in collection:
1. lucky-chicken (NOTE001): "Critical analysis of methodology"
   Created: 2 days ago, Modified: 1 day ago
2. brave-turtle (NOTE002): "Comparison with Smith et al 2023"
   Created: yesterday
```

**2. `read_note(friendly_name_or_key)`**

Resolves friendly name to key (maintain in-memory cache) and fetches full content.

**3. `create_or_extend_note(content, collection_key=None, parent_item_key=None, target_note=None)`**

Core note operation tool:
- If `target_note` specified: extends existing note
- Otherwise: creates new note
- Auto-generates section header for extensions
- Adds `ai-generated` tag
- Ensures first line is descriptive

### Note Extension Logic

```python
if extending:
    existing_content = read_note(target_note)
    section_header = generate_section_header(content)  # AI-generated
    new_content = f"{existing_content}\n\n## {section_header}\n{content}"
    update_note(note_key, new_content)
else:
    first_line = generate_first_line(content)  # AI-generated
    formatted = f"{first_line}\n\n{content}"
    create_note(formatted, collection_key, parent_item_key)
```

### Section Header Generation

Simple prompt to AI model:
```
Given this note content to be added:
"{content}"

Generate a concise markdown header (2-4 words) that describes this content.
Examples: "Contradicting evidence", "Implementation notes", "Related work"

Return only the header text, no "##" prefix.
```

---

## Error Handling

### Connection Failures

**Plugin not reachable:**
- MCP server pings `/health` on first tool use
- If fails, return clear error:
  ```
  Cannot connect to Zotero plugin. Please ensure:
  1. Zotero 7 is running
  2. zotero-mcp-bridge plugin is installed and enabled
  3. Plugin server is running on localhost:23120
  ```
- Cache connection status for 30s to avoid repeated checks

**Zotero not running:**
- Plugin HTTP server only runs when Zotero is open
- MCP tools gracefully fail with user-friendly message
- No fallback to SQLite (keep architecture simple)

### Note Operations

**Ambiguous friendly names:**

If friendly name collision occurs (rare but possible):
```
Multiple notes match 'lucky-chicken':
1. lucky-chicken (in collection 'Papers/ML', created 2024-12-28)
2. lucky-chicken (attached to 'Attention Is All You Need', created 2024-12-29)

Please specify using note key directly: NOTE001 or NOTE002
```

**Empty/invalid first line:**
- If note doesn't start with descriptor, show `[No title]` in listings
- When extending, AI generates section header regardless

**Concurrent modifications:**
- No locking mechanism (Zotero handles internally)
- Last write wins (acceptable for single-user scenario)

**Tag conflicts:**
- Always add `ai-generated` tag
- Preserve existing tags when updating

### HTTP Errors

**Plugin returns error:**
- Parse JSON error message from plugin
- Pass through to user with context:
  ```
  Failed to create note: [Plugin error message]
  ```

**Timeout (30s default):**
- Large note operations might take time
- Return: "Operation timed out. Check Zotero to see if it completed."

---

## Zotero Plugin Implementation

### Plugin Structure

```
zotero-mcp-bridge/
├── manifest.json           # Zotero 7 plugin manifest
├── bootstrap.js            # Plugin entry point
├── content/
│   ├── server.js          # HTTP server implementation
│   ├── handlers.js        # Request handlers (collections, notes, etc.)
│   └── utils.js           # Helper functions
└── install.rdf            # Legacy compatibility (optional)
```

### Key Zotero APIs

**Collections:**
```javascript
Zotero.Collections.getAll()
Zotero.Collections.get(collectionID)
collection.getName()
collection.getParent()
```

**Items/Papers:**
```javascript
Zotero.Items.get(itemID)
item.getField('title')
item.getCreators()
item.getTags()
Zotero.Items.search(libraryID, { title: query })
```

**Notes:**
```javascript
// Create note
let note = new Zotero.Item('note')
note.setNote(content)  // HTML or plain text
note.addTag(tagName)
note.setCollections([collectionID])
note.parentItemID = parentID  // if child note
await note.saveTx()

// Read notes
let notes = Zotero.Items.get(noteIDs)
note.getNote()  // Returns HTML content
note.getTags()

// Update note
note.setNote(newContent)
await note.saveTx()
```

### HTTP Server

Use Zotero's built-in HTTP capabilities or Mozilla components:

```javascript
// Option 1: nsIServerSocket
const server = Components.classes["@mozilla.org/network/server-socket;1"]
    .createInstance(Components.interfaces.nsIServerSocket);
server.init(23120, false, -1);
server.asyncListen(requestHandler);

// Option 2: Check if Zotero 7 has newer HTTP server infrastructure
```

### Plugin Lifecycle

- **Startup:** Initialize HTTP server when Zotero launches
- **Shutdown:** Close server gracefully on Zotero exit
- **No persistence:** Stateless, all data lives in Zotero database

---

## Testing Strategy

### Plugin Testing

**Manual testing during development:**
- Zotero JavaScript console: Tools → Developer → Run JavaScript
- Test API calls directly:
  ```javascript
  Zotero.debug("Testing note creation...")
  let note = new Zotero.Item('note')
  note.setNote("Test content")
  await note.saveTx()
  ```

**HTTP endpoint testing:**
```bash
curl http://localhost:23120/collections
curl http://localhost:23120/health
curl -X POST http://localhost:23120/notes/create \
  -H "Content-Type: application/json" \
  -d '{"note": "Test", "tags": ["ai-generated"]}'
```

**Edge cases:**
- Non-ASCII characters, very long notes
- Notes in different contexts (standalone, child, multiple collections)
- Tag handling

### MCP Server Testing

**Unit tests (pytest):**
```python
def test_friendly_name_deterministic():
    assert get_friendly_name("ABC123") == get_friendly_name("ABC123")

def test_note_extension_adds_section():
    original = "Title\n\nOriginal content"
    extended = extend_note_content(original, "New content", "Additional insights")
    assert "## Additional insights" in extended
```

**Integration tests:**
- Mock plugin HTTP responses
- Test each MCP tool with various inputs
- Verify error handling paths

**End-to-end testing:**
- Requires Zotero running with plugin installed
- Manual test cases for release validation

### No Automated Plugin Tests (v1)

Plugin code is simple HTTP handlers. Manual testing is acceptable for v1. Future: explore Zotero plugin test frameworks.

---

## Deployment & Installation

### Plugin Installation

**Option 1: Manual Install**
1. Download `.xpi` file (zipped plugin)
2. Zotero → Tools → Add-ons → Install Add-on From File
3. Restart Zotero
4. Verify: `curl http://localhost:23120/health`

**Option 2: Zotero Plugin Repository (future)**
- Submit to official directory
- Auto-updates possible

### MCP Server Configuration

**Simplified configuration (no API key needed!):**

```json
{
  "mcpServers": {
    "zotero2ai": {
      "command": "uv",
      "args": ["run", "mcp-zotero2ai", "run"],
      "env": {
        "ZOTERO_DATA_DIR": "/Users/you/Zotero"
      }
    }
  }
}
```

**Optional environment variables:**
- `ZOTERO_PLUGIN_URL` (default: `http://localhost:23120`)
- Remove `ZOTERO_API_KEY` and `ZOTERO_USER_ID` requirements

### Documentation Updates

**README.md:**
- Add "Prerequisites: Zotero 7 + zotero-mcp-bridge plugin"
- Link to plugin installation guide
- Update features: "No API key needed!"

**New files:**
- `docs/PLUGIN_INSTALLATION.md` - Step-by-step plugin setup
- `plugin/README.md` - Plugin development guide

### Migration Path

**Breaking change: v2.0.0**
- Requires plugin installation
- Document in CHANGELOG.md
- Provide migration guide from v1.x (API-based) to v2.0 (plugin-based)
- Keep v1.x branch for users who can't use plugin

---

## Dependencies

### New Python Dependencies

```toml
[project.dependencies]
coolname = ">=2.2.0"  # Human-readable ID generation
```

### Plugin Dependencies

None - uses Zotero's built-in APIs and Mozilla components.

---

## Success Criteria

1. **Plugin successfully starts** HTTP server on Zotero launch
2. **All endpoints respond** correctly to test requests
3. **MCP tools work end-to-end** in ChatGPT/Claude
4. **Friendly names are consistent** across sessions
5. **Note extensions preserve** existing content and add sections
6. **Error messages are helpful** when plugin unavailable
7. **Documentation enables** users to install and use successfully

---

## Open Questions & Future Work

### Future Enhancements

1. **WebSocket support** for real-time updates
2. **Delete note tool** (not in v1 scope)
3. **Batch operations** for performance
4. **Search note content** (full-text search)
5. **Note templates** for consistent formatting
6. **Attachment handling** (PDFs, images in notes)

### Decisions Deferred

1. **Port conflict handling** - What if 23120 is in use?
2. **Multi-library support** - Current design assumes single library
3. **Plugin auto-updates** - Manual updates for v1
4. **Internationalization** - English-only error messages for v1

---

## Implementation Phases

### Phase 1: Plugin Foundation
- Set up plugin project structure
- Implement basic HTTP server
- Add `/health` endpoint
- Test plugin loads in Zotero 7

### Phase 2: Read Operations
- Implement `/collections`, `/items/search`, `/items/recent`
- Implement `/notes` (list/read)
- Test all read endpoints

### Phase 3: Write Operations
- Implement `/notes/create`
- Implement `/notes/update`
- Test note CRUD operations

### Phase 4: MCP Server Integration
- Add `coolname` dependency
- Implement friendly name generation
- Update existing tools to use plugin
- Implement new note tools
- Add section header generation

### Phase 5: Testing & Documentation
- Write unit tests
- Write integration tests
- Create plugin installation guide
- Update README and docs
- Manual end-to-end testing

### Phase 6: Release
- Build `.xpi` file
- Create CHANGELOG
- Tag v2.0.0
- Publish to GitHub releases
