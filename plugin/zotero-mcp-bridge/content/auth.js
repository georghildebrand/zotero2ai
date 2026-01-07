/* global Components, Services, Zotero */

/**
 * Authentication manager for MCP Bridge
 * Handles token generation, storage, and validation
 */
class AuthManager {
    constructor() {
        this.prefKey = "extensions.zotero-mcp-bridge.authToken";
        this.token = null;
    }

    /**
     * Initialize authentication - generate or load token
     */
    async init() {
        Zotero.debug("AuthManager: Initializing...");

        // Try to load existing token
        this.token = Zotero.Prefs.get(this.prefKey);

        if (!this.token) {
            // Generate new 256-bit token
            this.token = this.generateToken();
            Zotero.Prefs.set(this.prefKey, this.token);
            Zotero.debug("AuthManager: Generated new token");
        } else {
            Zotero.debug("AuthManager: Loaded existing token");
        }

        Zotero.debug(`AuthManager: Token = ${this.token}`);
    }

    /**
     * Generate a cryptographically secure 256-bit token
     * @returns {string} Hex-encoded token (64 characters)
     */
    generateToken() {
        // Generate 32 bytes (256 bits) of random data
        const array = new Uint8Array(32);
        crypto.getRandomValues(array);

        // Convert to hex string
        return Array.from(array)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }

    /**
     * Validate an authorization header
     * @param {string} authHeader - The Authorization header value
     * @returns {boolean} True if valid
     */
    validateAuth(authHeader) {
        if (!authHeader) {
            return false;
        }

        // Expected format: "Bearer <token>"
        const parts = authHeader.split(' ');
        if (parts.length !== 2 || parts[0] !== 'Bearer') {
            return false;
        }

        const providedToken = parts[1];
        return providedToken === this.token;
    }

    /**
     * Get the current token (for display in UI)
     * @returns {string} The current token
     */
    getToken() {
        return this.token;
    }

    /**
     * Clear the stored token (for testing/reset)
     */
    clearToken() {
        Zotero.Prefs.clear(this.prefKey);
        this.token = null;
        Zotero.debug("AuthManager: Token cleared");
    }
}
