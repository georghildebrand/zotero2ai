# Zotero Bridge Agentic Workflow Improvements Plan

**Created:** 2026-01-10  
**Status:** Planning  
**Priority:** High

## Executive Summary

This plan addresses five critical improvements to make the Zotero MCP Bridge more efficient, reliable, and agent-friendly. The improvements focus on reducing token usage, preventing truncation, fixing pagination bugs, improving search accuracy, and adding caching for performance.

---

## 1. Add `list_collection_children` Tool (The "ls" Command)

### Problem
Currently, agents must choose between:
- **Listing everything**: Huge, slow, gets truncated (missing folders)
- **Fuzzy searching**: Hit-or-miss, unreliable for navigation

This creates a poor user experience where agents can't reliably navigate the collection hierarchy.

### Solution
Implement a dedicated tool for directory-style walking:

**Tool Name:** `list_collection_children(parent_key, library_id?)`

**Behavior:**
- Returns **only** immediate sub-collections and items of the specified folder
- Does NOT recurse into children
- Mimics Unix `ls` command behavior

**Benefits:**
- Drastically reduces token usage (only immediate children vs entire tree)
- Prevents timeouts and connection resets
- Ensures agents see ALL files in a folder without truncation
- Enables reliable step-by-step navigation

### Implementation Details

#### API Endpoint
```
GET /collections/{key}/children?libraryID={id}
```

**Response Format:**
```json
{
  "success": true,
  "data": {
    "collections": [
      {
        "key": "ABC123",
        "name": "Subfolder 1",
        "childCount": 5
      }
    ],
    "items": [
      {
        "key": "XYZ789",
        "title": "Paper Title",
        "itemType": "journalArticle"
      }
    ],
    "totalCollections": 10,
    "totalItems": 25
  }
}
```

#### Code Changes

**File:** `plugin/zotero-mcp-bridge/content/handlers.js`

Add new handler method:
```javascript
async handleGetCollectionChildren(request) {
    try {
        const pathParts = request.path.split('/');
        const collectionKey = pathParts[2];
        const libraryIDParam = request.query.libraryID;

        if (!collectionKey) {
            return MCPUtils.formatError("Missing collection key in path");
        }

        // Find the collection
        let collection = null;
        if (libraryIDParam) {
            collection = Zotero.Collections.getByLibraryAndKey(
                parseInt(libraryIDParam), 
                collectionKey
            );
        } else {
            const libraries = Zotero.Libraries.getAll();
            for (const lib of libraries) {
                collection = Zotero.Collections.getByLibraryAndKey(lib.id, collectionKey);
                if (collection) break;
            }
        }

        if (!collection) {
            return { statusCode: 404, body: { error: "Collection not found" } };
        }

        // Get immediate children only
        const childCollections = collection.getChildCollections();
        const childItems = collection.getChildItems(false, false); // no deleted, no notes

        const collections = childCollections.map(child => ({
            key: child.key,
            name: child.name,
            childCount: child.getChildCollections().length,
            libraryID: child.libraryID
        }));

        // Get basic item info (lightweight)
        const items = [];
        for (const itemID of childItems.slice(0, 100)) { // Limit to 100 items
            const item = await Zotero.Items.getAsync(itemID);
            if (item) {
                items.push({
                    key: item.key,
                    title: item.getField('title') || '',
                    itemType: Zotero.ItemTypes.getName(item.itemTypeID)
                });
            }
        }

        return MCPUtils.formatSuccess({
            collections: collections,
            items: items,
            totalCollections: childCollections.length,
            totalItems: childItems.length
        });
    } catch (e) {
        Zotero.debug("MCP Error handleGetCollectionChildren: " + e);
        return { statusCode: 500, body: { error: e.toString() } };
    }
}
```

Add route in `handle()` method:
```javascript
if (method === "GET" && path.match(/^\/collections\/[A-Z0-9]+\/children$/)) {
    return await this.handleGetCollectionChildren(request);
}
```

#### MCP Server Changes

**File:** `src/zotero2ai/server.py`

