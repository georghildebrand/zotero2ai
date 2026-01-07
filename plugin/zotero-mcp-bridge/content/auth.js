/* global Components, Services, Zotero */

var AuthManager = class {
    constructor() {
        this.prefKey = "extensions.zotero-mcp-bridge.authToken";
        this.token = null;
    }

    async init() {
        Zotero.debug("AuthManager: Initializing...");
        this.token = Zotero.Prefs.get(this.prefKey);

        if (!this.token) {
            this.token = this.generateToken();
            Zotero.Prefs.set(this.prefKey, this.token);
            Zotero.debug("AuthManager: Generated new token");
        } else {
            Zotero.debug("AuthManager: Loaded existing token");
        }
        // Don't log full token in production, but okay for debug
        Zotero.debug(`AuthManager: Token ready`);
    }

    generateToken() {
        const array = new Uint8Array(32);
        crypto.getRandomValues(array);
        return Array.from(array)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }

    validateAuth(authHeader) {
        if (!authHeader) return false;
        const parts = authHeader.split(' ');
        if (parts.length !== 2 || parts[0] !== 'Bearer') return false;
        return parts[1] === this.token;
    }

    getToken() {
        return this.token;
    }
};