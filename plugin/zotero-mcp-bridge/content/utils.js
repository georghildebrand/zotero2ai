/* global Zotero */

var MCPUtils = class {
    static getCollectionPath(collection) {
        try {
            let name = collection.name || (typeof collection.getName === 'function' ? collection.getName() : "Unknown");
            let path = name;
            let current = collection;

            // Limit recursion depth to prevent infinite loops just in case
            let depth = 0;
            while (current.parentKey && depth < 20) {
                const parent = Zotero.Collections.getByLibraryAndKey(current.libraryID, current.parentKey);
                if (!parent) break;

                let parentName = parent.name || (typeof parent.getName === 'function' ? parent.getName() : "Unknown");
                path = parentName + " / " + path;
                current = parent;
                depth++;
            }
            return path;
        } catch (e) {
            Zotero.debug("MCP: Error in getCollectionPath: " + e);
            return collection.name || "Unknown";
        }
    }

    static formatError(message) {
        return {
            statusCode: 400,
            body: { error: message }
        };
    }

    static formatSuccess(data) {
        return {
            statusCode: 200,
            body: { success: true, data: data } // Standardisiertes Format
        };
    }
};