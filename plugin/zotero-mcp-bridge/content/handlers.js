/* global Zotero */

/**
 * Request handlers with authentication enforcement
 * Routes requests and enforces Bearer token authentication
 */
class RequestHandlers {
    constructor(authManager) {
        this.authManager = authManager;
    }

    /**
     * Main request handler
     * Enforces authentication and routes to appropriate handler
     */
    handle(request) {
        // Check authentication (all routes require auth)
        const authHeader = request.headers['authorization'];
        if (!this.authManager.validateAuth(authHeader)) {
            Zotero.debug("RequestHandlers: Authentication failed");
            return {
                statusCode: 401,
                body: {
                    error: "Unauthorized",
                    message: "Missing or invalid Bearer token"
                }
            };
        }

        // Route to appropriate handler
        const { method, path } = request;

        // Health check endpoint
        if (method === "GET" && path === "/health") {
            return this.handleHealth(request);
        }

        // Collections endpoint
        if (method === "GET" && path === "/collections") {
            return this.handleGetCollections(request);
        }

        // Items search endpoint
        if (method === "GET" && path.startsWith("/items/search")) {
            return this.handleSearchItems(request);
        }

        // Items recent endpoint
        if (method === "GET" && path === "/items/recent") {
            return this.handleRecentItems(request);
        }

        // Notes list endpoint
        if (method === "GET" && path === "/notes") {
            return this.handleGetNotes(request);
        }

        // Notes detail endpoint (GET /notes/{key})
        if (method === "GET" && path.match(/^\/notes\/[A-Z0-9]+$/)) {
            return this.handleGetNote(request);
        }

        // Notes create endpoint
        if (method === "POST" && path === "/notes") {
            return this.handleCreateNote(request);
        }

        // Notes update endpoint (PUT /notes/{key})
        if (method === "PUT" && path.match(/^\/notes\/[A-Z0-9]+$/)) {
            return this.handleUpdateNote(request);
        }

        // No route matched
        return {
            statusCode: 404,
            body: {
                error: "Not Found",
                message: `No handler for ${method} ${path}`
            }
        };
    }

    /**
     * Health check endpoint
     */
    handleHealth(request) {
        return {
            statusCode: 200,
            body: {
                status: "ok",
                version: "0.1.0",
                timestamp: new Date().toISOString()
            }
        };
    }

