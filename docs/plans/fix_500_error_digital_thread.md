# Plan - Fix 500 Error in Zotero MCP Bridge

## Problem
The endpoint `/collections/{key}/items` returns a 500 error because of a `TypeError: item.getRelatedItems is not a function`. This is due to Zotero 7 API changes where `getRelatedItems()` was replaced by `getRelatedItemIDs()`.

## Proposed Changes

### 1. Fix `handleGetCollectionItems` in `plugin/zotero-mcp-bridge/content/handlers.js`
- Change `Zotero.Collections.getByLibraryAndKeyAsync` to `Zotero.Collections.getByLibraryAndKey`.
- `getByLibraryAndKey` is the standard synchronous method which works in both Zotero 6 and 7.

### 2. Fix `_getRelatedKeys` in `plugin/zotero-mcp-bridge/content/handlers.js`
- Update the method to use `getRelatedItemIDs()` if available (Zotero 7), falling back to `getRelatedItems()` (Zotero 6) or an empty array.
- Add a filter to the mapping of keys to prevent errors if `getAsync` returns null for any IDs.

### 3. Rebuild and Verify
- Run `plugin/build.sh` to generate the new `.xpi`.
- Ask the user to re-install and restart Zotero.
- Verify with `curl`.

## Verification Plan
- Run `curl -v -H "Authorization: Bearer ..." "http://127.0.0.1:23120/collections/ZRRPAK7K/items?limit=1"`
- Expected: 200 OK with item data.
