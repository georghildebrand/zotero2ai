/* global Components, Services, Zotero */

var MCPBridge = {
    server: null,

    async startup(rootURI) {
        Zotero.debug("MCP Bridge: Starting...");

        // Import modules in dependency order using rootURI
        Services.scriptloader.loadSubScript(
            rootURI + "content/auth.js",
            this
        );
        Services.scriptloader.loadSubScript(
            rootURI + "content/utils.js",
            this
        );
        Services.scriptloader.loadSubScript(
            rootURI + "content/handlers.js",
            this
        );
        Services.scriptloader.loadSubScript(
            rootURI + "content/server.js",
            this
        );

        // Start HTTP server
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
    Zotero.debug(`MCP Bridge: rootURI type = ${typeof rootURI}`);
    Zotero.debug(`MCP Bridge: rootURI = ${rootURI}`);

    // rootURI is an nsIURI object, convert to string
    let rootPath = rootURI.spec;
    Zotero.debug(`MCP Bridge: rootPath = ${rootPath}`);

    // Ensure trailing slash
    if (!rootPath.endsWith('/')) {
        rootPath += '/';
        Zotero.debug(`MCP Bridge: Added trailing slash: ${rootPath}`);
    }

    await MCPBridge.startup(rootPath);
}

async function shutdown() {
    Zotero.debug("MCP Bridge: shutdown called");
    await MCPBridge.shutdown();
}