Add new tool:
```python
@self.mcp.tool()
async def list_collection_children(
    collection_key: str,
    library_id: Optional[int] = None
) -> str:
    """
    List immediate children (sub-collections and items) of a collection.
    
    This is like 'ls' for Zotero - shows only direct children, not recursive.
    Use this to navigate the collection hierarchy step-by-step.
    
    Args:
        collection_key: The key of the parent collection
        library_id: Optional library ID to search in
        
    Returns:
        JSON with collections and items arrays
    """
    params = {}
    if library_id:
        params['libraryID'] = library_id
        
    response = await self._make_request(
        "GET",
        f"/collections/{collection_key}/children",
        params=params
    )
    return json.dumps(response, indent=2)
```

---

## 2. Fix Pagination & Limits (The "Missing Folder" Bug)

### Problem
Large collections (like "00 Projects" with 20+ subfolders) are truncated because:
- Zotero API limits responses to 50-100 items per page
- The bridge grabs "Page 1" and stops
- No pagination logic exists to fetch remaining items

### Solution
Implement proper pagination with configurable limits and automatic page fetching.

### Implementation Details

#### Code Changes

**File:** `plugin/zotero-mcp-bridge/content/handlers.js`

Update `handleGetCollections()` to support pagination:

```javascript
async handleGetCollections(request) {
    try {
        const libraryIDParam = request.query.libraryID;
        const parentKey = request.query.parentKey;
        const limit = parseInt(request.query.limit || "100");
        const start = parseInt(request.query.start || "0");
        const sort = request.query.sort || "title"; // Default sort by title

        let result = [];
        let allCollections = [];

        // First, gather ALL collections (no pagination at Zotero API level needed
        // because getByLibrary() returns everything)
        if (parentKey === 'root') {
            if (libraryIDParam) {
                const collections = Zotero.Collections.getByLibrary(parseInt(libraryIDParam));
                for (const collection of collections) {
                    if (!collection.parentKey) {
                        allCollections.push(collection);
                    }
                }
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    const collections = Zotero.Collections.getByLibrary(lib.id);
                    for (const collection of collections) {
                        if (!collection.parentKey) {
                            allCollections.push(collection);
                        }
                    }
                }
            }
        } else if (parentKey) {
            let parent = null;
            if (libraryIDParam) {
                parent = Zotero.Collections.getByLibraryAndKey(parseInt(libraryIDParam), parentKey);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    parent = Zotero.Collections.getByLibraryAndKey(lib.id, parentKey);
                    if (parent) break;
                }
            }

            if (!parent) return MCPUtils.formatError(`Collection '${parentKey}' not found`);
            allCollections = parent.getChildCollections();
        } else {
            // All collections
            if (libraryIDParam) {
                allCollections = Zotero.Collections.getByLibrary(parseInt(libraryIDParam));
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    const collections = Zotero.Collections.getByLibrary(lib.id);
                    allCollections = allCollections.concat(collections);
                }
            }
        }

        // Sort collections
        allCollections.sort((a, b) => {
            if (sort === 'title' || sort === 'name') {
                return a.name.localeCompare(b.name);
            } else if (sort === 'dateAdded') {
                return new Date(b.dateAdded) - new Date(a.dateAdded);
            }
            return 0;
        });

        // Apply pagination
        const total = allCollections.length;
        const paginatedCollections = allCollections.slice(start, start + limit);

        // Format results
        for (const col of paginatedCollections) {
            result.push(this._formatCollection(col));
        }

        Zotero.debug(`MCP: Returning ${result.length} of ${total} collections (start=${start}, limit=${limit})`);
        
        return {
            statusCode: 200,
            body: {
                success: true,
                data: result,
                pagination: {
                    total: total,
                    start: start,
                    limit: limit,
                    hasMore: (start + limit) < total
                }
            }
        };
    } catch (e) {
        Zotero.debug("MCP Error handleGetCollections: " + e);
        return { statusCode: 500, body: { error: e.toString() } };
    }
}
```

#### MCP Server Changes

**File:** `src/zotero2ai/server.py`

Update `list_collections()` to handle pagination:

