# ChatGPT Desktop Integration Guide

This guide explains how to integrate `zotero2ai` with ChatGPT Desktop using the Model Context Protocol (MCP).

## Prerequisites

1. **ChatGPT Desktop App**: Download and install from [OpenAI's website](https://openai.com/chatgpt/desktop/)
2. **zotero2ai installed**: Follow the main README installation instructions
3. **Zotero**: Have Zotero installed with your research library

## Setup Steps

### 1. Locate Your Zotero Data Directory

First, find where your Zotero data is stored. Common locations:
- macOS: `~/Zotero` or `~/Library/Application Support/Zotero`
- Linux: `~/Zotero`
- Windows: `C:\Users\<username>\Zotero`

You can verify this in Zotero: **Preferences → Advanced → Files and Folders → Data Directory Location**

### 2. Configure ChatGPT Desktop

ChatGPT Desktop reads MCP server configurations from a JSON file:

**macOS**: `~/Library/Application Support/ChatGPT/mcp_config.json`

If the file doesn't exist, create it. Add the following configuration:

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

**Important**: Update the paths:
- Replace `/Users/georg.hildebrand/workspace/github.com/zotero2ai` with your actual project path
- Replace `/Users/georg.hildebrand/Zotero` with your actual Zotero data directory

### 3. If You Have Multiple MCP Servers

If you already have other MCP servers configured, merge the configurations:

```json
{
  "mcpServers": {
    "existing-server": {
      "command": "...",
      "args": [...]
    },
    "zotero2ai": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/zotero2ai",
        "mcp-zotero2ai",
        "run"
      ],
      "env": {
        "ZOTERO_DATA_DIR": "/path/to/Zotero"
      }
    }
  }
}
```

### 4. Restart ChatGPT Desktop

After saving the configuration file:
1. Quit ChatGPT Desktop completely
2. Relaunch the application
3. The MCP server should automatically start when you begin a new chat

### 5. Verify Integration

In ChatGPT Desktop, you should see:
- A small icon or indicator showing MCP servers are connected
- The ability to use tools from `zotero2ai`

Try asking: "Can you ping the zotero2ai server?" to test the connection.

## Troubleshooting

### Server Not Connecting

1. **Check the configuration file syntax**: Ensure valid JSON (no trailing commas, proper quotes)
2. **Verify paths**: Make sure all paths in the config are absolute and correct
3. **Check logs**: Look for error messages in ChatGPT Desktop's console

### Permission Issues

If you get permission errors:
```bash
chmod +x /path/to/zotero2ai/src/zotero2ai/cli.py
```

### Zotero Database Not Found

Run the diagnostic command:
```bash
cd /path/to/zotero2ai
make doctor
```

This will verify your Zotero setup.

### View Logs

To see what's happening with your MCP server, you can run it manually:
```bash
cd /path/to/zotero2ai
uv run mcp-zotero2ai run
```

Then type messages in JSON-RPC format to test (Ctrl+C to exit).

## Alternative: Using Python Virtual Environment

If you prefer not to use `uv`, you can configure ChatGPT Desktop to use a Python virtual environment:

```json
{
  "mcpServers": {
    "zotero2ai": {
      "command": "/path/to/zotero2ai/.venv/bin/python",
      "args": [
        "-m",
        "zotero2ai.cli",
        "run"
      ],
      "env": {
        "ZOTERO_DATA_DIR": "/path/to/Zotero"
      }
    }
  }
}
```

## What's Next?

Once integrated, you can:
- Ask ChatGPT to search your Zotero library
- Query specific papers, notes, or collections
- Get summaries of your research materials
- Find connections between different sources

## Current Limitations (v0.1.0)

The current version includes:
- ✅ Basic MCP server setup
- ✅ Ping tool for connectivity testing
- ⏳ Full Zotero search capabilities (coming in future versions)
- ⏳ Vector search (coming in future versions)

## Support

For issues or questions:
- Check the main [README.md](../README.md)
- Run `make doctor` to diagnose configuration issues
- Review the [implementation plan](plans/zotero_2_ai_implementation_plan.md)
