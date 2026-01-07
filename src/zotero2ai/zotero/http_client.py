"""HTTP client for Zotero MCP Bridge plugin."""

import logging
import os
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class PluginAuthError(Exception):
    """Raised when plugin authentication fails."""

    pass


class PluginConnectionError(Exception):
    """Raised when connection to the plugin fails."""

    pass


class ZoteroHTTPClient:
    """HTTP client for Zotero MCP Bridge plugin.

    Communicates with the plugin's HTTP server using Bearer token authentication.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:23119",
        token: str | None = None,
        timeout: float = 10.0,
        auth_token: str | None = None,  # Alias for backward compatibility
    ):
        """Initialize the plugin client."""
        self.base_url = base_url.rstrip("/")
        self.auth_token = token or auth_token or os.getenv("ZOTERO_MCP_TOKEN")
        self.timeout = timeout
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        """Get or create the httpx client."""
        if self._client is None:
            headers = {}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
            )
        return self._client

    def set_auth_token(self, token: str) -> None:
        """Set the authentication token."""
        self.auth_token = token
        if self._client is not None:
            self._client.close()
            self._client = None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "ZoteroHTTPClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an authenticated request to the plugin."""
        if not self.auth_token:
            raise PluginAuthError("No authentication token configured. Set ZOTERO_MCP_TOKEN environment variable.")

        try:
            response = self.client.request(method, path, **kwargs)

            if response.status_code == 401:
                raise PluginAuthError("Authentication failed. Check that ZOTERO_MCP_TOKEN matches the plugin's token.")

            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        except httpx.ConnectError as e:
            raise PluginConnectionError(f"Failed to connect to plugin at {self.base_url}. Ensure the Zotero MCP Bridge plugin is installed and Zotero is running.") from e
        except httpx.TimeoutException as e:
            raise PluginConnectionError(f"Request to plugin timed out after {self.timeout}s") from e

    # Health check
    def health_check(self) -> dict[str, Any]:
        """Check plugin health status."""
        return self._request("GET", "/health")

    # Collections
    def list_collections(self) -> list[dict[str, Any]]:
        """List all Zotero collections."""
        response = self._request("GET", "/collections")
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_collections(self) -> list[dict[str, Any]]:
        """Alias for list_collections."""
        return self.list_collections()

    # Items
    def search_items(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for items by title."""
        # Clean query: sometimes we get Markdown links or brackets
        clean_query = str(query).strip("[]")
        response = self._request("GET", "/items/search", params={"q": clean_query, "limit": limit})
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_recent_items(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recently added items."""
        response = self._request("GET", "/items/recent", params={"limit": limit})
        return cast(list[dict[str, Any]], response.get("data", []))

    # Notes
    def list_notes(
        self,
        collection_key: str | None = None,
        parent_item_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """List notes with optional filtering."""
        if not collection_key and not parent_item_key:
            raise ValueError("Must provide either collection_key or parent_item_key")

        params = {}
        if collection_key:
            params["collectionKey"] = collection_key
        if parent_item_key:
            params["parentItemKey"] = parent_item_key

        response = self._request("GET", "/notes", params=params)
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_notes(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Alias for list_notes."""
        return self.list_notes(*args, **kwargs)

    def get_note(self, key: str) -> dict[str, Any]:
        """Get full note content by key."""
        response = self._request("GET", f"/notes/{key}")
        return cast(dict[str, Any], response.get("data", {}))

    def create_note(
        self,
        note: str | None = None,
        tags: list[str] | None = None,
        collections: list[str] | None = None,
        parent_item_key: str | None = None,
        content: str | None = None,  # Compatibility alias
    ) -> dict[str, Any]:
        """Create a new note."""
        actual_note = note or content
        if actual_note is None:
            raise ValueError("Note content is required")

        body: dict[str, Any] = {"note": actual_note}
        if tags is not None:
            body["tags"] = tags
        if collections is not None:
            body["collections"] = collections
        if parent_item_key is not None:
            body["parentItemKey"] = parent_item_key

        response = self._request("POST", "/notes", json=body)
        return cast(dict[str, Any], response.get("data", {}))

    def update_note(
        self,
        key: str,
        note: str | None = None,
        tags: list[str] | None = None,
        collections: list[str] | None = None,
        parent_item_key: str | None = None,
        content: str | None = None,  # Compatibility alias
    ) -> dict[str, Any]:
        """Update an existing note."""
        actual_note = note or content
        body: dict[str, Any] = {}
        if actual_note is not None:
            body["note"] = actual_note
        if tags is not None:
            body["tags"] = tags
        if collections is not None:
            body["collections"] = collections
        if parent_item_key is not None:
            body["parentItemKey"] = parent_item_key

        response = self._request("PUT", f"/notes/{key}", json=body)
        return cast(dict[str, Any], response.get("data", {}))

    def extend_note(self, key: str, additional_content: str) -> dict[str, Any]:
        """Extend an existing note."""
        current_note = self.get_note(key)
        current_content = current_note.get("note", "")
        new_content = current_content + "\n" + additional_content
        return self.update_note(key, note=new_content)


PluginClient = ZoteroHTTPClient