```python
@self.mcp.tool()
async def list_collections(
    library_id: Optional[int] = None,
    parent_key: Optional[str] = None,
    limit: int = 100,
    start: int = 0
) -> str:
    """
    List Zotero collections with pagination support.
    
    Args:
        library_id: Optional library ID to filter by
        parent_key: Optional parent collection key ('root' for top-level)
        limit: Maximum number of collections to return (default: 100)
        start: Starting offset for pagination (default: 0)
        
    Returns:
        JSON with collections array and pagination metadata
    """
    params = {
        'limit': limit,
        'start': start,
        'sort': 'title'
    }
    if library_id:
        params['libraryID'] = library_id
    if parent_key:
        params['parentKey'] = parent_key
        
    response = await self._make_request("GET", "/collections", params=params)
    
    # Auto-fetch remaining pages if truncated
    if response.get('pagination', {}).get('hasMore'):
        logger.info(f"Collection list truncated. Total: {response['pagination']['total']}, "
                   f"fetched: {len(response['data'])}")
    
    return json.dumps(response, indent=2)
```

---

## 3. Improve Search Scoring (Fuzzy Match Issues)

### Problem
- Search for "2023-11 Blog Posts" fails
- Search for "2023-11" works
- Token-based matching would improve reliability

### Solution
Implement intelligent token-based fuzzy matching with path inclusion.

### Implementation Details

**File:** `plugin/zotero-mcp-bridge/content/utils.js`

Add fuzzy matching utility:

```javascript
static fuzzyMatchScore(query, text, fullPath) {
    // Normalize inputs
    const queryLower = query.toLowerCase().trim();
    const textLower = text.toLowerCase();
    const pathLower = fullPath.toLowerCase();
    
    // Exact match = highest score
    if (textLower === queryLower) return 1000;
    if (pathLower === queryLower) return 900;
    
    // Contains exact query
    if (textLower.includes(queryLower)) return 800;
    if (pathLower.includes(queryLower)) return 700;
    
    // Token-based matching
    const queryTokens = queryLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);
    const textTokens = textLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);
    const pathTokens = pathLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);
    
    let matchedTokens = 0;
    let partialMatches = 0;
    
    for (const qToken of queryTokens) {
        // Check text tokens
        for (const tToken of textTokens) {
            if (tToken === qToken) {
                matchedTokens++;
                break;
            } else if (tToken.includes(qToken) || qToken.includes(tToken)) {
                partialMatches++;
            }
        }
        
        // Check path tokens
        for (const pToken of pathTokens) {
            if (pToken === qToken) {
                matchedTokens += 0.5; // Path matches worth less than name matches
                break;
            }
        }
    }
    
    // Calculate score based on token matches
    const tokenRatio = matchedTokens / queryTokens.length;
    const partialRatio = partialMatches / queryTokens.length;
    
    if (tokenRatio >= 0.8) return 600; // 80%+ tokens match
    if (tokenRatio >= 0.6) return 500; // 60%+ tokens match
    if (tokenRatio >= 0.4) return 400; // 40%+ tokens match
    if (partialRatio >= 0.5) return 300; // 50%+ partial matches
    
    return 0; // No match
}
```

**File:** `plugin/zotero-mcp-bridge/content/handlers.js`

Update `handleSearchCollections()`:

```javascript
async handleSearchCollections(request) {
    try {
        const query = (request.query.q || "").trim();
        if (!query) return MCPUtils.formatError("Missing 'q' query parameter");

        const minScore = parseInt(request.query.minScore || "300"); // Configurable threshold
        const limit = parseInt(request.query.limit || "50");

        // Search across all libraries
        const libraries = Zotero.Libraries.getAll();
        const allCollectionsResult = [];

        for (const lib of libraries) {
            const allCollections = Zotero.Collections.getByLibrary(lib.id);
            for (const col of allCollections) {
                const formatted = this._formatCollection(col);
                const score = MCPUtils.fuzzyMatchScore(query, formatted.name, formatted.fullPath);
                
                if (score >= minScore) {
                    formatted.matchScore = score;
                    allCollectionsResult.push(formatted);
                }
            }
        }

        // Sort by score (highest first)
        allCollectionsResult.sort((a, b) => b.matchScore - a.matchScore);

        // Apply limit
        const result = allCollectionsResult.slice(0, limit);

        Zotero.debug(`MCP: Search for "${query}" found ${result.length} collections (${allCollectionsResult.length} total matches)`);
        
        return MCPUtils.formatSuccess(result);
    } catch (e) {
        Zotero.debug("MCP Error handleSearchCollections: " + e);
        return { statusCode: 500, body: { error: e.toString() } };
    }
}
```

---

