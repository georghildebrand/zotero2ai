/* global Components, Services, Zotero */

const { HttpServer } = ChromeUtils.import("resource://gre/modules/Http.jsm");

/**
 * Production HTTP server for MCP Bridge
 * Handles all HTTP communication with proper UTF-8, CORS, and security
 */
class MCPServer {
    constructor() {
        this.server = null;
        this.port = 23119; // Default port
        this.host = "127.0.0.1"; // Loopback only for security
        this.authManager = null;
        this.handlers = null;
    }

    /**
     * Start the HTTP server
     */
    async start() {
        Zotero.debug("MCPServer: Starting...");

        // Initialize authentication
        this.authManager = new AuthManager();
        await this.authManager.init();

        // Initialize request handlers
        this.handlers = new RequestHandlers(this.authManager);

        // Create and configure HTTP server
        this.server = new HttpServer();
        this.server.registerPrefixHandler("/", this.handleRequest.bind(this));

        // Start server on loopback only
        this.server.start(this.port);

        Zotero.debug(`MCPServer: Listening on ${this.host}:${this.port}`);
        Zotero.debug(`MCPServer: Auth token = ${this.authManager.getToken()}`);
    }

    /**
     * Stop the HTTP server
     */
    async stop() {
        if (this.server) {
            Zotero.debug("MCPServer: Stopping...");
            await new Promise((resolve) => {
                this.server.stop(() => {
                    Zotero.debug("MCPServer: Stopped");
                    resolve();
                });
            });
            this.server = null;
        }
    }

    /**
     * Main request handler
     * Handles OPTIONS, body reading, UTF-8, and delegates to route handlers
     */
    handleRequest(request, response) {
        try {
            Zotero.debug(`MCPServer: ${request.method} ${request.path}`);

            // Handle OPTIONS for CORS preflight
            if (request.method === "OPTIONS") {
                this.handleOptions(response);
                return;
            }

            // Security: Enforce Host header check to prevent DNS rebinding
            // This ensures we only accept requests intended for localhost
            try {
                const hostHeader = request.getHeader("Host");
                const hostname = hostHeader ? hostHeader.split(":")[0] : "";
                if (hostname !== "127.0.0.1" && hostname !== "localhost") {
                    Zotero.debug(`MCPServer: Rejected request with invalid Host header: ${hostname}`);
                    this.sendResponse(response, {
                        statusCode: 403,
                        body: { error: "Forbidden: Invalid Host header" }
                    });
                    return;
                }
            } catch (e) {
                Zotero.debug(`MCPServer: Error checking Host header (likely missing): ${e}`);
                this.sendResponse(response, {
                    statusCode: 400,
                    body: { error: "Bad Request: Missing or invalid Host header" }
                });
                return;
            }

            // Read request body if present
            let body = null;
            if (request.method === "POST" || request.method === "PUT") {
                body = this.readRequestBody(request);
            }

            // Parse query parameters from URL
            const query = this.parseQueryParams(request.path);

            // Build request object
            const req = {
                method: request.method,
                path: request.path.split('?')[0], // Remove query string from path
                query: query,
                headers: this.extractHeaders(request),
                body: body
            };

            // Delegate to handlers
            const result = this.handlers.handle(req);

            // Send response
            this.sendResponse(response, result);

        } catch (error) {
            Zotero.debug(`MCPServer: Error handling request: ${error}`);
            this.sendResponse(response, {
                statusCode: 500,
                body: { error: "Internal server error" }
            });
        }
    }

    /**
     * Handle OPTIONS request for CORS
     */
    handleOptions(response) {
        response.setStatusLine("1.1", 204, "No Content");
        this.setCORSHeaders(response);
        response.setHeader("Allow", "GET, POST, PUT, DELETE, OPTIONS", false);
        response.finish();
    }