    /**
     * GET /collections - List all collections
     */
    handleGetCollections(request) {
        try {
            const collections = Zotero.Collections.getAll();
            const result = [];

            for (const collection of collections) {
                result.push({
                    key: collection.key,
                    name: collection.getName(),
                    parentKey: collection.parentKey || null,
                    fullPath: MCPUtils.getCollectionPath(collection),
                    libraryID: collection.libraryID
                });
            }

            return MCPUtils.formatSuccess(result);
        } catch (e) {
            Zotero.debug(`MCP Bridge: Error in handleGetCollections: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * GET /items/search - Search items by title
     * Query parameters:
     *   - q: search query (required)
     *   - limit: maximum number of results (default: 10)
     */
    handleSearchItems(request) {
        try {
            const searchQuery = request.query.q || "";
            const limit = parseInt(request.query.limit || "10");

            if (!searchQuery) {
                return MCPUtils.formatError("Missing 'q' query parameter");
            }

            // Search in default library (usually ID 1)
            const s = new Zotero.Search();
            s.libraryID = Zotero.Libraries.userLibraryID;
            s.addCondition('title', 'contains', searchQuery);
            s.addCondition('itemType', 'isNot', 'attachment');
            s.addCondition('itemType', 'isNot', 'note');

            const itemIDs = s.search();
            const limitedIDs = itemIDs.slice(0, limit);

            return this.formatItems(limitedIDs);
        } catch (e) {
            Zotero.debug(`MCP Bridge: Error in handleSearchItems: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * GET /items/recent - Get recent items sorted by dateAdded
     * Query parameters:
     *   - limit: maximum number of results (default: 5)
     */
    handleRecentItems(request) {
        try {
            const limit = parseInt(request.query.limit || "5");

            // Get recent items
            const s = new Zotero.Search();
            s.libraryID = Zotero.Libraries.userLibraryID;
            s.addCondition('itemType', 'isNot', 'attachment');
            s.addCondition('itemType', 'isNot', 'note');

            const itemIDs = s.search();

            // Sort by dateAdded (most recent first)
            const items = Zotero.Items.get(itemIDs);
            items.sort((a, b) => {
                const dateA = new Date(a.dateAdded);
                const dateB = new Date(b.dateAdded);
                return dateB - dateA;
            });

            const limitedIDs = items.slice(0, limit).map(item => item.id);

            return this.formatItems(limitedIDs);
        } catch (e) {
            Zotero.debug(`MCP Bridge: Error in handleRecentItems: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * GET /notes - List notes (summaries)
     * Query parameters:
     * - collectionKey: Filter notes by collection
     * - parentItemKey: Filter notes attached to a specific item
     */
    handleGetNotes(request) {
        try {
            const collectionKey = request.query.collectionKey;
            const parentItemKey = request.query.parentItemKey;

            let noteIDs = [];

            if (collectionKey) {
                // Get notes in collection
                const collection = Zotero.Collections.getByLibraryAndKey(
                    Zotero.Libraries.userLibraryID,
                    collectionKey
                );

                if (!collection) {
                    return MCPUtils.formatError(`Collection not found: ${collectionKey}`);
                }

                const itemIDs = collection.getChildItems();
                const items = Zotero.Items.get(itemIDs);
                noteIDs = items.filter(item => item.isNote()).map(item => item.id);

            } else if (parentItemKey) {
                // Get notes attached to item
                const parentItem = Zotero.Items.getByLibraryAndKey(
                    Zotero.Libraries.userLibraryID,
                    parentItemKey
                );

                if (!parentItem) {
                    return MCPUtils.formatError(`Item not found: ${parentItemKey}`);
                }

                noteIDs = parentItem.getNotes();

            } else {
                return MCPUtils.formatError("Must provide collectionKey or parentItemKey");
            }

            return this.formatNotes(noteIDs);
        } catch (e) {
            Zotero.debug(`MCP Bridge: Error in handleGetNotes: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * Format notes for response (summaries only)
     * @param {Array} noteIDs - Array of note IDs
     * @returns {Object} Formatted response with note summaries
     */
    formatNotes(noteIDs) {
        const notes = Zotero.Items.get(noteIDs);
        const result = [];

        for (const note of notes) {
            const tags = note.getTags().map(t => t.tag);
            const collections = note.getCollections();

            result.push({
                key: note.key,
                note: note.getNote(), // HTML content
                tags: tags,
                parentItemKey: note.parentItemKey || null,
                collections: collections,
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            });
        }

        return MCPUtils.formatSuccess(result);
    }

    /**
     * GET /notes/{key} - Get full note content
     * Returns complete note data including HTML content and metadata
     */
    handleGetNote(request) {
        try {
            // Extract key from path (e.g., /notes/ABC123XYZ)
            const key = request.path.split('/')[2];

            if (!key) {
                return MCPUtils.formatError("Missing note key in path");
            }

            // Get note by library and key
            const note = Zotero.Items.getByLibraryAndKey(
                Zotero.Libraries.userLibraryID,
                key
            );

            if (!note) {
                return {
                    statusCode: 404,
                    body: {
                        error: "Not Found",
                        message: `Note with key ${key} not found`
                    }
                };
            }

            // Verify it's actually a note
            if (!note.isNote()) {
                return MCPUtils.formatError(`Item ${key} is not a note`);
            }

            // Get note metadata
            const tags = note.getTags().map(t => t.tag);
            const collections = note.getCollections();

            // Build response with full note content
            const noteData = {
                key: note.key,
                note: note.getNote(), // Full HTML content
                tags: tags,
                parentItemKey: note.parentItemKey || null,
                collections: collections,
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            };

            return MCPUtils.formatSuccess(noteData);

        } catch (e) {
            Zotero.debug(`RequestHandlers: Error in handleGetNote: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * POST /notes - Create new note
     * Request body:
     * {
     *   "note": "HTML content",  // required
     *   "tags": ["tag1", "tag2"],  // optional
     *   "collections": ["KEY1", "KEY2"],  // optional
     *   "parentItemKey": "ITEMKEY"  // optional
     * }
     */
    handleCreateNote(request) {
        try {
            // Parse request body
            const body = request.body;
            if (!body) {
                return MCPUtils.formatError("Missing request body");
            }

            // Validate required fields
            if (body.note === undefined || body.note === null) {
                return MCPUtils.formatError("Missing required field: note");
            }

            // Create new note item
            const note = new Zotero.Item('note');
            note.libraryID = Zotero.Libraries.userLibraryID;
            note.setNote(body.note);

            // Set parent item if provided
            if (body.parentItemKey) {
                const parentItem = Zotero.Items.getByLibraryAndKey(
                    Zotero.Libraries.userLibraryID,
                    body.parentItemKey
                );
                if (!parentItem) {
                    return MCPUtils.formatError(`Parent item not found: ${body.parentItemKey}`);
                }
                note.parentItemID = parentItem.id;
            }

            // Set tags if provided
            if (body.tags !== undefined) {
                if (!Array.isArray(body.tags)) {
                    return MCPUtils.formatError("Tags must be an array");
                }
                note.setTags(body.tags.map(tag => ({ tag: tag })));
            }

            // Save the note first to get an ID
            const noteID = note.save();

            // Set collections if provided (must be done after save)
            if (body.collections !== undefined) {
                if (!Array.isArray(body.collections)) {
                    return MCPUtils.formatError("Collections must be an array");
                }

                // Validate all collections exist
                for (const collectionKey of body.collections) {
                    const collection = Zotero.Collections.getByLibraryAndKey(
                        Zotero.Libraries.userLibraryID,
                        collectionKey
                    );
                    if (!collection) {
                        // Clean up the created note
                        note.deleted = true;
                        note.save();
                        return MCPUtils.formatError(`Collection not found: ${collectionKey}`);
                    }
                }

                note.setCollections(body.collections);
                note.save();
            }

            // Return created note data
            const tags = note.getTags().map(t => t.tag);
            const collections = note.getCollections();

            const noteData = {
                key: note.key,
                note: note.getNote(),
                tags: tags,
                parentItemKey: note.parentItemKey || null,
                collections: collections,
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            };

            return {
                statusCode: 201,
                body: {
                    success: true,
                    data: noteData
                }
            };

        } catch (e) {
            Zotero.debug(`RequestHandlers: Error in handleCreateNote: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * PUT /notes/{key} - Update existing note
     * Request body:
     * {
     *   "note": "HTML content",
     *   "tags": ["tag1", "tag2"],  // optional
     *   "collections": ["KEY1", "KEY2"],  // optional
     *   "parentItemKey": "ITEMKEY"  // optional
     * }
     */
    handleUpdateNote(request) {
        try {
            // Extract key from path (e.g., /notes/ABC123XYZ)
            const key = request.path.split('/')[2];

            if (!key) {
                return MCPUtils.formatError("Missing note key in path");
            }

            // Get note by library and key
            const note = Zotero.Items.getByLibraryAndKey(
                Zotero.Libraries.userLibraryID,
                key
            );

            if (!note) {
                return {
                    statusCode: 404,
                    body: {
                        error: "Not Found",
                        message: `Note with key ${key} not found`
                    }
                };
            }

            // Verify it's actually a note
            if (!note.isNote()) {
                return MCPUtils.formatError(`Item ${key} is not a note`);
            }

            // Parse request body
            const body = request.body;
            if (!body) {
                return MCPUtils.formatError("Missing request body");
            }

            // Update note content if provided
            if (body.note !== undefined) {
                note.setNote(body.note);
            }

            // Update tags if provided
            if (body.tags !== undefined) {
                if (!Array.isArray(body.tags)) {
                    return MCPUtils.formatError("Tags must be an array");
                }
                note.setTags(body.tags.map(tag => ({ tag: tag })));
            }

            // Update collections if provided
            if (body.collections !== undefined) {
                if (!Array.isArray(body.collections)) {
                    return MCPUtils.formatError("Collections must be an array");
                }
                note.setCollections(body.collections);
            }

            // Update parent item if provided
            if (body.parentItemKey !== undefined) {
                if (body.parentItemKey === null) {
                    // Remove parent (make standalone note)
                    note.parentItemID = null;
                } else {
                    // Set new parent
                    const parentItem = Zotero.Items.getByLibraryAndKey(
                        Zotero.Libraries.userLibraryID,
                        body.parentItemKey
                    );
                    if (!parentItem) {
                        return MCPUtils.formatError(`Parent item not found: ${body.parentItemKey}`);
                    }
                    note.parentItemID = parentItem.id;
                }
            }

            // Save the note
            note.save();

            // Return updated note data
            const tags = note.getTags().map(t => t.tag);
            const collections = note.getCollections();

            const noteData = {
                key: note.key,
                note: note.getNote(),
                tags: tags,
                parentItemKey: note.parentItemKey || null,
                collections: collections,
                dateAdded: note.dateAdded,
                dateModified: note.dateModified
            };

            return MCPUtils.formatSuccess(noteData);

        } catch (e) {
            Zotero.debug(`RequestHandlers: Error in handleUpdateNote: ${e.message}`);
            return {
                statusCode: 500,
                body: {
                    error: "Internal Server Error",
                    message: e.message
                }
            };
        }
    }

    /**
     * Helper method to format items for API response
     * @param {Array} itemIDs - Array of Zotero item IDs
     * @returns {Object} Formatted response with item data
     */
    formatItems(itemIDs) {
        const items = Zotero.Items.get(itemIDs);
        const result = [];

        for (const item of items) {
            const creators = item.getCreators().map(c => {
                if (c.firstName) {
                    return `${c.lastName}, ${c.firstName}`;
                }
                return c.lastName;
            });

            const tags = item.getTags().map(t => t.tag);
            const collections = item.getCollections();

            result.push({
                key: item.key,
                itemType: Zotero.ItemTypes.getName(item.itemTypeID),
                title: item.getField('title') || '',
                creators: creators,
                date: item.getField('date') || '',
                tags: tags,
                collections: collections
            });
        }

        return MCPUtils.formatSuccess(result);
    }
}

