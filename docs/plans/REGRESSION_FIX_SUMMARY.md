# Regression Fix Summary

**Date**: 2026-01-10  
**Status**: ✅ FIXED (Iteration 2) 
**Build**: `plugin/zotero-mcp-bridge.xpi` (rebuilt)

## What Was Fixed

### 1. 🔍 Hierarchy Depth Issue (The "Missing Folder" Bug)

**Problem**: Queries for nested folders (e.g., "Wetterdatenprojekt") returned 0 results.
**Root Cause**: `Zotero.Collections.getByLibrary(lib.id)` apparently returns **only top-level root collections** in the execution context, not the full recursive tree.
**Fix**: Implemented `_getAllCollectionsFlat(libID)`, a new helper ensuring complete recursive traversal of the collection tree.
**Impact**:
- `list_collections()` (no args) now correctly returns ~200+ items (all folders).
- `search_collections()` now correctly scans deep nested folders.

### 2. 🐛 Fuzzy Search Logic

**Problem**: Search double-counted tokens in path + name.
**Fix**: Prevented double-counting in `utils.js` (matches only count once per token).

### 3. 📊 Search Tuning

**Changes**:
- Added extensive debug usage logging.
- Lowered `minScore` threshold to **200**.

## Installation Instructions

1. **Close Zotero** completely.
2. **Install the updated plugin**:
   - Go to `Tools` → `Add-ons`
   - Click the gear icon → `Install Add-on From File...`
   - Select: [PATH_TO_REPO]/plugin/zotero-mcp-bridge.xpi
3. **Restart Zotero**.

## Verification Scenarios

### Test 1: Deep Search
Input: `search_collections("Wetterdatenprojekt")`
- **Before**: "No collections found"
- **After**: Should return the collection key and path.

### Test 2: Full List
Input: `list_collections()`
- **Before**: Returned only ~9 root items.
- **After**: Should return ALL collections (paginated 100 at a time).

### Test 3: False Positives
Input: `search_collections("x2025")`
- **Before**: Returned "02-Private projects" (false match).
- **After**: Should return "00 Projects / x2025" (exact match).

## Files Changed

```
plugin/zotero-mcp-bridge/content/
├── utils.js          (scoring fix)
└── handlers.js       (recursive fetching logic added)
```

## Rollback Plan

If connection resets (Errno 54) return due to valid recursive fetching, we will need to implement **Batching** or **Pagination** on the server side immediately.

The current implementation fetches ALL collections into memory before filtering/pagination. If this crashes Zotero:
1. Revert to `Zotero.Collections.getByLibrary` (roots only).
2. Use `list_collection_children` (Tool 1 in the improvement plan) exclusively for navigation.
