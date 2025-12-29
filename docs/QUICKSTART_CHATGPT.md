# ChatGPT Desktop Integration - Quick Start

## Summary

Your `zotero2ai` MCP server is now ready to integrate with ChatGPT Desktop! Here's what was done:

### Changes Made

1. **Updated MCP Server** (`src/zotero2ai/cli.py`)
   - Modified `cmd_run()` to actually start the MCP server using `mcp.run(transport="stdio")`
   - Previously it was just a validation stub; now it runs a real server

2. **Created Setup Script** (`scripts/setup-chatgpt-desktop.sh`)
   - Automated configuration generator
   - Auto-detects Zotero data directory
   - Handles existing configurations safely

3. **Documentation**
   - Comprehensive integration guide: `docs/CHATGPT_DESKTOP_INTEGRATION.md`
   - Example configuration: `docs/chatgpt-desktop-config.json`
   - Updated main README with integration instructions

4. **Updated Tests**
   - Fixed all tests to work with the new server implementation
   - All 51 tests passing ✅

## Quick Setup (3 Steps)

### Step 1: Run the Setup Script

```bash
cd /Users/georg.hildebrand/workspace/github.com/zotero2ai
./scripts/setup-chatgpt-desktop.sh
```

This will:
- Detect your Zotero directory
- Generate the MCP configuration
- Install it for ChatGPT Desktop

### Step 2: Restart ChatGPT Desktop

Completely quit and relaunch the ChatGPT Desktop app.

### Step 3: Test the Connection

In ChatGPT Desktop, try asking:
> "Can you ping the zotero2ai server?"

You should see a response indicating the server is connected.

## Manual Setup (Alternative)

If you prefer to configure manually, add this to:
`~/Library/Application Support/ChatGPT/mcp_config.json`

```json
{
  "mcpServers": {
    "zotero2ai": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/georg.hildebrand/workspace/github.com/zotero2ai",
        "mcp-zotero2ai",
        "run"
      ],
      "env": {
        "ZOTERO_DATA_DIR": "/Users/georg.hildebrand/Zotero"
      }
    }
  }
}
```

**Important**: Update the paths if your Zotero directory is in a different location.

## Troubleshooting

### Server Not Connecting?

1. Check the config file syntax (valid JSON)
2. Verify paths are correct and absolute
3. Run `make doctor` to check Zotero setup

### View Logs

Run the server manually to see what's happening:
```bash
cd /Users/georg.hildebrand/workspace/github.com/zotero2ai
uv run mcp-zotero2ai run
```

Press Ctrl+C to stop.

## What's Available Now (v0.1.0)

Currently, the server includes:
- ✅ Basic MCP server infrastructure
- ✅ Ping tool (for testing connectivity)
- ⏳ Full Zotero search (coming in future versions)
- ⏳ Vector search (coming in future versions)

## Next Steps

Once integrated, you can expand the server with:
- Zotero item search tools
- Collection browsing
- Note retrieval
- Hybrid search (lexical + vector)

See `docs/plans/zotero_2_ai_implementation_plan.md` for the full roadmap.

## Resources

- **Full Integration Guide**: `docs/CHATGPT_DESKTOP_INTEGRATION.md`
- **Main README**: `README.md`
- **Implementation Plan**: `docs/plans/zotero_2_ai_implementation_plan.md`

---

**Need Help?**
- Run `make doctor` to diagnose configuration issues
- Check the detailed guide in `docs/CHATGPT_DESKTOP_INTEGRATION.md`
- Review test output with `make test`