## 4. Cache the Hierarchy (Speed & Reliability)

### Problem
- Fetching full collection tree every time causes `[Errno 54]` connection resets
- Slow performance for repeated operations
- Unnecessary load on Zotero

### Solution
Implement in-memory caching with refresh capability.

### Implementation Details

**File:** `plugin/zotero-mcp-bridge/content/cache.js` (NEW FILE)

```javascript
/* global Zotero */

var MCPCache = class {
    constructor() {
        this.collections = null;
        this.lastRefresh = null;
        this.ttl = 300000; // 5 minutes in milliseconds
    }

    isValid() {
        if (!this.collections || !this.lastRefresh) return false;
        const age = Date.now() - this.lastRefresh;
        return age < this.ttl;
    }

    async refresh() {
        try {
            Zotero.debug("MCP Cache: Refreshing collection hierarchy...");
            const startTime = Date.now();
            
            const libraries = Zotero.Libraries.getAll();
            const allCollections = [];

            for (const lib of libraries) {
                const collections = Zotero.Collections.getByLibrary(lib.id);
                for (const col of collections) {
                    allCollections.push({
                        key: col.key,
                        name: col.name,
                        parentKey: col.parentKey || null,
                        libraryID: col.libraryID,
                        childCount: col.getChildCollections().length,
                        dateAdded: col.dateAdded,
                        dateModified: col.dateModified
                    });
                }
            }

            this.collections = allCollections;
            this.lastRefresh = Date.now();
            
            const duration = Date.now() - startTime;
            Zotero.debug(`MCP Cache: Refreshed ${allCollections.length} collections in ${duration}ms`);
            
            return true;
        } catch (e) {
            Zotero.debug("MCP Cache: Error refreshing: " + e);
            return false;
        }
    }

    async get() {
        if (!this.isValid()) {
            await this.refresh();
        }
        return this.collections;
    }

    invalidate() {
        Zotero.debug("MCP Cache: Invalidated");
        this.collections = null;
        this.lastRefresh = null;
    }

    search(query) {
        if (!this.collections) return [];
        
        const queryLower = query.toLowerCase();
        return this.collections.filter(col => {
            return col.name.toLowerCase().includes(queryLower);
        });
    }

    findByKey(key, libraryID = null) {
        if (!this.collections) return null;
        
        return this.collections.find(col => {
            if (libraryID !== null) {
                return col.key === key && col.libraryID === libraryID;
            }
            return col.key === key;
        });
    }

    getChildren(parentKey, libraryID = null) {
        if (!this.collections) return [];
        
        return this.collections.filter(col => {
            if (libraryID !== null) {
                return col.parentKey === parentKey && col.libraryID === libraryID;
            }
            return col.parentKey === parentKey;
        });
    }
};
```

**File:** `plugin/zotero-mcp-bridge/content/handlers.js`

Add cache initialization:

```javascript
constructor(authManager) {
    this.authManager = authManager;
    this.cache = new MCPCache();
}
```

Add cache refresh endpoint:

```javascript
async handleRefreshCache(request) {
    try {
        const success = await this.cache.refresh();
        if (success) {
            return MCPUtils.formatSuccess({
                message: "Cache refreshed successfully",
                collectionCount: this.cache.collections.length,
                timestamp: this.cache.lastRefresh
            });
        } else {
            return { statusCode: 500, body: { error: "Cache refresh failed" } };
        }
    } catch (e) {
        return { statusCode: 500, body: { error: e.toString() } };
    }
}
```

Add route:
```javascript
if (method === "POST" && path === "/cache/refresh") {
    return await this.handleRefreshCache(request);
}
```

Update collection handlers to use cache:

```javascript
async handleGetCollections(request) {
    try {
        // Use cache for fast access
        const allCollections = await this.cache.get();
        
        // ... rest of filtering and pagination logic using cached data
    } catch (e) {
        // Fallback to direct Zotero API if cache fails
        Zotero.debug("MCP: Cache failed, using direct API: " + e);
        // ... original implementation
    }
}
```

#### MCP Server Changes

**File:** `src/zotero2ai/server.py`

Add cache refresh tool:

