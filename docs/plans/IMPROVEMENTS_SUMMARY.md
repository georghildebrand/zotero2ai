# Zotero Bridge Improvements - Quick Reference

## Overview

Five critical improvements to make the Zotero MCP Bridge more efficient and agent-friendly.

## The Five Improvements

### 1. 🗂️ Add `list_collection_children` Tool
**The "ls" Command for Zotero**

- **Problem**: Agents must choose between listing everything (slow, truncated) or fuzzy search (unreliable)
- **Solution**: New tool that returns only immediate children of a collection
- **Benefit**: 70% reduction in token usage, no truncation, reliable navigation
- **Files**: `handlers.js`, `server.py`

### 2. 📄 Fix Pagination & Limits
**The "Missing Folder" Bug**

- **Problem**: Large collections truncated at 50-100 items, missing subfolders
- **Solution**: Proper pagination with configurable limits and automatic page fetching
- **Benefit**: 100% of collections visible, no missing data
- **Files**: `handlers.js`

### 3. 🔍 Improve Search Scoring
**Fuzzy Match Issues**

- **Problem**: Search for "2023-11 Blog Posts" fails, but "2023-11" works
- **Solution**: Token-based matching with path inclusion
- **Benefit**: 95%+ search accuracy, more reliable discovery
- **Files**: `utils.js`, `handlers.js`

### 4. ⚡ Cache the Hierarchy
**Speed & Reliability**

- **Problem**: Fetching full tree every time causes connection resets
- **Solution**: In-memory caching with 5-minute TTL and manual refresh
- **Benefit**: <100ms response time, zero connection resets
- **Files**: `cache.js` (new), `handlers.js`, `server.py`

### 5. 🛡️ Standardize Error Handling
**Graceful Degradation**

- **Problem**: 500 errors stop workflows completely (e.g., `getTags()` failures)
- **Solution**: Try-catch wrappers with fallbacks, return partial data with warnings
- **Benefit**: Workflows continue even with errors, better debugging
- **Files**: `handlers.js`

## Implementation Phases

### ✅ Phase 1 - Critical Fixes (Week 1)
- [ ] Fix pagination (#2)
- [ ] Implement error handling (#5)
- [ ] Test with large collections

### 🔄 Phase 2 - Navigation (Week 2)
- [ ] Add `list_collection_children` (#1)
- [ ] Improve fuzzy search (#3)
- [ ] Update MCP tools

### 🚀 Phase 3 - Performance (Week 3)
- [ ] Implement caching (#4)
- [ ] Add cache refresh tool
- [ ] Performance testing

## Quick Start

To implement these improvements:

1. **Read the detailed plan**: `agentic-workflow-improvements.md`
2. **Start with Phase 1**: Critical fixes first
3. **Test incrementally**: Each improvement is independent
4. **Deploy gradually**: No breaking changes

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Token Usage Reduction | 70% | - |
| Connection Resets | 0 per 100 ops | - |
| Collection Completeness | 100% | ~60% |
| Search Accuracy | 95% | ~70% |
| Cached Response Time | <100ms | - |

## Files to Modify

```
plugin/zotero-mcp-bridge/content/
├── handlers.js       (All 5 improvements)
├── utils.js          (Improvements #3, #5)
└── cache.js          (NEW - Improvement #4)

src/zotero2ai/
└── server.py         (Improvements #1, #4)
```

## API Changes Summary

### New Endpoints
- `GET /collections/{key}/children` - List immediate children
- `POST /cache/refresh` - Refresh collection cache

### Enhanced Endpoints
- `GET /collections` - Now supports pagination (`limit`, `start`, `sort`)
- `GET /collections/search` - Improved fuzzy matching with scores

### New Response Fields
- `pagination`: `{ total, start, limit, hasMore }`
- `warnings`: `{ message, errors }` (for partial failures)
- `matchScore`: Relevance score for search results

## Backward Compatibility

✅ All changes are backward compatible
✅ Existing tools continue to work
✅ No breaking changes to MCP interface
✅ Zotero 6 and 7 both supported

## Next Steps

1. Review the detailed plan
2. Prioritize which improvements to implement first
3. Create feature branches for each phase
4. Test with your actual Zotero library
5. Deploy incrementally

---

**Full Details**: See `agentic-workflow-improvements.md`
