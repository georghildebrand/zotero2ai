# GitHub Issues Template

Use these templates to create issues for tracking each improvement.

---

## Issue #1: Add `list_collection_children` Tool

**Title**: Add `list_collection_children` tool for efficient collection navigation

**Labels**: `enhancement`, `agent-experience`, `performance`

**Description**:

### Problem
Currently, agents must choose between:
- Listing everything (huge, slow, gets truncated)
- Fuzzy searching (hit-or-miss, unreliable)

This makes navigation inefficient and unreliable.

### Solution
Implement a new tool `list_collection_children(parent_key)` that:
- Returns only immediate sub-collections and items
- Mimics Unix `ls` command behavior
- Drastically reduces token usage

### Implementation
- [ ] Add `handleGetCollectionChildren()` in `handlers.js`
- [ ] Add route `GET /collections/{key}/children`
- [ ] Add `list_collection_children()` tool in `server.py`
- [ ] Add tests
- [ ] Update documentation

### Success Criteria
- 70% reduction in token usage for navigation tasks
- No truncation of results
- Response time <200ms

**See**: `docs/plans/agentic-workflow-improvements.md` Section 1

---

## Issue #2: Fix Pagination & Limits

**Title**: Fix pagination to prevent missing collections in large folders

**Labels**: `bug`, `critical`, `data-completeness`

**Description**:

### Problem
Large collections (like "00 Projects" with 20+ subfolders) are truncated because:
- Zotero API limits responses to 50-100 items
- Bridge grabs "Page 1" and stops
- No pagination logic exists

### Solution
Implement proper pagination with:
- Configurable `limit` and `start` parameters
- Consistent sorting (`sort=title`)
- Pagination metadata in responses

### Implementation
- [ ] Update `handleGetCollections()` with pagination
- [ ] Add `pagination` object to responses
- [ ] Update `list_collections()` in `server.py`
- [ ] Add tests for large collections
- [ ] Update documentation

### Success Criteria
- 100% of collections visible (no truncation)
- Pagination metadata accurate
- Consistent ordering

**See**: `docs/plans/agentic-workflow-improvements.md` Section 2

---

## Issue #3: Improve Search Scoring

**Title**: Implement token-based fuzzy matching for collection search

**Labels**: `enhancement`, `search`, `agent-experience`

**Description**:

### Problem
- Search for "2023-11 Blog Posts" fails
- Search for "2023-11" works
- No token-based matching or path inclusion

### Solution
Implement intelligent fuzzy matching:
- Token-based matching (split on spaces, dashes, slashes)
- Path inclusion in scoring
- Configurable minimum score threshold

### Implementation
- [ ] Add `fuzzyMatchScore()` in `utils.js`
- [ ] Update `handleSearchCollections()` to use scoring
- [ ] Add `matchScore` to search results
- [ ] Add `minScore` parameter
- [ ] Add tests for various query patterns
- [ ] Update documentation

### Success Criteria
- 95%+ search accuracy
- "2023-11 Blog Posts" query works
- Results sorted by relevance

**See**: `docs/plans/agentic-workflow-improvements.md` Section 3

---

## Issue #4: Implement Collection Hierarchy Caching

**Title**: Add in-memory caching to prevent connection resets and improve performance

**Labels**: `enhancement`, `performance`, `reliability`

**Description**:

### Problem
- Fetching full collection tree every time causes `[Errno 54]` connection resets
- Slow performance for repeated operations
- Unnecessary load on Zotero

### Solution
Implement in-memory caching:
- Cache collection hierarchy with 5-minute TTL
- Manual refresh endpoint
- Automatic refresh on cache miss
- Cache-aware handlers

### Implementation
- [ ] Create `cache.js` with `MCPCache` class
- [ ] Add `handleRefreshCache()` in `handlers.js`
- [ ] Update collection handlers to use cache
- [ ] Add `refresh_cache()` tool in `server.py`
- [ ] Add cache invalidation on collection changes
- [ ] Add tests
- [ ] Update documentation

### Success Criteria
- <100ms response time for cached operations
- Zero connection resets in 100 consecutive operations
- Cache hit rate >90%

**See**: `docs/plans/agentic-workflow-improvements.md` Section 4

---

## Issue #5: Standardize Error Handling

**Title**: Implement graceful degradation for API errors

**Labels**: `bug`, `reliability`, `error-handling`

**Description**:

### Problem
- 500 Internal Server Error stops workflows completely
- `item.getTags()` fails in Zotero 7 updates
- No graceful fallback mechanism

### Solution
Implement error-safe wrappers:
- Try-catch blocks around all Zotero API calls
- Return partial data with warnings instead of 500 errors
- Detailed error logging for debugging

### Implementation
- [ ] Add `_safeGetTags()` wrapper
- [ ] Add `_safeGetField()` wrapper
- [ ] Add `_safeGetCreators()` wrapper
- [ ] Add `_safeGetAttachments()` wrapper
- [ ] Update `formatItems()` to use wrappers
- [ ] Update `handleGetTags()` with better error handling
- [ ] Add `warnings` field to responses
- [ ] Add tests for error scenarios
- [ ] Update documentation

### Success Criteria
- No 500 errors for common failures
- Workflows continue with partial data
- Clear warning messages for debugging

**See**: `docs/plans/agentic-workflow-improvements.md` Section 5

---

## Milestone: Agentic Workflow Improvements

**Title**: Improve Zotero Bridge for Agentic Workflows

**Description**:
This milestone tracks the implementation of five critical improvements to make the Zotero MCP Bridge more efficient, reliable, and agent-friendly.

**Issues**:
- #1: Add `list_collection_children` tool
- #2: Fix pagination & limits
- #3: Improve search scoring
- #4: Implement caching
- #5: Standardize error handling

**Target Date**: 3 weeks from start

**Success Metrics**:
- Token usage: -70%
- Connection resets: 0 per 100 ops
- Collection completeness: 100%
- Search accuracy: 95%
- Cached response time: <100ms

---

## Creating the Issues

To create these issues on GitHub:

```bash
# Navigate to repository
cd /Users/georg.hildebrand/workspace/github.com/zotero2ai

# Create issues using GitHub CLI (if installed)
gh issue create --title "Add list_collection_children tool" \
  --label "enhancement,agent-experience,performance" \
  --body-file <(sed -n '/^## Issue #1/,/^---$/p' docs/plans/GITHUB_ISSUES.md)

# Repeat for issues #2-5
```

Or manually create them through the GitHub web interface.
