#!/usr/bin/env bash
# Setup script for ChatGPT Desktop integration

set -e

echo "🔧 zotero2ai ChatGPT Desktop Setup"
echo "=================================="
echo ""

# Get the absolute path to the project
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "📁 Project directory: $PROJECT_DIR"

# Detect Zotero data directory
ZOTERO_DIR=""
if [ -d "$HOME/Zotero" ]; then
    ZOTERO_DIR="$HOME/Zotero"
elif [ -d "$HOME/zotero" ]; then
    ZOTERO_DIR="$HOME/zotero"
elif [ -d "$HOME/Library/Application Support/Zotero" ]; then
    ZOTERO_DIR="$HOME/Library/Application Support/Zotero"
fi

if [ -z "$ZOTERO_DIR" ]; then
    echo "⚠️  Could not auto-detect Zotero directory"
    read -p "Enter your Zotero data directory path: " ZOTERO_DIR
fi

echo "📚 Zotero directory: $ZOTERO_DIR"

# Verify Zotero directory
if [ ! -d "$ZOTERO_DIR" ]; then
    echo "❌ Error: Zotero directory not found: $ZOTERO_DIR"
    exit 1
fi

if [ ! -f "$ZOTERO_DIR/zotero.sqlite" ]; then
    echo "❌ Error: zotero.sqlite not found in $ZOTERO_DIR"
    exit 1
fi

echo "✅ Zotero directory verified"
echo ""

# Determine ChatGPT config location
if [[ "$OSTYPE" == "darwin"* ]]; then
    CONFIG_DIR="$HOME/Library/Application Support/ChatGPT"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CONFIG_DIR="$HOME/.config/ChatGPT"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

CONFIG_FILE="$CONFIG_DIR/mcp_config.json"
echo "📝 ChatGPT config file: $CONFIG_FILE"

# Create config directory if it doesn't exist
mkdir -p "$CONFIG_DIR"

# Generate the configuration
cat > /tmp/zotero2ai_mcp_config.json <<EOF
{
  "mcpServers": {
    "zotero2ai": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "$PROJECT_DIR",
        "mcp-zotero2ai",
        "run"
      ],
      "env": {
        "ZOTERO_DATA_DIR": "$ZOTERO_DIR"
      }
    }
  }
}
EOF

echo ""
echo "Generated configuration:"
echo "========================"
cat /tmp/zotero2ai_mcp_config.json
echo "========================"
echo ""

# Check if config file exists
if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  ChatGPT config file already exists"
    echo ""
    echo "You have two options:"
    echo "1. Backup and replace the existing config (if you have no other MCP servers)"
    echo "2. Manually merge the configuration shown above into your existing file"
    echo ""
    read -p "Do you want to backup and replace? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
        echo "✅ Backed up existing config"
        cp /tmp/zotero2ai_mcp_config.json "$CONFIG_FILE"
        echo "✅ Installed new config"
    else
        echo ""
        echo "📋 Please manually add the zotero2ai section to: $CONFIG_FILE"
        echo "   The configuration has been saved to: /tmp/zotero2ai_mcp_config.json"
    fi
else
    cp /tmp/zotero2ai_mcp_config.json "$CONFIG_FILE"
    echo "✅ Created ChatGPT config file"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Restart ChatGPT Desktop"
echo "2. Start a new chat"
echo "3. Try asking: 'Can you ping the zotero2ai server?'"
echo ""
echo "For more information, see: docs/CHATGPT_DESKTOP_INTEGRATION.md"
