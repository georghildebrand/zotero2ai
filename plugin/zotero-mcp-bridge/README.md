# Zotero MCP Bridge Plugin

HTTP API bridge for integrating Zotero with Model Context Protocol (MCP) servers.

## Development

### Building

```bash
cd plugin/zotero-mcp-bridge
zip -r ../zotero-mcp-bridge.xpi *
```

### Installation

1. Open Zotero
2. Go to Tools → Add-ons
3. Click gear icon → Install Add-on From File
4. Select `zotero-mcp-bridge.xpi`
5. Restart Zotero

### Testing

Check Zotero debug output (Help → Debug Output Logging) for:
```
MCP Bridge: Starting...
MCP Bridge: Started successfully
```

Test health endpoint:
```bash
curl http://localhost:23120/health
```

## Architecture

- `bootstrap.js` - Plugin entry point and lifecycle management
- `content/server.js` - HTTP server implementation
- `content/handlers.js` - Request handlers for each endpoint
- `content/utils.js` - Helper functions
