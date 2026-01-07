/* global Zotero */

/**
 * Utility functions for MCP Bridge
 */
class MCPUtils {
    /**
     * Get full hierarchical path for a collection
     * @param {Object} collection - Zotero collection object
     * @returns {string} Full path with parent collections separated by " / "
     */
    static getCollectionPath(collection) {
        let path = collection.getName();
        let parent = collection.getParent();

        while (parent) {
            path = parent.getName() + " / " + path;
            parent = parent.getParent();
        }

        return path;
    }

    /**
     * Format error response
     * @param {string} message - Error message
     * @returns {Object} Formatted error response
     */
    static formatError(message) {
        return {
            statusCode: 400,
            body: { error: message }
        };
    }

    /**
     * Format success response
     * @param {*} data - Response data
     * @returns {Object} Formatted success response
     */
    static formatSuccess(data) {
        return {
            statusCode: 200,
            body: data
        };
    }
}
