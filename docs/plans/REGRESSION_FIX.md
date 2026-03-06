# Regression Fix: Search & Hierarchy Issues

**Date**: 2026-01-10  
**Severity**: Critical  
**Status**: Diagnosed

## Problem Summary

After implementing the improvements, three critical regressions occurred:
1. **Search returns wrong collections** (false positives)
2. **Hierarchy appears flat** (only 9 root folders visible)
3. **Specific collections not found** (e.g., "Wetterdatenprojekt")

## Root Cause Analysis

### Issue #1: Fuzzy Search Double-Counting Bug

**Location**: `plugin/zotero-mcp-bridge/content/utils.js` lines 50-68

**Problem**: The token matching loop has a logic error that causes double-counting:

```javascript
for (const qToken of queryTokens) {
    // Check text tokens
    for (const tToken of textTokens) {
        if (tToken === qToken) {
            matchedTokens++;
            break;  // ✅ Correctly breaks after match
        } else if (tToken.includes(qToken) || qToken.includes(tToken)) {
            partialMatches++;
        }
    }

    // Check path tokens
    for (const pToken of pathTokens) {
        if (pToken === qToken) {
            matchedTokens += 0.5;  // ❌ BUG: Can add to SAME qToken!
            break;
        }
    }
}
```

**Impact**: A query token can match BOTH in text AND in path, inflating the score incorrectly.

**Example**:
- Query: `"x2025"`
- Collection A: `"02-Private projects"` (path: `"02-Private projects"`)
  - Text tokens: `["02", "private", "projects"]`
  - Path tokens: `["02", "private", "projects"]`
  - If `"02"` partially matches `"x2025"`, it gets counted in both loops!
  
- Collection B: `"x2025"` (path: `"00 Projects / x2025"`)
  - Should score 1000 (exact match)
  - But Collection A might score higher due to double-counting

### Issue #2: Hierarchy Not Visible (By Design, Not Bug)

**Location**: MCP Server tool `list_collections()`

**Behavior**: When called without `parent_key`, it returns ALL collections in a flat list.

**Why it looks broken**: The agent sees 200+ collections but they're not indented/nested in the output.

**This is actually CORRECT** - the flat list includes all nested collections. The issue is presentation, not data.

### Issue #3: Collections "Not Found" (Pagination/Scoring)

**Possible Causes**:
1. **Fuzzy score too low**: Due to the double-counting bug, correct matches might score below the `minScore` threshold (300).
2. **Search not looking at full path**: The scoring function checks `fullPath`, but if the path isn't being constructed correctly, it won't match.

## Fixes Required

### Fix #1: Correct Fuzzy Match Scoring

**File**: `plugin/zotero-mcp-bridge/content/utils.js`

**Change**: Prevent double-counting by tracking which query tokens have already been matched:

```javascript
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
    if (pathLower.includes(queryLower)) return 700;

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
                    matchedTokens += 0.5; // Path matches worth less
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
```

### Fix #2: Improve Search Debugging

**File**: `plugin/zotero-mcp-bridge/content/handlers.js`

**Change**: Add debug logging to see what's happening:

```javascript
async handleSearchCollections(request) {
    try {
        const query = (request.query.q || "").trim();
        if (!query) return MCPUtils.formatError("Missing 'q' query parameter");

        const minScore = parseInt(request.query.minScore || "300");
        const limit = parseInt(request.query.limit || "50");

        // Search across all libraries
        const libraries = Zotero.Libraries.getAll();
        const allCollectionsResult = [];

        for (const lib of libraries) {
            const allCollections = Zotero.Collections.getByLibrary(lib.id);
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
```

### Fix #3: Lower Default minScore

**File**: `plugin/zotero-mcp-bridge/content/handlers.js` line 261

**Change**: Lower the default threshold to catch more matches:

```javascript
const minScore = parseInt(request.query.minScore || "200"); // Was 300
```

## Testing Plan

1. **Test exact match**:
   ```
   search_collections("x2025")
   Expected: Returns "00 Projects / x2025" with score 1000
   ```

2. **Test partial match**:
   ```
   search_collections("2023-11")
   Expected: Returns "00 Projects / 2023-11 Blog Posts" with high score
   ```

3. **Test false positive**:
   ```
   search_collections("x2025")
   Expected: Does NOT return "02-Private projects"
   ```

4. **Test missing collection**:
   ```
   search_collections("Wetterdatenprojekt")
   Expected: Returns the collection (wherever it is in the hierarchy)
   ```

## Implementation Priority

1. **CRITICAL**: Fix fuzzy scoring (Fix #1) - Implement immediately
2. **HIGH**: Add debug logging (Fix #2) - Helps diagnose remaining issues
3. **MEDIUM**: Lower minScore (Fix #3) - Can be adjusted after testing

## Rollback Plan

If the fix causes new issues:
1. Revert `utils.js` to simple substring matching:
   ```javascript
   static fuzzyMatchScore(query, text, fullPath) {
       const queryLower = query.toLowerCase();
       const textLower = text.toLowerCase();
       const pathLower = fullPath.toLowerCase();
       
       if (textLower === queryLower) return 1000;
       if (textLower.includes(queryLower)) return 800;
       if (pathLower.includes(queryLower)) return 700;
       return 0;
   }
   ```

2. Set `minScore` to 0 to return all substring matches.

---

**Next Step**: Implement Fix #1 immediately and rebuild the plugin.
