"""Collection Management and Active Collection state."""

import logging
from typing import Any

from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.plugin_client import PluginClient

logger = logging.getLogger(__name__)


class ActiveCollectionManager:
    """Manages the 'active' collection state stored in Zotero settings."""

    def __init__(self, client: PluginClient) -> None:
        self.client = client
        self.mm = MemoryManager(client)

    def set_active_collection(self, key: str, full_path: str = "", root_name: str = "Agent Memory") -> None:
        """Store the active collection key in Zotero settings."""
        try:
            cols = self.mm.ensure_collections(root_name=root_name)
            settings = self.mm.get_settings(cols["system"])
            
            settings["active_collection_key"] = key
            if full_path:
                settings["active_collection_path"] = full_path
                
            self.mm.update_settings(cols["system"], settings)
            logger.info(f"Set active collection to: {key} ({full_path}) in Zotero")
        except Exception as e:
            logger.error(f"Error setting active collection in Zotero: {e}")

    def get_active_collection_key(self, root_name: str = "Agent Memory") -> str | None:
        """Retrieve the active collection key from Zotero settings."""
        config = self._load_settings(root_name)
        return config.get("active_collection_key")

    def get_active_collection_path(self, root_name: str = "Agent Memory") -> str | None:
        """Retrieve the active collection path from Zotero settings."""
        config = self._load_settings(root_name)
        return config.get("active_collection_path")

    def _load_settings(self, root_name: str = "Agent Memory") -> dict[str, Any]:
        """Load settings from Zotero _System collection."""
        try:
            cols = self.mm.ensure_collections(root_name=root_name)
            return self.mm.get_settings(cols["system"])
        except Exception as e:
            logger.error(f"Error loading Zotero settings: {e}")
            return {}