    /**
     * Read request body with proper UTF-8 handling
     * CRITICAL: Uses Content-Length, not available()
     */
    readRequestBody(request) {
        try {
            const contentLength = parseInt(request.getHeader("Content-Length") || "0");

            if (contentLength === 0) {
                return null;
            }

            // Read exact number of bytes specified by Content-Length
            const inputStream = request.bodyInputStream;
            const scriptableStream = Components.classes["@mozilla.org/scriptableinputstream;1"]
                .createInstance(Components.interfaces.nsIScriptableInputStream);
            scriptableStream.init(inputStream);

            // Read bytes
            const bytes = scriptableStream.read(contentLength);
            scriptableStream.close();

            // Convert from UTF-8 bytes to string
            const converter = Components.classes["@mozilla.org/intl/scriptableunicodeconverter"]
                .createInstance(Components.interfaces.nsIScriptableUnicodeConverter);
            converter.charset = "UTF-8";

            const bodyString = converter.ConvertToUnicode(bytes);

            // Parse JSON if content-type is JSON
            const contentType = request.getHeader("Content-Type") || "";
            if (contentType.includes("application/json")) {
                return JSON.parse(bodyString);
            }

            return bodyString;

        } catch (error) {
            Zotero.debug(`MCPServer: Error reading request body: ${error}`);
            throw error;
        }
    }

    /**
     * Parse query parameters from URL path
     * @param {string} path - Request path potentially containing query string
     * @returns {Object} Object with query parameter key-value pairs
     */
    parseQueryParams(path) {
        const query = {};
        const queryIndex = path.indexOf('?');

        if (queryIndex === -1) {
            return query;
        }

        const queryString = path.substring(queryIndex + 1);
        const pairs = queryString.split('&');

        for (const pair of pairs) {
            const [key, value] = pair.split('=');
            if (key) {
                query[decodeURIComponent(key)] = value ? decodeURIComponent(value) : '';
            }
        }

        return query;
    }

    /**
     * Extract headers from request
     */
    extractHeaders(request) {
        const headers = {};
        const headerEnum = request.headers;

        while (headerEnum.hasMoreElements()) {
            const header = headerEnum.getNext().QueryInterface(Components.interfaces.nsISupportsString);
            const [name, value] = header.data.split(": ", 2);
            headers[name.toLowerCase()] = value;
        }

        return headers;
    }

    /**
     * Send HTTP response with proper UTF-8 and headers
     */
    sendResponse(response, result) {
        const statusCode = result.statusCode || 200;
        const body = result.body || {};

        // Set status
        response.setStatusLine("1.1", statusCode, this.getStatusText(statusCode));

        // Set CORS headers
        this.setCORSHeaders(response);

        // CRITICAL: Always send Connection: close
        response.setHeader("Connection", "close", false);

        // Convert body to JSON
        const jsonBody = JSON.stringify(body);

        // Convert to UTF-8 bytes and calculate Content-Length
        const converter = Components.classes["@mozilla.org/intl/scriptableunicodeconverter"]
            .createInstance(Components.interfaces.nsIScriptableUnicodeConverter);
        converter.charset = "UTF-8";

        const bodyBytes = converter.ConvertFromUnicode(jsonBody);
        const byteLength = bodyBytes.length;

        // Set headers
        response.setHeader("Content-Type", "application/json; charset=utf-8", false);
        response.setHeader("Content-Length", byteLength.toString(), false);

        // Write body
        response.write(bodyBytes);
        response.finish();
    }

    /**
     * Set CORS headers for cross-origin requests
     */
    setCORSHeaders(response) {
        response.setHeader("Access-Control-Allow-Origin", "*", false);
        response.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS", false);
        response.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization", false);
        response.setHeader("Access-Control-Max-Age", "86400", false);
    }

    /**
     * Get HTTP status text
     */
    getStatusText(code) {
        const statusTexts = {
            200: "OK",
            201: "Created",
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error"
        };
        return statusTexts[code] || "Unknown";
    }
}
