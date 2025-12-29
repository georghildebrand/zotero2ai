"""Collection Management and Active Collection state."""

import json
import logging
from pathlib import Path
from platformdirs import user_config_dir

logger = logging.getLogger(__name__)


class ActiveCollectionManager:
    """Manages the 'active' collection state for the current user."""

    def __init__(self):
        self.config_dir = Path(user_config_dir("zotero2ai"))
        self.config_file = self.config_dir / "config.json"
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def set_active_collection(self, key: str, full_path: str = "") -> None:
        """Store the active collection key."""
        config = self._load_config()
        config["active_collection_key"] = key
        if full_path:
            config["active_collection_path"] = full_path

        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
        logger.info(f"Set active collection to: {key} ({full_path})")

    def get_active_collection_key(self) -> str | None:
        """Retrieve the active collection key."""
        config = self._load_config()
        return config.get("active_collection_key")

    def get_active_collection_path(self) -> str | None:
        """Retrieve the active collection path."""
        config = self._load_config()
        return config.get("active_collection_path")

    def _load_config(self) -> dict:
        """Load config from disk."""
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {}
