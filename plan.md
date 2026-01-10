# Plan to list children of "2023-11 Blog Posts"

The collection "2023-11 Blog Posts" was found with key `LQD2FXSQ`.
The MCP tool `get_collection_attachments` is failing with a 500 error, likely due to a bug in the Zotero Bridge plugin (specifically `TypeError: item.getRelatedItems is not a function` in Zotero 7).

## Steps:
1. Fix the `_getRelatedKeys` method in `plugin/zotero-mcp-bridge/content/handlers.js` to be compatible with Zotero 7.
2. Verify if other methods in `handlers.js` need Zotero 7 async/await updates.
3. Once the bridge is stable, use `mcp_zotero2ai_get_collection_attachments` to list the children.
4. List the notes found in the collection (already found 2: `WA3YV4UP` and `L2ZMJFU3`).

## Details for Step 1:
In Zotero 7, `getRelatedItems` might have changed. Use a more robust check or use the new API if available.
The error `item.getRelatedItems is not a function` suggests that the check `item.getRelatedItems ? item.getRelatedItems() : []` might be failing if `item` is not what we expect or if the property exists but isn't a function (unlikely) or if it was removed.
Actually, in Zotero 7, related items are handled via `Zotero.Relations`.

I will update `_getRelatedKeys` to gracefully handle missing methods.
