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
            if (method === "GET" && path === "/collections/search") return await this.handleSearchCollections(request);
            if (method === "GET" && path.match(/^\/collections\/[A-Z0-9]+\/items$/)) return await this.handleGetCollectionItems(request);
            if (method === "GET" && path.startsWith("/items/search")) return await this.handleSearchItems(request);
            if (method === "GET" && path === "/items/recent") return await this.handleRecentItems(request);
            if (method === "GET" && path === "/notes") return await this.handleGetNotes(request);
            if (method === "GET" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleGetNote(request);
            if (method === "POST" && path === "/notes") return await this.handleCreateNote(request);
            if (method === "PUT" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleUpdateNote(request);
            if (method === "GET" && path === "/tags") return await this.handleGetTags(request);
            if (method === "POST" && path === "/tags/rename") return await this.handleRenameTag(request);

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

    // Helper method to recursively collect all collections including subcollections
    _getAllCollectionsRecursive(collection, result) {
        // Add current collection
        result.push(this._formatCollection(collection));

        // Recursively add child collections
        const children = collection.getChildCollections();
        for (const child of children) {
            this._getAllCollectionsRecursive(child, result);
        }
    }


    async handleGetCollections(request) {
        try {
            const libraryIDParam = request.query.libraryID;
            const parentKey = request.query.parentKey;

            let result = [];

            if (parentKey === 'root') {
                // Return only top-level (root) collections from specified or all libraries
                if (libraryIDParam) {
                    const allCollections = Zotero.Collections.getByLibrary(parseInt(libraryIDParam));
                    for (const collection of allCollections) {
                        if (!collection.parentKey) {
                            result.push(this._formatCollection(collection));
                        }
                    }
                } else {
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        const allCollections = Zotero.Collections.getByLibrary(lib.id);
                        for (const collection of allCollections) {
                            if (!collection.parentKey) {
                                result.push(this._formatCollection(collection));
                            }
                        }
                    }
                }
            } else if (parentKey) {
                // Return direct children of specific collection
                let parent = null;
                if (libraryIDParam) {
                    parent = Zotero.Collections.getByLibraryAndKey(parseInt(libraryIDParam), parentKey);
                } else {
                    // Search across all libraries for the parentKey
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        parent = Zotero.Collections.getByLibraryAndKey(lib.id, parentKey);
                        if (parent) break;
                    }
                }

                if (!parent) return MCPUtils.formatError(`Collection '${parentKey}' not found`);

                const children = parent.getChildCollections();
                Zotero.debug(`MCP: Found ${children.length} children for parent ${parentKey}`);

                for (const child of children) {
                    result.push(this._formatCollection(child));
                }
            } else {
                // List all collections across all libraries or just one
                // FIX: Zotero.Collections.getByLibrary returns ALL collections flatly. 
                // We should NOT recurse here, otherwise we create duplicates (N*Depth).
                if (libraryIDParam) {
                    const allCollections = Zotero.Collections.getByLibrary(parseInt(libraryIDParam));
                    Zotero.debug(`MCP: Found ${allCollections.length} collections in library ${libraryIDParam}`);
                    for (const col of allCollections) {
                        result.push(this._formatCollection(col));
                    }
                } else {
                    const libraries = Zotero.Libraries.getAll();
                    for (const lib of libraries) {
                        const allCollections = Zotero.Collections.getByLibrary(lib.id);
                        Zotero.debug(`MCP: Found ${allCollections.length} collections in library ${lib.id}`);
                        for (const col of allCollections) {
                            result.push(this._formatCollection(col));
                        }
                    }
                }
            }

            Zotero.debug(`MCP: Returning ${result.length} collections`);
            return MCPUtils.formatSuccess(result);
        } catch (e) {
            Zotero.debug("MCP Error handleGetCollections: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleSearchCollections(request) {
        try {
            const query = (request.query.q || "").toLowerCase();
            if (!query) return MCPUtils.formatError("Missing 'q' query parameter");

            // Search across all libraries for maximum helpfulness
            const libraries = Zotero.Libraries.getAll();
            const allCollectionsResult = [];

            // Collect all collections from all libraries
            // FIX: No recursion needed, getByLibrary is already flat
            for (const lib of libraries) {
                const allCollections = Zotero.Collections.getByLibrary(lib.id);
                for (const col of allCollections) {
                    allCollectionsResult.push(this._formatCollection(col));
                }
            }

            // Filter by query
            const result = allCollectionsResult.filter(col => {
                const name = col.name.toLowerCase();
                const fullPath = col.fullPath.toLowerCase();
                // Match against both name and full path for better results
                return name.includes(query) || fullPath.includes(query);
            });

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
            const limit = parseInt(request.query.limit || "10");
            const libraryIDParam = request.query.libraryID;

            if (!searchQuery && !tag) return MCPUtils.formatError("Missing 'q' or 'tag' query parameter");

            const libraries = libraryIDParam ? [{ id: parseInt(libraryIDParam) }] : Zotero.Libraries.getAll();
            let allItemIDs = [];

            for (const lib of libraries) {
                const s = new Zotero.Search();
                s.libraryID = lib.id;

                if (searchQuery) {
                    s.addCondition('title', 'contains', searchQuery);
                }

                if (tag) {
                    s.addCondition('tag', 'is', tag);
                }

                s.addCondition('itemType', 'isNot', 'attachment');
                s.addCondition('itemType', 'isNot', 'note');

                // FIX: Zotero 7 search() ist ASYNC -> await!
                const itemIDs = await s.search();
                allItemIDs = allItemIDs.concat(itemIDs);
                if (allItemIDs.length >= limit) break;
            }

            const limitedIDs = allItemIDs.slice(0, limit);
            // Items laden (getAsync ist besser in Zotero 7, aber get() geht oft noch)
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
                tags: note.getTags().map(t => t.tag),
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
        const ids = item.getRelatedItemIDs ? item.getRelatedItemIDs() : (item.getRelatedItems ? item.getRelatedItems() : []);
        if (!ids || ids.length === 0) return [];
        const items = await Zotero.Items.getAsync(ids);
        return items.filter(i => i).map(i => i.key);
    }

    async formatItems(itemIDsOrItems) {
        if (!itemIDsOrItems || itemIDsOrItems.length === 0) return MCPUtils.formatSuccess([]);

        let items;
        if (typeof itemIDsOrItems[0] === 'object') {
            items = itemIDsOrItems;
        } else {
            const validIDs = itemIDsOrItems.filter(id => id && !isNaN(id));
            if (validIDs.length === 0) return MCPUtils.formatSuccess([]);
            items = await Zotero.Items.getAsync(validIDs);
        }

        const result = [];
        for (const item of items) {
            if (!item) continue;
            const creators = item.getCreators().map(c => c.firstName ? `${c.lastName}, ${c.firstName}` : c.lastName);

            // Get attachment file paths and URLs
            const attachments = [];
            const attachmentIDs = item.getAttachments();
            for (const attachmentID of attachmentIDs) {
                try {
                    const attachment = await Zotero.Items.getAsync(attachmentID);
                    if (attachment && attachment.isAttachment()) {
                        const filePath = await attachment.getFilePathAsync();
                        const attachmentUrl = attachment.getField('url');

                        if (filePath || attachmentUrl) {
                            attachments.push({
                                key: attachment.key,
                                title: attachment.getField('title') || 'Untitled',
                                contentType: attachment.attachmentContentType || 'link',
                                path: filePath || '',
                                url: attachmentUrl || ''
                            });
                        }
                    }
                } catch (e) {
                    Zotero.debug(`Error getting attachment ${attachmentID}: ${e}`);
                }
            }

            result.push({
                key: item.key,
                itemType: Zotero.ItemTypes.getName(item.itemTypeID),
                title: item.getField('title') || '',
                url: item.getField('url') || '',
                creators: creators,
                date: item.getField('date') || '',
                tags: item.getTags().map(t => t.tag),
                collections: item.getCollections(),
                related: await this._getRelatedKeys(item),
                attachments: attachments
            });
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
            notes = await Zotero.Items.getAsync(validIDs);
        }

        const result = [];
        for (const note of notes) {
            if (!note) continue;
            result.push({
                key: note.key,
                note: note.getNote(),
                tags: note.getTags().map(t => t.tag),
                parentItemKey: note.parentItemKey || null,
                collections: note.getCollections(),
                related: await this._getRelatedKeys(note),
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            });
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
};