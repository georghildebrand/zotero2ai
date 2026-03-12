"""Configuration resolution for zotero2ai.

This module handles the resolution and validation of the Zotero data directory.
"""

import os
from pathlib import Path

import platformdirs


class ZoteroDataDirNotFoundError(FileNotFoundError):
    """Raised when the Zotero data directory cannot be found or is invalid."""

    pass


def resolve_zotero_data_dir() -> Path:
    """Resolve the Zotero data directory.

    Resolution order:
    1. ZOTERO_DATA_DIR environment variable
    2. ~/Zotero
    3. ~/zotero

    Returns:
        Path: Absolute path to the validated Zotero data directory.

    Raises:
        ZoteroDataDirNotFoundError: If no valid Zotero data directory is found.
    Raises:
        ZoteroDataDirNotFoundError: If no valid Zotero data directory is found.
    """
    # Resolution order
    candidates: list[Path] = []

    # 1. Check ZOTERO_DATA_DIR environment variable
    if env_dir := os.getenv("ZOTERO_DATA_DIR"):
        candidates.append(Path(env_dir).expanduser().resolve())

    # 2. Check ~/Zotero
    candidates.append(Path.home() / "Zotero")

    # 3. Check ~/zotero
    candidates.append(Path.home() / "zotero")

    # Try each candidate
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            # Validate the directory
            try:
                validate_zotero_data_dir(candidate)
                return candidate
            except ZoteroDataDirNotFoundError:
                # This candidate is invalid, try the next one
                continue

    # No valid directory found
    raise ZoteroDataDirNotFoundError(
        "Could not find a valid Zotero data directory. "
        "Please ensure that:\n"
        "  1. Zotero is installed and has been run at least once, OR\n"
        "  2. Set the ZOTERO_DATA_DIR environment variable to point to your Zotero data directory.\n"
        "\n"
        "Searched locations:\n" + "\n".join(f"  - {c}" for c in candidates)
    )


def resolve_zotero_api_key() -> str | None:
    """Resolve the Zotero API key from the ZOTERO_API_KEY environment variable."""
    return os.getenv("ZOTERO_API_KEY")


def resolve_zotero_user_id() -> str | None:
    """Resolve the Zotero User ID (Library ID) from the ZOTERO_USER_ID environment variable."""
    return os.getenv("ZOTERO_USER_ID")


def resolve_zotero_mcp_token() -> str | None:
    """Resolve the Zotero MCP Bridge plugin authentication token from the ZOTERO_MCP_TOKEN environment variable."""
    return os.getenv("ZOTERO_MCP_TOKEN")


def resolve_zotero_bridge_port() -> int:
    """Resolve the Zotero Bridge port from ZOTERO_BRIDGE_PORT or use default 23120."""
    port_str = os.getenv("ZOTERO_BRIDGE_PORT", "23120")
    try:
        return int(port_str)
    except ValueError:
        return 23120


def validate_zotero_data_dir(data_dir: Path) -> None:
    """Validate that a directory is a valid Zotero data directory.

    Args:
        data_dir: Path to the directory to validate.

    Raises:
        ZoteroDataDirNotFoundError: If the directory is missing required files/folders.
    """
    # Check for zotero.sqlite
    sqlite_path = data_dir / "zotero.sqlite"
    if not sqlite_path.exists():
        raise ZoteroDataDirNotFoundError(
            f"Invalid Zotero data directory: {data_dir}\nMissing required file: zotero.sqlite\nPlease set ZOTERO_DATA_DIR to a valid Zotero data directory."
        )

    # Check for storage/ directory
    storage_path = data_dir / "storage"
    if not storage_path.exists() or not storage_path.is_dir():
        raise ZoteroDataDirNotFoundError(
            f"Invalid Zotero data directory: {data_dir}\nMissing required directory: storage/\nPlease set ZOTERO_DATA_DIR to a valid Zotero data directory."
        )


def resolve_sidecar_dir() -> Path:
    """Resolve the directory for the sidecar memory index state.

    Uses platformdirs to find a suitable user data directory.
    """
    app_dir = Path(platformdirs.user_data_dir("zotero2ai"))
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def resolve_sidecar_db_path() -> Path:
    """Resolve the path to the sidecar SQLite database."""
    return resolve_sidecar_dir() / "catalog.sqlite"
