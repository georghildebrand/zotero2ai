/* global Zotero */

var MCPUtils = class {
    static getCollectionPath(collection) {
        // Zotero 7 nutzt Properties, Zotero 6 Methoden. Wir nutzen robust Properties.
        let path = collection.name || (typeof collection.getName === 'function' ? collection.getName() : "Unknown");
        let parent = collection.parent || (typeof collection.getParent === 'function' ? collection.getParent() : null);

        while (parent) {
            let parentName = parent.name || (typeof parent.getName === 'function' ? parent.getName() : "Unknown");
            path = parentName + " / " + path;
            parent = parent.parent || (typeof parent.getParent === 'function' ? parent.getParent() : null);
        }
        return path;
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