"""HTTP client for communicating with the Zotero MCP Bridge plugin.

This module provides a client for making authenticated requests to the
Zotero plugin's HTTP server running on localhost.
"""

import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)


class PluginAuthError(Exception):
    """Raised when plugin authentication fails."""

    pass


class PluginConnectionError(Exception):
    """Raised when connection to the plugin fails."""

    pass


class PluginClient:
    """HTTP client for the Zotero MCP Bridge plugin.

    Communicates with the plugin's HTTP server using Bearer token authentication.
    The plugin must be running and the auth token must be configured.
    """

    def __init__(self, base_url: str | None = None, auth_token: str | None = None, timeout: float = 10.0):
        """Initialize the plugin client.

        Args:
            base_url: Base URL of the plugin HTTP server. If None, uses ZOTERO_BRIDGE_PORT or 23120.
            auth_token: Bearer token for authentication. If None, must be set via set_auth_token().
            timeout: Request timeout in seconds (default: 10.0)
        """
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            import os

            port = os.getenv("ZOTERO_BRIDGE_PORT", "23120")
            self.base_url = f"http://127.0.0.1:{port}"

        self.auth_token = auth_token
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
        """Set the authentication token.

        Args:
            token: Bearer token for authentication
        """
        self.auth_token = token
        # Reset client to pick up new token
        if self._client is not None:
            self._client.close()
            self._client = None

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "PluginClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Make an authenticated request to the plugin.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            path: Request path (e.g., "/collections")
            **kwargs: Additional arguments to pass to httpx.request()

        Returns:
            Response JSON data

        Raises:
            PluginAuthError: If authentication fails (401)
            PluginConnectionError: If connection to plugin fails
            httpx.HTTPStatusError: For other HTTP errors
        """
        if not self.auth_token:
            raise PluginAuthError("No authentication token configured. Set ZOTERO_MCP_TOKEN environment variable.")

        try:
            response = self.client.request(method, path, **kwargs)

            # Handle authentication errors
            if response.status_code == 401:
                raise PluginAuthError("Authentication failed. Check that ZOTERO_MCP_TOKEN matches the plugin's token.")

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse JSON response
            return cast(dict[str, Any], response.json())

        except httpx.ConnectError as e:
            raise PluginConnectionError(f"Failed to connect to plugin at {self.base_url}. Ensure the Zotero MCP Bridge plugin is installed and Zotero is running.") from e
        except httpx.TimeoutException as e:
            raise PluginConnectionError(f"Request to plugin timed out after {self.timeout}s") from e

    def health_check(self) -> dict[str, Any]:
        """Check plugin health status.

        Returns:
            Health check response with status, version, and timestamp
        """
        return self._request("GET", "/health")

    def get_collections(self, parent_key: str | None = None, limit: int = 100, start: int = 0, sort: str = "title", library_id: int | None = None) -> list[dict[str, Any]]:
        """Get Zotero collections.

        Args:
            parent_key: Optional key to filter by. Use 'root' for top-level collections.
            limit: Maximum number of collections to return.
            start: Starting offset for pagination.
            sort: Sort field ('title', 'dateAdded').
            library_id: Optional library ID to filter by.

        Returns:
            List of collection objects with keys, names, and paths
        """
        params = {"limit": limit, "start": start, "sort": sort}
        if parent_key:
            params["parentKey"] = parent_key
        if library_id:
            params["libraryID"] = library_id

        response = self._request("GET", "/collections", params=params)
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_collections_paginated(self, parent_key: str | None = None, limit: int = 100, start: int = 0, sort: str = "title", library_id: int | None = None) -> dict[str, Any]:
        """Get Zotero collections with pagination info.

        Args:
            parent_key: Optional key to filter by. Use 'root' for top-level collections.
            limit: Maximum number of collections to return.
            start: Starting offset for pagination.
            sort: Sort field ('title', 'dateAdded').
            library_id: Optional library ID to filter by.

        Returns:
            Full API response dict containing 'data', 'pagination', etc.
        """
        params = {"limit": limit, "start": start, "sort": sort}
        if parent_key:
            params["parentKey"] = parent_key
        if library_id:
            params["libraryID"] = library_id

        return self._request("GET", "/collections", params=params)

    def search_items(
        self,
        query: str | None = None,
        tag: str | list[str] | None = None,
        collection_key: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_by: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for items by title, tags, date range, or collection.

        Args:
            query: Search query string (optional)
            tag: Tag or list of tags to filter by (AND logic, optional)
            collection_key: Filter by collection key (optional)
            date_from: ISO date string, items added after this date (optional)
            date_to: ISO date string, items added before this date (optional)
            sort_by: Sort field, e.g. 'dateAdded' for chronological (optional)
            limit: Maximum number of results (default: 10)

        Returns:
            List of matching items
        """
        params: dict[str, Any] = {"limit": limit}
        if query:
            params["q"] = query
        if tag:
            if isinstance(tag, list):
                params["tag"] = ",".join(tag)
            else:
                params["tag"] = tag
        if collection_key:
            params["collectionKey"] = collection_key
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        if sort_by:
            params["sortBy"] = sort_by

        response = self._request("GET", "/items/search", params=params)
        return cast(list[dict[str, Any]], response.get("data", []))

    def search_collections(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search for collections by name (fuzzy).

        Args:
            query: Search query string
            limit: Maximum number of results (default: 50)

        Returns:
            List of matching collections
        """
        response = self._request("GET", "/collections/search", params={"q": query, "limit": limit})
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_recent_items(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recently added items.

        Args:
            limit: Maximum number of results (default: 5)

        Returns:
            List of recent items sorted by date added
        """
        response = self._request("GET", "/items/recent", params={"limit": limit})
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_collection_items(self, collection_key: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all items in a collection with their attachments.

        Args:
            collection_key: The key of the collection
            limit: Maximum number of items to return (default: 100, max: 500)

        Returns:
            List of items with their attachments and file paths
        """
        response = self._request("GET", f"/collections/{collection_key}/items", params={"limit": limit})
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_notes(self, collection_key: str | None = None, parent_item_key: str | None = None) -> list[dict[str, Any]]:
        """Get notes (summaries).

        Args:
            collection_key: Filter notes by collection key
            parent_item_key: Filter notes attached to a specific item

        Returns:
            List of note summaries

        Raises:
            ValueError: If neither collection_key nor parent_item_key is provided
        """
        if not collection_key and not parent_item_key:
            raise ValueError("Must provide either collection_key or parent_item_key")

        params = {}
        if collection_key:
            params["collectionKey"] = collection_key
        if parent_item_key:
            params["parentItemKey"] = parent_item_key

        response = self._request("GET", "/notes", params=params)
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_note(self, key: str) -> dict[str, Any]:
        """Get full note content by key.

        Args:
            key: Note key (e.g., "ABC123XYZ")

        Returns:
            Complete note data including HTML content and metadata

        Raises:
            httpx.HTTPStatusError: If note not found (404)
        """
        response = self._request("GET", f"/notes/{key}")
        return cast(dict[str, Any], response.get("data", {}))

    def create_note(
        self,
        content: str,
        tags: list[str] | None = None,
        collections: list[str] | None = None,
        parent_item_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a new note.

        Args:
            content: HTML content of the note
            tags: Optional list of tags
            collections: Optional list of collection keys
            parent_item_key: Optional parent item key to attach note to

        Returns:
            Created note data
        """
        body: dict[str, Any] = {"note": content}

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
        content: str | None = None,
        tags: list[str] | None = None,
        collections: list[str] | None = None,
        parent_item_key: str | None = None,
        related: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing note."""
        body: dict[str, Any] = {}

        if content is not None:
            body["note"] = content
        if tags is not None:
            body["tags"] = tags
        if collections is not None:
            body["collections"] = collections
        if parent_item_key is not None:
            body["parentItemKey"] = parent_item_key
        if related is not None:
            body["related"] = related

        response = self._request("PUT", f"/notes/{key}", json=body)
        return cast(dict[str, Any], response.get("data", {}))

    def extend_note(self, key: str, additional_content: str) -> dict[str, Any]:
        """Extend an existing note by appending content.

        Args:
            key: Note key
            additional_content: HTML content to append to the note

        Returns:
            Updated note data
        """
        # First, get the current note content
        current_note = self.get_note(key)
        current_content = current_note.get("note", "")

        # Append the new content
        new_content = current_content + "\n" + additional_content

        # Update the note
        return self.update_note(key, content=new_content)

    def get_tags(self, library_id: int | None = None) -> list[str]:
        """Get all tags in a library.

        Args:
            library_id: Library ID to get tags from (optional)

        Returns:
            List of tags
        """
        params = {}
        if library_id:
            params["libraryID"] = library_id
        response = self._request("GET", "/tags", params=params)
        return cast(list[str], response.get("data", []))

    def rename_tag(self, old_name: str, new_name: str, library_id: int | None = None) -> dict[str, Any]:
        """Rename a tag library-wide.

        Args:
            old_name: Current name of the tag
            new_name: New name for the tag
            library_id: Library ID (optional)

        Returns:
            Success status
        """
        body: dict[str, str | int] = {"oldName": old_name, "newName": new_name}
        if library_id:
            body["libraryID"] = library_id
        return self._request("POST", "/tags/rename", json=body)

    def get_item_content(self, key: str, library_id: int | None = None) -> dict[str, Any]:
        """Get the valid content (text/html) of an item or its attachment.

        Args:
            key: Item key
            library_id: Library ID (optional)

        Returns:
            Dict containing 'content', 'contentType', 'filename', etc.
        """
        params = {}
        if library_id:
            params["libraryID"] = library_id

        response = self._request("GET", f"/items/{key}/content", params=params)
        return cast(dict[str, Any], response.get("data", {}))

    def get_collection_tree(self, depth: int = 99, library_id: int | None = None) -> list[dict[str, Any]]:
        """Get the full collection tree.

        Args:
            depth: Max depth of recursion (default: 99)
            library_id: Library ID (optional)

        Returns:
            Nested list of collections and their children
        """
        params = {"depth": depth}
        if library_id:
            params["libraryID"] = library_id

        response = self._request("GET", "/collections/tree", params=params)
        return cast(list[dict[str, Any]], response.get("data", []))

    def get_item(self, key: str, library_id: int | None = None) -> dict[str, Any]:
        """Get a single item by key.

        Args:
            key: Item key
            library_id: Library ID (optional)

        Returns:
            Item data
        """
        params = {}
        if library_id:
            params["libraryID"] = library_id

        response = self._request("GET", f"/items/{key}", params=params)
        data = response.get("data", [])
        if not data:
            return {}
        return cast(dict[str, Any], data[0])

    def create_collection(self, name: str, parent_key: str | None = None, library_id: int | None = None) -> dict[str, Any]:
        """Create a new Zotero collection.

        Args:
            name: Collection name
            parent_key: Optional parent collection key
            library_id: Optional library ID (defaults to user library)

        Returns:
            Created collection data
        """
        body: dict[str, Any] = {"name": name}
        if parent_key:
            body["parentKey"] = parent_key
        if library_id:
            body["libraryID"] = library_id

        response = self._request("POST", "/collections", json=body)
        return cast(dict[str, Any], response.get("data", {}))

    def create_item(
        self,
        item_type: str,
        title: str,
        tags: list[str] | None = None,
        collections: list[str] | None = None,
        note: str | None = None,
        fields: dict[str, str] | None = None,
        library_id: int | None = None,
    ) -> dict[str, Any]:
        """Create a new Zotero item.

        Args:
            item_type: Zotero item type (e.g., 'report', 'book')
            title: Item title
            tags: Optional list of tags
            collections: Optional list of collection keys
            note: Optional HTML content for a child note
            fields: Optional dict of additional fields
            library_id: Optional library ID (defaults to user library)

        Returns:
            Created item data
        """
        body: dict[str, Any] = {"itemType": item_type, "title": title}
        if tags:
            body["tags"] = tags
        if collections:
            body["collections"] = collections
        if note:
            body["note"] = note
        if fields:
            body["fields"] = fields
        if library_id:
            body["libraryID"] = library_id

        response = self._request("POST", "/items", json=body)
        return cast(dict[str, Any], response.get("data", {}))

    def add_related(self, key: str, related_keys: list[str]) -> dict[str, Any]:
        """Add Zotero Related links between items.

        Args:
            key: Source item key
            related_keys: List of target item keys to link to

        Returns:
            Success status
        """
        body = {"relatedKeys": related_keys}
        return self._request("POST", f"/items/{key}/related", json=body)

    def update_item(
        self,
        key: str,
        title: str | None = None,
        tags: list[str] | list[dict[str, str]] | None = None,
        collections: list[str] | list[int] | None = None,
    ) -> dict[str, Any]:
        """Update an existing Zotero item via the bridge.

        Args:
            key: Item key to update
            title: New title
            tags: List of tags
            collections: List of collection keys or IDs

        Returns:
            Success status and updated key
        """
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if tags is not None:
            # handle list[str] vs list[dict]
            clean_tags = []
            for t in tags:
                if isinstance(t, dict):
                    clean_tags.append(t.get("tag", ""))
                else:
                    clean_tags.append(str(t))
            body["tags"] = clean_tags
        if collections is not None:
            body["collections"] = collections

        return self._request("PUT", f"/items/{key}", json=body)