```python
@self.mcp.tool()
async def refresh_cache() -> str:
    """
    Refresh the collection hierarchy cache.
    
    Call this after adding/removing/moving collections to ensure
    the cache is up-to-date. The cache auto-refreshes every 5 minutes.
    
    Returns:
        Status message with collection count and timestamp
    """
    response = await self._make_request("POST", "/cache/refresh")
    return json.dumps(response, indent=2)
```

---

## 5. Standardize Error Handling (Graceful Degradation)

### Problem
- 500 Internal Server Error on tags and recent papers stops workflow completely
- `item.getTags()` fails in Zotero 7 updates
- No graceful fallback mechanism

### Solution
Implement try-catch blocks with graceful degradation and warning messages.

### Implementation Details

**File:** `plugin/zotero-mcp-bridge/content/handlers.js`

Create error-safe wrapper functions:

```javascript
_safeGetTags(item) {
    try {
        if (typeof item.getTags === 'function') {
            const tags = item.getTags();
            return Array.isArray(tags) ? tags.map(t => t.tag || t) : [];
        }
        return [];
    } catch (e) {
        Zotero.debug(`MCP: Error getting tags for item ${item.key}: ${e}`);
        return [];
    }
}

_safeGetField(item, fieldName, defaultValue = '') {
    try {
        if (typeof item.getField === 'function') {
            return item.getField(fieldName) || defaultValue;
        }
        return defaultValue;
    } catch (e) {
        Zotero.debug(`MCP: Error getting field '${fieldName}' for item ${item.key}: ${e}`);
        return defaultValue;
    }
}

_safeGetCreators(item) {
    try {
        if (typeof item.getCreators === 'function') {
            const creators = item.getCreators();
            return creators.map(c => 
                c.firstName ? `${c.lastName}, ${c.firstName}` : c.lastName
            );
        }
        return [];
    } catch (e) {
        Zotero.debug(`MCP: Error getting creators for item ${item.key}: ${e}`);
        return [];
    }
}

async _safeGetAttachments(item) {
    try {
        if (typeof item.getAttachments !== 'function') {
            return [];
        }

        const attachmentIDs = item.getAttachments();
        const attachments = [];

        for (const attachmentID of attachmentIDs) {
            try {
                const attachment = await Zotero.Items.getAsync(attachmentID);
                if (attachment && attachment.isAttachment()) {
                    const filePath = await attachment.getFilePathAsync();
                    const attachmentUrl = this._safeGetField(attachment, 'url');

                    if (filePath || attachmentUrl) {
                        attachments.push({
                            key: attachment.key,
                            title: this._safeGetField(attachment, 'title', 'Untitled'),
                            contentType: attachment.attachmentContentType || 'link',
                            path: filePath || '',
                            url: attachmentUrl || ''
                        });
                    }
                }
            } catch (e) {
                Zotero.debug(`MCP: Error getting attachment ${attachmentID}: ${e}`);
                // Continue with other attachments
            }
        }

        return attachments;
    } catch (e) {
        Zotero.debug(`MCP: Error getting attachments for item ${item.key}: ${e}`);
        return [];
    }
}
```

Update `formatItems()` to use safe wrappers:

```javascript
async formatItems(itemIDsOrItems) {
    if (!itemIDsOrItems || itemIDsOrItems.length === 0) {
        return MCPUtils.formatSuccess([]);
    }

    let items;
    if (typeof itemIDsOrItems[0] === 'object') {
        items = itemIDsOrItems;
    } else {
        const validIDs = itemIDsOrItems.filter(id => id && !isNaN(id));
        if (validIDs.length === 0) return MCPUtils.formatSuccess([]);
        
        try {
            items = await Zotero.Items.getAsync(validIDs);
        } catch (e) {
            Zotero.debug(`MCP: Error loading items: ${e}`);
            return MCPUtils.formatSuccess([]);
        }
    }

    const result = [];
    const errors = [];

    for (const item of items) {
        if (!item) continue;

        try {
            const creators = this._safeGetCreators(item);
            const tags = this._safeGetTags(item);
            const attachments = await this._safeGetAttachments(item);
            const related = await this._getRelatedKeys(item);

            result.push({
                key: item.key,
                itemType: Zotero.ItemTypes.getName(item.itemTypeID),
                title: this._safeGetField(item, 'title'),
                url: this._safeGetField(item, 'url'),
                creators: creators,
                date: this._safeGetField(item, 'date'),
                tags: tags,
                collections: item.getCollections ? item.getCollections() : [],
                related: related,
                attachments: attachments
            });
        } catch (e) {
            Zotero.debug(`MCP: Error formatting item ${item.key}: ${e}`);
            errors.push({
                key: item.key,
                error: e.toString()
            });
            
            // Add partial item data
            result.push({
                key: item.key,
                itemType: 'unknown',
                title: '[Error loading item]',
                error: e.toString()
            });
        }
    }

    // Include error summary if any errors occurred
    const response = {
        statusCode: 200,
        body: {
            success: true,
            data: result
        }
    };

    if (errors.length > 0) {
        response.body.warnings = {
            message: `${errors.length} items had errors during formatting`,
            errors: errors
        };
    }

    return response;
}
```

