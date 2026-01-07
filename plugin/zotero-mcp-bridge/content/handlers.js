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
            if (method === "GET" && path === "/collections") return await this.handleGetCollections();
            if (method === "GET" && path.startsWith("/items/search")) return await this.handleSearchItems(request);
            if (method === "GET" && path === "/items/recent") return await this.handleRecentItems(request);
            if (method === "GET" && path === "/notes") return await this.handleGetNotes(request);
            if (method === "GET" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleGetNote(request);
            if (method === "POST" && path === "/notes") return await this.handleCreateNote(request);
            if (method === "PUT" && path.match(/^\/notes\/[A-Z0-9]+$/)) return await this.handleUpdateNote(request);

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

    async handleGetCollections() {
        try {
            const libraryID = Zotero.Libraries.userLibraryID;
            // Zotero 7: getByLibrary ist synchron, aber sicherheitshalber in try/catch
            const collections = Zotero.Collections.getByLibrary(libraryID);

            const result = [];
            for (const collection of collections) {
                result.push({
                    key: collection.key,
                    name: collection.name,
                    parentKey: collection.parentKey || null,
                    fullPath: MCPUtils.getCollectionPath(collection),
                    libraryID: collection.libraryID
                });
            }
            return MCPUtils.formatSuccess(result);
        } catch (e) {
            Zotero.debug("MCP Error handleGetCollections: " + e);
            return { statusCode: 500, body: { error: e.toString() } };
        }
    }

    async handleSearchItems(request) {
        try {
            const searchQuery = request.query.q || "";
            const limit = parseInt(request.query.limit || "10");
            if (!searchQuery) return MCPUtils.formatError("Missing 'q' query parameter");

            const s = new Zotero.Search();
            s.libraryID = Zotero.Libraries.userLibraryID;
            s.addCondition('title', 'contains', searchQuery);
            s.addCondition('itemType', 'isNot', 'attachment');
            s.addCondition('itemType', 'isNot', 'note');

            // FIX: Zotero 7 search() ist ASYNC -> await!
            const itemIDs = await s.search();
            const limitedIDs = itemIDs.slice(0, limit);

            // Items laden (getAsync ist besser in Zotero 7, aber get() geht oft noch)
            return await this.formatItems(limitedIDs);
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleRecentItems(request) {
        try {
            const limit = parseInt(request.query.limit || "5");
            const s = new Zotero.Search();
            s.libraryID = Zotero.Libraries.userLibraryID;
            s.addCondition('itemType', 'isNot', 'attachment');
            s.addCondition('itemType', 'isNot', 'note');

            // Wait for search to complete
            const itemIDs = await s.search();
            if (!itemIDs || itemIDs.length === 0) return MCPUtils.formatSuccess([]);

            // Load items for sorting
            const items = await Zotero.Items.getAsync(itemIDs);
            items.sort((a, b) => new Date(b.dateAdded) - new Date(a.dateAdded));

            const limitedItems = items.slice(0, limit);
            return await this.formatItems(limitedItems);
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
        }
    }

    async handleGetNotes(request) {
        try {
            const collectionKey = request.query.collectionKey;
            const parentItemKey = request.query.parentItemKey;

            if (collectionKey) {
                const collection = Zotero.Collections.getByLibraryAndKey(Zotero.Libraries.userLibraryID, collectionKey);
                if (!collection) return MCPUtils.formatError(`Collection not found: ${collectionKey}`);

                const itemIDs = collection.getChildItems(true);

                if (!itemIDs || itemIDs.length === 0) return MCPUtils.formatSuccess([]);

                const items = await Zotero.Items.getAsync(itemIDs);
                const notes = items.filter(item => item && item.isNote());
                return await this.formatNotes(notes);
            } else if (parentItemKey) {
                const parentItem = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, parentItemKey);
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
            // getByLibraryAndKey ist synchron, liefert aber Zotero Item Objekt
            const note = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key);

            if (!note) return { statusCode: 404, body: { error: "Not Found", message: "Note not found" } };
            if (!note.isNote()) return MCPUtils.formatError(`Item ${key} is not a note`);

            return MCPUtils.formatSuccess({
                key: note.key,
                note: note.getNote(),
                tags: note.getTags().map(t => t.tag),
                parentItemKey: note.parentItemKey || null,
                collections: note.getCollections(),
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
            note.libraryID = Zotero.Libraries.userLibraryID;
            note.setNote(body.note);

            if (body.parentItemKey) {
                const parent = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, body.parentItemKey);
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
            const note = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, key);

            if (!note) return { statusCode: 404, body: { error: "Not Found" } };
            if (!note.isNote()) return MCPUtils.formatError("Item is not a note");

            const body = request.body;
            if (body.note !== undefined) note.setNote(body.note);
            if (body.tags !== undefined) note.setTags(body.tags.map(t => ({ tag: t })));
            if (body.collections !== undefined) note.setCollections(body.collections);

            if (body.parentItemKey !== undefined) {
                if (body.parentItemKey === null) {
                    note.parentItemID = null;
                } else {
                    const parent = Zotero.Items.getByLibraryAndKey(Zotero.Libraries.userLibraryID, body.parentItemKey);
                    if (parent) note.parentItemID = parent.id;
                }
            }

            await note.saveTx();
            return MCPUtils.formatSuccess({ success: true, key: note.key });
        } catch (e) {
            return { statusCode: 500, body: { error: e.message } };
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
            items = await Zotero.Items.getAsync(validIDs);
        }

        const result = [];
        for (const item of items) {
            if (!item) continue;
            const creators = item.getCreators().map(c => c.firstName ? `${c.lastName}, ${c.firstName}` : c.lastName);
            result.push({
                key: item.key,
                itemType: Zotero.ItemTypes.getName(item.itemTypeID),
                title: item.getField('title') || '',
                creators: creators,
                date: item.getField('date') || '',
                tags: item.getTags().map(t => t.tag),
                collections: item.getCollections()
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
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            });
        }
        return MCPUtils.formatSuccess(result);
    }
};