/* global Components, Services, Zotero */

var MCPBridge = {
    server: null,

    async startup(rootPath) {
        Zotero.debug("MCP Bridge: Starting...");

        // Import modules into global scope (sandbox)
        // Order matters!
        Services.scriptloader.loadSubScript(rootPath + "content/utils.js");
        Services.scriptloader.loadSubScript(rootPath + "content/auth.js");
        Services.scriptloader.loadSubScript(rootPath + "content/handlers.js");
        Services.scriptloader.loadSubScript(rootPath + "content/server.js");

        // Start HTTP server
        Zotero.debug("MCP Bridge: Classes loaded, initializing server...");
        this.server = new MCPServer();
        await this.server.start();

        Zotero.debug("MCP Bridge: Started successfully");
    },

    async shutdown() {
        Zotero.debug("MCP Bridge: Shutting down...");

        if (this.server) {
            await this.server.stop();
            this.server = null;
        }

        Zotero.debug("MCP Bridge: Shutdown complete");
    }
};

function install() {
    Zotero.debug("MCP Bridge: Installing...");
}

function uninstall() {
    Zotero.debug("MCP Bridge: Uninstalling...");
}

async function startup({ id, version, rootURI }) {
    Zotero.debug(`MCP Bridge: startup called (version ${version})`);

    // Fix for rootURI being string or object
    let rootPath;
    if (typeof rootURI === 'string') {
        rootPath = rootURI;
    } else if (rootURI && typeof rootURI.spec === 'string') {
        rootPath = rootURI.spec;
    } else {
        Zotero.debug("MCP Bridge: ERROR - Invalid rootURI format");
        return;
    }

    if (!rootPath.endsWith('/')) {
        rootPath += '/';
    }

    await MCPBridge.startup(rootPath);
}

async function shutdown() {
    await MCPBridge.shutdown();
}