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

    static fuzzyMatchScore(query, text, fullPath) {
        // Normalize inputs
        const queryLower = query.toLowerCase().trim();
        const textLower = text.toLowerCase();
        const pathLower = fullPath.toLowerCase();

        // Exact match = highest score
        if (textLower === queryLower) return 1000;
        if (pathLower === queryLower) return 900;

        // Contains exact query
        if (textLower.includes(queryLower)) return 800;
        if (pathLower.includes(queryLower)) return 100; // Drastically lowered to avoid matching all sub-collections by default

        // Token-based matching
        const queryTokens = queryLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);
        const textTokens = textLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);
        const pathTokens = pathLower.split(/[\s\-_\/]+/).filter(t => t.length > 0);

        let matchedTokens = 0;
        let partialMatches = 0;

        for (const qToken of queryTokens) {
            let matched = false;

            // Check text tokens FIRST (higher priority)
            for (const tToken of textTokens) {
                if (tToken === qToken) {
                    matchedTokens++;
                    matched = true;
                    break;
                } else if (tToken.includes(qToken) || qToken.includes(tToken)) {
                    partialMatches++;
                    matched = true;
                }
            }

            // Only check path if NOT already matched in text
            if (!matched) {
                for (const pToken of pathTokens) {
                    if (pToken === qToken) {
                        matchedTokens += 0.5; // Path matches worth less than name matches
                        break;
                    }
                }
            }
        }

        // Calculate score based on token matches
        const tokenRatio = matchedTokens / queryTokens.length;
        const partialRatio = partialMatches / queryTokens.length;

        if (tokenRatio >= 0.8) return 600; // 80%+ tokens match
        if (tokenRatio >= 0.6) return 500; // 60%+ tokens match
        if (tokenRatio >= 0.4) return 400; // 40%+ tokens match
        if (partialRatio >= 0.5) return 300; // 50%+ partial matches

        return 0; // No match
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