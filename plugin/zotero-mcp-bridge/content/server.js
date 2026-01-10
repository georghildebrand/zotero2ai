/* global Components, Services, Zotero, AuthManager, RequestHandlers */

var MCPServer = class {
    constructor() {
        this.serverSocket = null;
        this.port = 23120; // Port 23120
        this.host = "127.0.0.1";
        this.authManager = null;
        this.handlers = null;
    }

    async start() {
        Zotero.debug("MCPServer: Starting...");

        this.authManager = new AuthManager();
        await this.authManager.init();
        this.handlers = new RequestHandlers(this.authManager);

        try {
            this.serverSocket = Components.classes["@mozilla.org/network/server-socket;1"]
                .createInstance(Components.interfaces.nsIServerSocket);

            this.serverSocket.init(this.port, true, -1);
            this.serverSocket.asyncListen(this);

            Zotero.debug(`MCPServer: Listening on ${this.host}:${this.port}`);
            Zotero.debug(`MCPServer: Auth token = ${this.authManager.getToken()}`);
        } catch (e) {
            Zotero.debug(`MCPServer: FATAL ERROR starting server: ${e}`);
            throw e;
        }
    }

    async stop() {
        if (this.serverSocket) {
            try { this.serverSocket.close(); } catch (e) { }
            this.serverSocket = null;
            Zotero.debug("MCPServer: Stopped");
        }
    }

    // WICHTIG: Diese Methode wird vom System aufgerufen. 
    // Wir machen sie 'async', um await für die Handler nutzen zu können.
    async onSocketAccepted(serverSocket, transport) {
        try {
            const input = transport.openInputStream(0, 0, 0);
            const output = transport.openOutputStream(0, 0, 0);

            const scriptableIn = Components.classes["@mozilla.org/scriptableinputstream;1"]
                .createInstance(Components.interfaces.nsIScriptableInputStream);
            scriptableIn.init(input);

            let rawData = "";
            let retryCount = 0;
            // Wait up to 100ms for data if socket is accepted but nothing is available yet
            while (retryCount < 5 && scriptableIn.available() === 0) {
                await new Promise(resolve => setTimeout(resolve, 20));
                retryCount++;
            }

            if (scriptableIn.available()) {
                rawData = scriptableIn.read(scriptableIn.available());
            }

            if (!rawData) {
                Zotero.debug("MCPServer: No data received after waiting");
                input.close();
                output.close();
                return;
            }

            const request = this.parseRawRequest(rawData);

            // WICHTIG: Hier warten wir auf die asynchrone Handler-Antwort
            const response = await this.handleRequestWrapper(request);

            this.sendResponse(output, response);

            scriptableIn.close();
            input.close();
            // output wird in sendResponse geschlossen
        } catch (e) {
            Zotero.debug(`MCPServer: Connection error: ${e}`);
        }
    }

    onStopListening(serverSocket, status) { }

    parseRawRequest(rawData) {
        const lines = rawData.split('\r\n');
        const [method, pathStr] = lines[0].split(' ');

        const headers = {};
        let lineIndex = 1;
        while (lineIndex < lines.length && lines[lineIndex] !== '') {
            const line = lines[lineIndex];
            const separator = line.indexOf(':');
            if (separator > -1) {
                headers[line.substring(0, separator).trim().toLowerCase()] = line.substring(separator + 1).trim();
            }
            lineIndex++;
        }

        let body = null;
        if (lineIndex < lines.length - 1) {
            const bodyStr = lines.slice(lineIndex + 1).join('\r\n').replace(/\0/g, '');
            try {
                if (bodyStr.trim().startsWith('{') || bodyStr.trim().startsWith('[')) {
                    body = JSON.parse(bodyStr);
                } else {
                    body = bodyStr;
                }
            } catch (e) {
                body = bodyStr;
            }
        }

        let path = pathStr;
        let query = {};
        if (pathStr && pathStr.includes('?')) {
            const parts = pathStr.split('?');
            path = parts[0];
            const queryString = parts[1];
            queryString.split('&').forEach(param => {
                const [key, value] = param.split('=');
                if (key) query[decodeURIComponent(key)] = value ? decodeURIComponent(value) : '';
            });
        }

        return { method, path, query, headers, body };
    }

    async handleRequestWrapper(request) {
        try {
            if (request.method === "OPTIONS") {
                return { statusCode: 204, headers: this.getCORSHeaders(), body: null };
            }

            const host = request.headers['host'];
            if (!host || (!host.startsWith('127.0.0.1') && !host.startsWith('localhost'))) {
                return { statusCode: 403, body: { error: "Forbidden: Invalid Host header" } };
            }

            // WICHTIG: await hier, da die Handler nun async sind
            const result = await this.handlers.handle(request);

            if (!result.headers) result.headers = {};
            Object.assign(result.headers, this.getCORSHeaders());
            return result;
        } catch (e) {
            return { statusCode: 500, body: { error: "Internal Server Error", details: e.message } };
        }
    }

    sendResponse(outputStream, responseData) {
        try {
            const statusCode = responseData.statusCode || 200;
            const statusText = statusCode === 200 ? "OK" : (statusCode === 404 ? "Not Found" : "Result");

            let bodyStr = "";
            if (responseData.body) {
                bodyStr = typeof responseData.body === 'string' ? responseData.body : JSON.stringify(responseData.body);
            }

            // UTF-8 encoding for content-length
            const encoder = new TextEncoder();
            const bodyBytes = encoder.encode(bodyStr);

            let responseHead = `HTTP/1.1 ${statusCode} ${statusText}\r\n`;
            const headers = responseData.headers || {};
            headers["Content-Type"] = "application/json; charset=utf-8";
            headers["Content-Length"] = bodyBytes.length;
            headers["Connection"] = "close";

            for (const key in headers) {
                responseHead += `${key}: ${headers[key]}\r\n`;
            }
            responseHead += "\r\n";

            const bos = Components.classes["@mozilla.org/binaryoutputstream;1"]
                .createInstance(Components.interfaces.nsIBinaryOutputStream);
            bos.setOutputStream(outputStream);
            bos.writeBytes(responseHead, responseHead.length);

            if (bodyStr) {
                const converter = Components.classes["@mozilla.org/intl/converter-output-stream;1"]
                    .createInstance(Components.interfaces.nsIConverterOutputStream);
                converter.init(outputStream, "UTF-8");
                converter.writeString(bodyStr);
                converter.flush();
                // converter.close() would close outputStream, but we can also rely on bos.close()
            }
            bos.close();
        } catch (e) {
            Zotero.debug(`MCPServer: Error sending response: ${e}`);
        }
    }

    getCORSHeaders() {
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "86400"
        };
    }
};
