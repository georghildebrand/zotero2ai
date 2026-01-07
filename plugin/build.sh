#!/bin/bash
set -e

# Zum Verzeichnis wechseln, in dem dieses Skript liegt
cd "$(dirname "$0")"

# In den Quellordner des Plugins wechseln
cd zotero-mcp-bridge

echo "Baue zotero-mcp-bridge.xpi..."

# Alte XPI löschen, falls vorhanden
rm -f ../zotero-mcp-bridge.xpi

# Neue XPI erstellen (rekursiv, nur notwendige Dateien)
# Wir schließen Testskripte und versteckte Dateien aus
zip -r ../zotero-mcp-bridge.xpi \
  manifest.json \
  install.rdf \
  bootstrap.js \
  content/ \
  -x "*.DS_Store" \
  -x "*.git*" \
  -x "*.md" \
  -x "*.sh"

echo "✅ Erfolgreich erstellt: plugin/zotero-mcp-bridge.xpi"
