/* global Zotero, MCPUtils */

var RequestHandlers = class {
    constructor(authManager) {
        this.authManager = authManager;
    }

    // WICHTIG: Hauptmethode ist jetzt async!
    async handle(request) {
        // Auth check
        const authHeader = request.headers['authorization'];
        if (!this.authManager.validateAuth(authHeader)) {
            return {
                statusCode: 401,
                body: { error: "Unauthorized", message: "Missing or invalid Bearer token" }
            };
        }

        const { method, path } = request;

        try {
            if (method === "GET" && path === "/health") return this.handleHealth();
            if (method === "GET" && path === "/collections") return await this.handleGetCollections(request);
            if (method === "GET" && path === "/collections/tree") return await this.handleGetCollectionTree(request);
            if (method === "GET" && path === "/collections/search") return await this.handleSearchCollections(request);
            if (method === "GET" && path.match(/^\/collections\/[A-Z0-9]+\/items$/)) return await this.handleGetCollectionItems(request);
            if (method === "GET" && path.startsWith("/items/search")) return await this.handleSearchItems(request);
            if (method === "GET" && path === "/items/recent") return await this.handleRecentItems(request);
            if (method === "GET" && path.match(/^\/items\/[A-Z0-9]+$/)) return await this.handleGetItem(request);
            if (method === "GET" && path === "/notes") return await this.handleGetNotes(request);
            if (method === "GET" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleGetNote(request);
            if (method === "POST" && path === "/notes") return await this.handleCreateNote(request);
            if (method === "PUT" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleUpdateNote(request);
            if (method === "GET" && path === "/tags") return await this.handleGetTags(request);
            if (method === "POST" && path === "/tags/rename") return await this.handleRenameTag(request);
            if (method === "POST" && path === "/collections") return await this.handleCreateCollection(request);
            if (method === "POST" && path === "/items") return await this.handleCreateItem(request);
            if (method === "PUT" && path.match(/^\/items\/[A-Z0-9]+$/)) return await this.handleUpdateItem(request);
            if (method === "POST" && path.match(/^\/items\/[A-Z0-9]+\/related$/)) return await this.handleAddRelated(request);
            if (method === "GET" && path.match(/^\/items\/[A-Z0-9]+\/content$/)) return await this.handleGetItemContent(request);


            return {
                statusCode: 404,
                body: { error: "Not Found", message: `No handler for ${method} ${path}` }
            };
        } catch (e) {
            Zotero.debug("MCP Handler Error: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    handleHealth() {
        return {
            statusCode: 200,
            body: { status: "ok", version: "0.2.0" }
        };
    }

    // Helper method to format a single collection
    _formatCollection(collection) {
        return {
            key: collection.key,
            name: collection.name,
            parentKey: collection.parentKey || null,
            fullPath: MCPUtils.getCollectionPath(collection),
            libraryID: collection.libraryID,
            childCount: collection.getChildCollections().length
        };
    }

    // SAFE DATA ACCESS HELPERS
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

    // Helper method to robusly get ALL collections (flat list) ensuring we hit deep nodes
    _getAllCollectionsFlat(libraryID) {
        try {
            const allMap = new Map();
            // Start with what Zotero gives us (might be just roots, might be all)
            const initial = Zotero.Collections.getByLibrary(libraryID);

            // Use a stack for iterative traversal to avoid recursion limits
            const stack = [...initial];

            while (stack.length > 0) {
                const col = stack.pop();
                if (!col) continue;

                // Add to map if not present
                if (!allMap.has(col.key)) {
                    allMap.set(col.key, col);

                    // Always check for children to be safe
                    const children = col.getChildCollections();
                    for (const child of children) {
                        stack.push(child);
                    }
                }
            }

            return Array.from(allMap.values());
        } catch (e) {
            Zotero.debug("MCP Error _getAllCollectionsFlat: " + e);
            return [];
        }
    }


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
                    allCollections = this._getAllCollectionsFlat(parseInt(libraryIDParam));
                } else {
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        const collections = this._getAllCollectionsFlat(lib.id);
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

    async handleSearchCollections(request) {
        try {
            const query = (request.query.q || "").trim();
            if (!query) return MCPUtils.formatError("Missing 'q' query parameter");

            const minScore = parseInt(request.query.minScore || "300"); // Raised from 200 to be more selective
            const limit = parseInt(request.query.limit || "50");

            // Search across all libraries
            const libraries = Zotero.Libraries.getAll();
            const allCollectionsResult = [];

            for (const lib of libraries) {
                const allCollections = this._getAllCollectionsFlat(lib.id);
                for (const col of allCollections) {
                    const formatted = this._formatCollection(col);
                    const score = MCPUtils.fuzzyMatchScore(query, formatted.name, formatted.fullPath);

                    // DEBUG: Log all scores for troubleshooting
                    if (score > 0) {
                        Zotero.debug(`MCP Search: "${formatted.name}" (${formatted.fullPath}) scored ${score} for query "${query}"`);
                    }

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

            Zotero.debug(`MCP: Search for "${query}" found ${result.length} collections (${allCollectionsResult.length} total matches, minScore=${minScore})`);

            return MCPUtils.formatSuccess(result);
        } catch (e) {
            Zotero.debug("MCP Error handleSearchCollections: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleGetCollectionItems(request) {
        try {
            // Extract collection key from path: /collections/{key}/items
            const pathParts = request.path.split('/');
            const collectionKey = pathParts[2];

            if (!collectionKey) {
                return MCPUtils.formatError("Missing collection key in path");
            }

            // Get limit parameter (default: 100, max: 500)
            const limit = Math.min(parseInt(request.query.limit || "100"), 500);

            // Search across all libraries
            const libraries = Zotero.Libraries.getAll();
            let collection = null;

            for (const lib of libraries) {
                const col = await Zotero.Collections.getByLibraryAndKeyAsync(lib.id, collectionKey);
                if (col) {
                    collection = col;
                    break;
                }
            }

            if (!collection) {
                return { statusCode: 404, body: { error: "Collection not found" } };
            }

            // Get all items in the collection (non-recursive for now)
            const itemIDs = collection.getChildItems(false, false); // false = no includeDeleted, false = no includeNotes

            // Apply limit
            const limitedItemIDs = itemIDs.slice(0, limit);

            // Format items with attachments
            return await this.formatItems(limitedItemIDs);
        } catch (e) {
            Zotero.debug("MCP Error handleGetCollectionItems: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }


    async handleSearchItems(request) {
        try {
            const searchQuery = request.query.q || "";
            const tag = request.query.tag || "";
            const collectionKey = request.query.collectionKey || "";
            const limit = parseInt(request.query.limit || "10");
            const libraryIDParam = request.query.libraryID;
            const dateFrom = request.query.dateFrom || "";
            const dateTo = request.query.dateTo || "";
            const sortBy = request.query.sortBy || "";  // "dateAdded" for chronological

            if (!searchQuery && !tag && !collectionKey) return MCPUtils.formatError("Missing 'q', 'tag', or 'collectionKey' query parameter");

            const libraries = libraryIDParam ? [{ id: parseInt(libraryIDParam) }] : Zotero.Libraries.getAll();
            let allItemIDs = [];

            for (const lib of libraries) {
                const s = new Zotero.Search();
                s.libraryID = lib.id;

                if (searchQuery) {
                    s.addCondition('title', 'contains', searchQuery);
                }

                // Support multiple tags (comma-separated): "mem:class:unit,mem:state:active"
                if (tag) {
                    const tags = tag.split(',').map(t => t.trim()).filter(t => t.length > 0);
                    for (const singleTag of tags) {
                        s.addCondition('tag', 'is', singleTag);
                    }
                }

                if (collectionKey) {
                    s.addCondition('collection', 'is', collectionKey);
                }

                // Date range filtering
                if (dateFrom) {
                    s.addCondition('dateAdded', 'isAfter', dateFrom);
                }
                if (dateTo) {
                    s.addCondition('dateAdded', 'isBefore', dateTo);
                }

                s.addCondition('itemType', 'isNot', 'attachment');
                s.addCondition('itemType', 'isNot', 'note');

                const itemIDs = await s.search();
                allItemIDs = allItemIDs.concat(itemIDs);
                if (allItemIDs.length >= limit) break;
            }

            // If sortBy is requested, load items for sorting before limiting
            if (sortBy === 'dateAdded' && allItemIDs.length > 0) {
                const items = await Zotero.Items.getAsync(allItemIDs);
                items.sort((a, b) => new Date(b.dateAdded) - new Date(a.dateAdded));
                const limitedItems = items.slice(0, limit);
                return await this.formatItems(limitedItems);
            }

            const limitedIDs = allItemIDs.slice(0, limit);
            return await this.formatItems(limitedIDs);
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleRecentItems(request) {
        try {
            const limit = parseInt(request.query.limit || "5");
            const libraryIDParam = request.query.libraryID;

            const libraries = libraryIDParam ? [{ id: parseInt(libraryIDParam) }] : Zotero.Libraries.getAll();
            let allItems = [];

            for (const lib of libraries) {
                const s = new Zotero.Search();
                s.libraryID = lib.id;
                s.addCondition('itemType', 'isNot', 'attachment');
                s.addCondition('itemType', 'isNot', 'note');

                // Wait for search to complete
                const itemIDs = await s.search();
                if (itemIDs && itemIDs.length > 0) {
                    // Load items for sorting (using Async for Zotero 7)
                    const items = await Zotero.Items.getAsync(itemIDs);
                    allItems = allItems.concat(items);
                }
            }

            // Sort all items by dateAdded descending
            allItems.sort((a, b) => new Date(b.dateAdded) - new Date(a.dateAdded));

            const limitedItems = allItems.slice(0, limit);
            return await this.formatItems(limitedItems);
        } catch (e) {
            Zotero.debug("MCP Error handleRecentItems: " + e);
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleGetNotes(request) {
        try {
            const collectionKey = request.query.collectionKey;
            const parentItemKey = request.query.parentItemKey;
            const libraryIDParam = request.query.libraryID;

            if (collectionKey) {
                let collection = null;
                if (libraryIDParam) {
                    collection = Zotero.Collections.getByLibraryAndKey(parseInt(libraryIDParam), collectionKey);
                } else {
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        collection = Zotero.Collections.getByLibraryAndKey(lib.id, collectionKey);
                        if (collection) break;
                    }
                }

                if (!collection) return MCPUtils.formatError(`Collection not found: ${collectionKey}`);

                const itemIDs = collection.getChildItems(true);

                if (!itemIDs || itemIDs.length === 0) return MCPUtils.formatSuccess([]);

                const items = await Zotero.Items.getAsync(itemIDs);
                const notes = items.filter(item => item && item.isNote());
                return await this.formatNotes(notes);
            } else if (parentItemKey) {
                let parentItem = null;
                if (libraryIDParam) {
                    parentItem = Zotero.Items.getByLibraryAndKey(parseInt(libraryIDParam), parentItemKey);
                } else {
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        parentItem = Zotero.Items.getByLibraryAndKey(lib.id, parentItemKey);
                        if (parentItem) break;
                    }
                }

                if (!parentItem) return MCPUtils.formatError(`Item not found: ${parentItemKey}`);
                const noteIDs = parentItem.getNotes();
                return await this.formatNotes(noteIDs);
            } else {
                return MCPUtils.formatError("Must provide collectionKey or parentItemKey");
            }
        } catch (e) {
            Zotero.debug("MCP Error handleGetNotes: " + e);
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleGetNote(request) {
        try {
            const key = request.path.split('/')[2];
            const libraryIDParam = request.query.libraryID;

            let note = null;
            if (libraryIDParam) {
                note = Zotero.Items.getByLibraryAndKey(parseInt(libraryIDParam), key);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    note = Zotero.Items.getByLibraryAndKey(lib.id, key);
                    if (note) break;
                }
            }

            if (!note) return { statusCode: 404, body: { error: "Not Found", message: "Note not found" } };
            if (!note.isNote()) return MCPUtils.formatError(`Item ${key} is not a note`);

            return MCPUtils.formatSuccess({
                key: note.key,
                note: note.getNote(),
                tags: this._safeGetTags(note),
                parentItemKey: note.parentItemKey || null,
                collections: note.getCollections(),
                related: await this._getRelatedKeys(note),
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            });
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleCreateNote(request) {
        try {
            const body = request.body;
            if (!body || !body.note) return MCPUtils.formatError("Missing required field: note");

            const note = new Zotero.Item('note');
            note.libraryID = body.libraryID ? parseInt(body.libraryID) : Zotero.Libraries.userLibraryID;
            note.setNote(body.note);

            if (body.parentItemKey) {
                let parent = null;
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    parent = Zotero.Items.getByLibraryAndKey(lib.id, body.parentItemKey);
                    if (parent) break;
                }

                if (!parent) return MCPUtils.formatError("Parent item not found");
                note.parentItemID = parent.id;
            }

            if (body.tags && Array.isArray(body.tags)) {
                note.setTags(body.tags.map(t => ({ tag: t })));
            }

            // In Zotero 7, saveTx() is async
            await note.saveTx();

            if (body.collections && Array.isArray(body.collections)) {
                note.setCollections(body.collections);
                await note.saveTx();
            }

            if (body.related && Array.isArray(body.related)) {
                const ids = [];
                for (const key of body.related) {
                    let item = null;
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        item = Zotero.Items.getByLibraryAndKey(lib.id, key);
                        if (item) break;
                    }
                    if (item) ids.push(item.id);
                }
                note.setRelatedItems(ids);
                await note.saveTx();
            }

            return {
                statusCode: 201,
                body: { success: true, data: { key: note.key } }
            };
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleUpdateNote(request) {
        try {
            const key = request.path.split('/')[2];
            const libraryIDParam = request.query.libraryID;

            let note = null;
            if (libraryIDParam) {
                note = Zotero.Items.getByLibraryAndKey(parseInt(libraryIDParam), key);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    note = Zotero.Items.getByLibraryAndKey(lib.id, key);
                    if (note) break;
                }
            }

            if (!note) return { statusCode: 404, body: { error: "Not Found" } };
            if (!note.isNote()) return MCPUtils.formatError("Item is not a note");

            const body = request.body;
            if (body.note !== undefined) note.setNote(body.note);
            if (body.tags !== undefined) note.setTags(body.tags.map(t => ({ tag: t })));
            if (body.collections !== undefined) note.setCollections(body.collections);
            if (body.related !== undefined && Array.isArray(body.related)) {
                const ids = [];
                for (const relatedKey of body.related) {
                    let item = null;
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        item = Zotero.Items.getByLibraryAndKey(lib.id, relatedKey);
                        if (item) break;
                    }
                    if (item) ids.push(item.id);
                }
                note.setRelatedItems(ids);
            }

            if (body.parentItemKey !== undefined) {
                if (body.parentItemKey === null) {
                    note.parentItemID = null;
                } else {
                    let parent = null;
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        parent = Zotero.Items.getByLibraryAndKey(lib.id, body.parentItemKey);
                        if (parent) break;
                    }
                    if (parent) note.parentItemID = parent.id;
                }
            }

            await note.saveTx();
            return MCPUtils.formatSuccess({ success: true, key: note.key });
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async _getRelatedKeys(item) {
        try {
            const keys = new Set();

            // Modern Zotero 7 method
            if (typeof item.getRelationsByPredicate === 'function') {
                const relURIs = item.getRelationsByPredicate('dc:relation');
                if (relURIs && Array.isArray(relURIs)) {
                    for (const uri of relURIs) {
                        if (typeof uri === 'string' && uri.startsWith('http://zotero.org/')) {
                            // Extract key directly from URI e.g. http://zotero.org/users/123/items/YACU8TY5
                            const parts = uri.split('/');
                            const key = parts[parts.length - 1];
                            if (key && key.length >= 8) keys.add(key);
                        }
                    }
                }
            } else {
                // Fallback for older versions
                const rawRels = item.getRelatedItemIDs ? item.getRelatedItemIDs() : (item.getRelatedItems ? item.getRelatedItems() : []);
                for (const rel of rawRels) {
                    if (typeof rel === 'number') {
                        const rItem = Zotero.Items.get(rel);
                        if (rItem && rItem.key) keys.add(rItem.key);
                    } else if (typeof rel === 'string' && rel.startsWith('http://zotero.org/')) {
                        const parts = rel.split('/');
                        const key = parts[parts.length - 1];
                        if (key && key.length >= 8) keys.add(key);
                    }
                }
            }
            return Array.from(keys);
        } catch (e) {
            Zotero.debug("MCP: Error in _getRelatedKeys: " + e);
            return [];
        }
    }

    async formatItems(itemIDsOrItems) {
        if (!itemIDsOrItems || itemIDsOrItems.length === 0) return MCPUtils.formatSuccess([]);

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
        for (const item of items) {
            if (!item) continue;

            try {
                // Use safe helpers for all properties
                const creators = this._safeGetCreators(item);
                const tags = this._safeGetTags(item);
                const attachments = await this._safeGetAttachments(item);
                const related = await this._getRelatedKeys(item);
                const title = this._safeGetField(item, 'title', '');
                const url = this._safeGetField(item, 'url', '');
                const date = this._safeGetField(item, 'date', '');
                const itemType = Zotero.ItemTypes.getName(item.itemTypeID);

                const itemData = {
                    key: item.key,
                    itemType: itemType,
                    title: title,
                    url: url,
                    creators: creators,
                    date: date,
                    tags: tags,
                    collections: item.getCollections(), // getCollections usually safe, returns array of keys
                    related: related,
                    attachments: attachments
                };

                // For attachment items, include the file path and content type at the top level
                if (item.isAttachment()) {
                    try {
                        itemData.path = await item.getFilePathAsync();
                        itemData.contentType = item.attachmentContentType || 'unknown';
                    } catch (e) {
                        Zotero.debug(`MCP: Error getting file path for attachment ${item.key}: ${e}`);
                    }
                }

                result.push(itemData);
            } catch (e) {
                Zotero.debug(`MCP: Error formatting item ${item.key}: ${e}`);
                // Graceful degradation: return minimal info with error
                result.push({
                    key: item.key,
                    error: "Failed to format item",
                    details: e.toString()
                });
            }
        }
        return MCPUtils.formatSuccess(result);
    }

    async formatNotes(noteIDsOrItems) {
        if (!noteIDsOrItems || noteIDsOrItems.length === 0) return MCPUtils.formatSuccess([]);

        let notes;
        if (typeof noteIDsOrItems[0] === 'object') {
            notes = noteIDsOrItems;
        } else {
            const validIDs = noteIDsOrItems.filter(id => id && !isNaN(id));
            if (validIDs.length === 0) return MCPUtils.formatSuccess([]);
            try {
                notes = await Zotero.Items.getAsync(validIDs);
            } catch (e) {
                Zotero.debug(`MCP: Error loading notes: ${e}`);
                return MCPUtils.formatSuccess([]);
            }
        }

        const result = [];
        for (const note of notes) {
            if (!note) continue;

            try {
                result.push({
                    key: note.key,
                    note: note.getNote(),
                    tags: this._safeGetTags(note),
                    parentItemKey: note.parentItemKey || null,
                    collections: note.getCollections(),
                    related: await this._getRelatedKeys(note),
                    dateAdded: note.dateAdded,
                    dateModified: note.dateModified
                });
            } catch (e) {
                Zotero.debug(`MCP: Error formatting note ${note.key}: ${e}`);
                result.push({
                    key: note.key,
                    error: "Failed to format note",
                    details: e.toString()
                });
            }
        }
        return MCPUtils.formatSuccess(result);
    }

    async handleGetTags(request) {
        try {
            const libraryIDParam = request.query.libraryID;
            const libraries = libraryIDParam ? [{ id: parseInt(libraryIDParam) }] : Zotero.Libraries.getAll();
            let allTags = new Set();

            for (const lib of libraries) {
                try {
                    const tags = await Zotero.Tags.search("", lib.id);
                    if (tags && Array.isArray(tags)) {
                        for (const t of tags) {
                            // Format tags to be simple strings for serialization
                            const tagName = (typeof t === 'string') ? t : (t.tag || t.name || (typeof t.getName === 'function' ? t.getName() : String(t)));
                            allTags.add(tagName);
                        }
                    }
                } catch (e) {
                    Zotero.debug(`Error getting tags for library ${lib.id}: ${e}`);
                }
            }
            return MCPUtils.formatSuccess(Array.from(allTags).sort());
        } catch (e) {
            Zotero.debug("MCP Error handleGetTags: " + e);
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleRenameTag(request) {
        try {
            const { oldName, newName } = request.body;
            const libraryIDParam = request.body.libraryID;

            if (!oldName || !newName) return MCPUtils.formatError("Missing 'oldName' or 'newName' in body");

            const libraries = libraryIDParam ? [{ id: parseInt(libraryIDParam) }] : Zotero.Libraries.getAll();
            for (const lib of libraries) {
                try {
                    await Zotero.Tags.rename(oldName, newName, lib.id);
                } catch (e) {
                    Zotero.debug(`Error renaming tag in library ${lib.id}: ${e}`);
                    // Continue with other libraries
                }
            }
            return MCPUtils.formatSuccess({ success: true, oldName, newName });
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleGetItemContent(request) {
        try {
            const key = request.path.split('/')[2];
            const libraryIDParam = request.query.libraryID;

            let item = null;
            if (libraryIDParam) {
                item = Zotero.Items.getByLibraryAndKey(parseInt(libraryIDParam), key);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    item = Zotero.Items.getByLibraryAndKey(lib.id, key);
                    if (item) break;
                }
            }

            if (!item) return { statusCode: 404, body: { error: "Item not found" } };

            // If it's a note, return its content directly
            if (item.isNote()) {
                return MCPUtils.formatSuccess({
                    key: item.key,
                    parentKey: item.parentItemKey || null,
                    filename: "Note.html",
                    contentType: "text/html",
                    content: item.getNote()
                });
            }

            let content = "";
            let contentType = "text/plain";
            let filename = "";
            let sourceKey = item.key;

            // If it's a regular item (paper), try to find the best attachment
            if (item.isRegularItem()) {
                const attachmentIDs = item.getAttachments();
                let bestAttachment = null;

                // Prefer PDF, then HTML/Snapshot
                for (const id of attachmentIDs) {
                    try {
                        const att = await Zotero.Items.getAsync(id);
                        if (!att) continue;

                        const isPDF = att.attachmentContentType === 'application/pdf' ||
                            att.attachmentContentType === 'application/x-pdf' ||
                            (att.attachmentFilename && att.attachmentFilename.toLowerCase().endsWith('.pdf'));

                        if (isPDF) {
                            bestAttachment = att;
                            break;
                        } else if ((att.attachmentContentType === 'text/html' || att.attachmentContentType === 'text/plain') && !bestAttachment) {
                            bestAttachment = att;
                        }
                    } catch (e) {
                        Zotero.debug("MCP: Error in attachment loop: " + e);
                    }
                }

                if (bestAttachment) {
                    item = bestAttachment;
                    sourceKey = item.key;
                } else if (attachmentIDs.length > 0) {
                    // Fallback to first attachment if none of the above
                    const firstAtt = await Zotero.Items.getAsync(attachmentIDs[0]);
                    if (firstAtt) {
                        item = firstAtt;
                        sourceKey = item.key;
                    }
                } else {
                    return MCPUtils.formatError("No suitable attachment found for this item");
                }
            }

            // Now processing the attachment item
            filename = item.attachmentFilename || "Unknown";
            contentType = item.attachmentContentType || "application/octet-stream";

            // 1. Try Zotero Fulltext (for PDFs especially)
            try {
                if (Zotero.Fulltext) {
                    let ft = null;
                    if (typeof Zotero.Fulltext.getItemText === 'function') {
                        ft = await Zotero.Fulltext.getItemText(item.id);
                    }

                    if (!ft && typeof Zotero.Fulltext.getText === 'function') {
                        ft = await Zotero.Fulltext.getText(item.id);
                    }

                    if (ft) {
                        if (typeof ft === 'string') {
                            content = ft;
                        } else if (ft.text) {
                            content = ft.text;
                        }
                    }

                    // Fallback 1.2: Check if annotations exist (sometimes Zotero 7 stores extracted text in annotations/notes)
                    if (!content && typeof item.getNotes === 'function') {
                        const noteIDs = item.getNotes();
                        for (const noteID of noteIDs) {
                            const note = await Zotero.Items.getAsync(noteID);
                            if (note && note.isNote()) {
                                const noteMarkdown = note.getNote();
                                if (noteMarkdown && noteMarkdown.length > 50) { // Likely extracted text
                                    content = noteMarkdown;
                                    break;
                                }
                            }
                        }
                    }
                }
            } catch (e) {
                Zotero.debug("MCP: Fulltext lookup failed: " + e);
            }

            // 2. If no fulltext yet, and it's a file we can read
            if (!content && (contentType === 'text/html' || contentType === 'text/plain' ||
                filename.toLowerCase().endsWith(".html") || filename.toLowerCase().endsWith(".txt") ||
                filename.toLowerCase().endsWith(".md"))) {
                const filePath = await item.getFilePathAsync();
                if (filePath) {
                    if (typeof IOUtils !== 'undefined') {
                        content = await IOUtils.readUTF8(filePath);
                    } else if (typeof OS !== 'undefined' && OS.File) {
                        const decoder = new TextDecoder();
                        content = decoder.decode(await OS.File.read(filePath));
                    }
                }
            }

            let isIndexed = false;
            let filePath = "";
            try {
                if (Zotero.Fulltext && typeof Zotero.Fulltext.isIndexed === 'function') {
                    isIndexed = await Zotero.Fulltext.isIndexed(item.id);
                }
                filePath = await item.getFilePathAsync();
            } catch (e) { }

            if (!content) {
                let msg = "Content not available.";
                if (contentType && (contentType.toLowerCase().includes("pdf") || (filename && filename.toLowerCase().endsWith(".pdf")))) {
                    if (!isIndexed) {
                        msg += " This PDF is NOT yet indexed by Zotero. Please right-click the item and select 'Reindex Item'.";
                    } else {
                        msg += " PDF is indexed but extraction returned no text. The PDF might be a scanned image without OCR.";
                    }
                } else {
                    msg += " Item format might be unsupported for direct text extraction.";
                }

                return MCPUtils.formatSuccess({
                    key: sourceKey,
                    error: "Content not available",
                    message: msg,
                    filename: filename,
                    contentType: contentType,
                    path: filePath,
                    indexed: isIndexed,
                    internalID: item.id
                });
            }

            return MCPUtils.formatSuccess({
                key: sourceKey,
                parentKey: item.parentItemKey || null,
                filename: filename,
                contentType: contentType,
                content: content,
                path: filePath,
                indexed: isIndexed
            });

        } catch (e) {
            Zotero.debug("MCP Error handleGetItemContent: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleGetCollectionTree(request) {
        try {
            const libraryIDParam = request.query.libraryID;
            const depth = parseInt(request.query.depth || "99"); // Default to deep

            // Get roots first
            let rootCollections = [];
            if (libraryIDParam) {
                const libID = parseInt(libraryIDParam);
                const allCols = Zotero.Collections.getByLibrary(libID);
                rootCollections = allCols.filter(c => !c.parentKey);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    const allCols = Zotero.Collections.getByLibrary(lib.id);
                    rootCollections = rootCollections.concat(allCols.filter(c => !c.parentKey));
                }
            }

            // Recursive formatter
            const buildTree = (collection, currentDepth) => {
                const node = {
                    key: collection.key,
                    name: collection.name,
                    items: []
                };

                // Add children if depth allows
                if (currentDepth < depth) {
                    const children = collection.getChildCollections();
                    node.children = children.map(c => buildTree(c, currentDepth + 1));

                    // Optimization: Do NOT fetch items for every collection in the tree unless requested?
                    // The user said "return a nested JSON with Sub-Collections and Items".
                    // Fetching items for EVERY collection might be heavy. 
                    // Let's include item counts at least, or maybe lightweight item list.
                    // For now, let's keep it to structure (collections) to be fast, 
                    // OR fetch items if explicitly asked. 
                    // User request: "geschachteltes JSON-Objekt mit Sub-Collections und Items"
                    // Okay, let's try to add items but keep it lightweight (key/title).

                    const items = collection.getChildItems(false); // false = don't include recursive items
                    node.items = items.map(i => ({
                        key: i.key,
                        title: i.getField('title'),
                        type: i.itemType
                    })).filter(i => i.type !== 'note' && i.type !== 'attachment');
                } else {
                    node.hasChildren = collection.getChildCollections().length > 0;
                }

                return node;
            };

            const tree = rootCollections.map(c => buildTree(c, 0));
            return MCPUtils.formatSuccess(tree);

        } catch (e) {
            Zotero.debug("MCP Error handleGetCollectionTree: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleGetItem(request) {
        try {
            const key = request.path.split('/')[2];
            const libraryIDParam = request.query.libraryID;
            let item = null;

            Zotero.debug(`MCP: Requested single item lookup for key: ${key} (libParam=${libraryIDParam})`);

            if (libraryIDParam) {
                item = Zotero.Items.getByLibraryAndKey(parseInt(libraryIDParam), key);
            } else {
                const libraries = Zotero.Libraries.getAll();
                for (const lib of libraries) {
                    item = Zotero.Items.getByLibraryAndKey(lib.id, key);
                    if (item) {
                        Zotero.debug(`MCP: Found item ${key} in library ${lib.id}`);
                        break;
                    }
                }
            }

            if (!item) {
                Zotero.debug(`MCP: Item ${key} NOT FOUND in any library`);
                return { statusCode: 404, body: { error: "Item not found" } };
            }

            const formatted = await this.formatItems([item.id]);
            Zotero.debug(`MCP: Formatted data for ${key}: ${JSON.stringify(formatted).substring(0, 100)}...`);
            return formatted;

        } catch (e) {
            Zotero.debug("MCP Error handleGetItem: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleCreateCollection(request) {
        try {
            const body = request.body;
            if (!body || !body.name) return MCPUtils.formatError("Missing required field: name");

            const collection = new Zotero.Collection();
            collection.name = body.name;
            collection.libraryID = body.libraryID ? parseInt(body.libraryID) : Zotero.Libraries.userLibraryID;

            if (body.parentKey) {
                collection.parentKey = body.parentKey;
            }

            await collection.saveTx();

            return {
                statusCode: 201,
                body: {
                    success: true,
                    data: {
                        key: collection.key,
                        name: collection.name,
                        libraryID: collection.libraryID,
                        fullPath: MCPUtils.getCollectionPath(collection)
                    }
                }
            };
        } catch (e) {
            Zotero.debug("MCP Error handleCreateCollection: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleCreateItem(request) {
        try {
            Zotero.debug("MCP: handleCreateItem called with body: " + JSON.stringify(request.body));
            const body = request.body;
            if (!body || !body.title) return MCPUtils.formatError("Missing required field: title");

            // Standardize on 'report' as default itemType for Phase 1 memory nodes
            const itemType = body.itemType || "report";
            const item = new Zotero.Item(itemType);

            item.libraryID = body.libraryID ? parseInt(body.libraryID) : Zotero.Libraries.userLibraryID;
            item.setField('title', body.title);

            // Set approved fields if present
            if (body.fields && typeof body.fields === 'object') {
                for (const field in body.fields) {
                    try {
                        item.setField(field, body.fields[field]);
                    } catch (e) {
                        Zotero.debug(`MCP: Field ${field} not supported for itemType ${itemType}`);
                    }
                }
            }

            if (body.tags && Array.isArray(body.tags)) {
                item.setTags(body.tags.map(t => ({ tag: t })));
            }

            if (body.collections && Array.isArray(body.collections)) {
                item.setCollections(body.collections);
            }

            await item.saveTx();

            // If note is present, create a child note
            if (body.note) {
                const note = new Zotero.Item('note');
                note.libraryID = item.libraryID;
                note.parentItemID = item.id;
                note.setNote(body.note);
                await note.saveTx();
            }

            return {
                statusCode: 201,
                body: {
                    success: true,
                    data: {
                        key: item.key,
                        title: body.title
                    }
                }
            };
        } catch (e) {
            Zotero.debug("MCP Error handleCreateItem: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleUpdateItem(request) {
        try {
            const pathParts = request.path.split('/');
            const key = pathParts[2];
            const body = request.body;

            Zotero.debug(`MCP: handleUpdateItem for key ${key}`);

            const libraries = Zotero.Libraries.getAll();
            let item = null;
            for (const lib of libraries) {
                item = Zotero.Items.getByLibraryAndKey(lib.id, key);
                if (item) break;
            }

            if (!item) return { statusCode: 404, body: { error: "Item not found" } };

            if (body.title !== undefined) item.setField('title', body.title);
            if (body.tags !== undefined) item.setTags(body.tags.map(t => ({ tag: t })));
            if (body.collections !== undefined) item.setCollections(body.collections);

            await item.saveTx();

            return MCPUtils.formatSuccess({ success: true, key: key });
        } catch (e) {
            Zotero.debug("MCP Error handleUpdateItem: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleAddRelated(request) {
        try {
            const pathParts = request.path.split('/');
            const key = pathParts[2];
            const body = request.body;

            Zotero.debug(`MCP: handleAddRelated for key ${key} with relatedKeys ${JSON.stringify(body?.relatedKeys)}`);

            if (!body || !body.relatedKeys || !Array.isArray(body.relatedKeys)) {
                return MCPUtils.formatError("Missing required field: relatedKeys (array)");
            }

            const libraries = Zotero.Libraries.getAll();
            let sourceItem = null;
            for (const lib of libraries) {
                sourceItem = Zotero.Items.getByLibraryAndKey(lib.id, key);
                if (sourceItem) break;
            }

            if (!sourceItem) {
                Zotero.debug(`MCP Error: Source item ${key} not found.`);
                return { statusCode: 404, body: { error: "Source item not found" } };
            }

            let addedCount = 0;
            for (const relKey of body.relatedKeys) {
                let relItem = null;
                for (const lib of libraries) {
                    relItem = Zotero.Items.getByLibraryAndKey(lib.id, relKey);
                    if (relItem) break;
                }

                if (relItem) {
                    try {
                        const relURI = Zotero.URI.getItemURI(relItem);
                        if (typeof sourceItem.addRelation === 'function') {
                            sourceItem.addRelation('dc:relation', relURI);
                            addedCount++;
                        } else if (typeof sourceItem.addRelatedItem === 'function') {
                            sourceItem.addRelatedItem(relItem);
                            addedCount++;
                        } else if (typeof sourceItem.addRelated === 'function') {
                            sourceItem.addRelated(relURI);
                            addedCount++;
                        }
                    } catch (e) {
                        Zotero.debug(`MCP Warning: Could not link ${key} to ${relKey}: ${e}`);
                    }
                } else {
                    Zotero.debug(`MCP Warning: Related item ${relKey} not found.`);
                }
            }

            await sourceItem.saveTx();

            return MCPUtils.formatSuccess({ success: true, key: key, itemsAdded: addedCount });
        } catch (e) {
            Zotero.debug("MCP Error handleAddRelated: " + e + "\nStack: " + e.stack);
            return { statusCode: 500, body: { error: e.toString(), stack: e.stack } };
        }
    }
};