Update `handleGetTags()` with better error handling:

```javascript
async handleGetTags(request) {
    try {
        const libraryIDParam = request.query.libraryID;
        const libraries = libraryIDParam 
            ? [{ id: parseInt(libraryIDParam) }] 
            : Zotero.Libraries.getAll();
        
        let allTags = new Set();
        const errors = [];

        for (const lib of libraries) {
            try {
                const tags = await Zotero.Tags.search("", lib.id);
                if (tags && Array.isArray(tags)) {
                    for (const t of tags) {
                        try {
                            const tagName = (typeof t === 'string') 
                                ? t 
                                : (t.tag || t.name || 
                                   (typeof t.getName === 'function' ? t.getName() : String(t)));
                            allTags.add(tagName);
                        } catch (e) {
                            Zotero.debug(`MCP: Error processing tag: ${e}`);
                        }
                    }
                }
            } catch (e) {
                Zotero.debug(`MCP: Error getting tags for library ${lib.id}: ${e}`);
                errors.push({
                    libraryID: lib.id,
                    error: e.toString()
                });
            }
        }

        const response = MCPUtils.formatSuccess(Array.from(allTags).sort());
        
        if (errors.length > 0) {
            response.body.warnings = {
                message: `${errors.length} libraries had errors`,
                errors: errors
            };
        }

        return response;
    } catch (e) {
        Zotero.debug("MCP Error handleGetTags: " + e);
        // Return empty array instead of 500 error
        return MCPUtils.formatSuccess([]);
    }
}
```

---

## Implementation Priority

1. **Phase 1 - Critical Fixes (Week 1)**
   - [ ] Fix pagination in `handleGetCollections()` (Issue #2)
   - [ ] Implement graceful error handling (Issue #5)
   - [ ] Test with large collections

2. **Phase 2 - Navigation Improvements (Week 2)**
   - [ ] Implement `list_collection_children` tool (Issue #1)
   - [ ] Add fuzzy search improvements (Issue #3)
   - [ ] Update MCP server tools

3. **Phase 3 - Performance Optimization (Week 3)**
   - [ ] Implement caching system (Issue #4)
   - [ ] Add cache refresh tool
   - [ ] Performance testing

## Testing Plan

### Unit Tests
- Test pagination with various limits and offsets
- Test fuzzy matching with different query patterns
- Test cache refresh and invalidation
- Test error handling with malformed data

### Integration Tests
- Test with real Zotero library (1000+ collections)
- Test connection stability over extended sessions
- Test agent workflows end-to-end

### Performance Tests
- Measure response times before/after caching
- Measure token usage reduction with `list_children`
- Test connection reset frequency

## Success Metrics

- **Token Usage**: Reduce by 70%+ for navigation tasks
- **Reliability**: Zero connection resets in 100 consecutive operations
- **Completeness**: 100% of collections visible (no truncation)
- **Search Accuracy**: 95%+ success rate for fuzzy searches
- **Performance**: <100ms response time for cached operations

## Rollback Plan

Each phase can be rolled back independently:
- Keep old handlers as `_legacy` methods
- Feature flags for new vs old behavior
- Gradual rollout with A/B testing

## Documentation Updates

- [ ] Update API documentation with new endpoints
- [ ] Add caching behavior to README
- [ ] Document pagination parameters
- [ ] Add troubleshooting guide for common errors

---

## Notes

- All changes maintain backward compatibility
- Zotero 6 and 7 both supported
- No breaking changes to existing MCP tools
- Incremental deployment possible
