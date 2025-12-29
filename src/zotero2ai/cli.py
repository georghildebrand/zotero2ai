"""CLI entry point for zotero2ai MCP server."""

import argparse
import sqlite3
import sys

from zotero2ai.config import resolve_zotero_data_dir
from zotero2ai.logging import setup_logging


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: List of arguments to parse. If None, uses sys.argv[1:].

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="mcp-zotero2ai",
        description="MCP server for Zotero integration with local vector search",
    )

    # Global flags
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )

    # Subcommands
    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
        required=True,
    )

    # doctor command
    subparsers.add_parser(
        "doctor",
        help="Validate Zotero configuration and database access",
    )

    # run command
    subparsers.add_parser(
        "run",
        help="Start the MCP server",
    )

    return parser.parse_args(args)


def cmd_doctor() -> int:
    """Validate Zotero setup and database access.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    import logging

    logger = logging.getLogger("zotero2ai.cli")

    try:
        # Resolve Zotero data directory
        logger.info("Resolving Zotero data directory...")
        zotero_dir = resolve_zotero_data_dir()
        logger.info(f"✓ Found Zotero data directory: {zotero_dir}")

        # Verify database exists
        db_path = zotero_dir / "zotero.sqlite"
        if not db_path.exists():
            logger.error(f"✗ Database not found: {db_path}")
            return 1
        logger.info(f"✓ Database found: {db_path}")

        # Verify storage directory exists
        storage_path = zotero_dir / "storage"
        if not storage_path.exists():
            logger.error(f"✗ Storage directory not found: {storage_path}")
            return 1
        logger.info(f"✓ Storage directory found: {storage_path}")

        # Test read-only database connection
        logger.info("Testing database connection...")
        db_uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)

        try:
            cursor = conn.cursor()
            # Run a simple sanity query
            cursor.execute("SELECT COUNT(*) FROM items")
            item_count = cursor.fetchone()[0]
            logger.info(f"✓ Database connection successful: {item_count} items found")

            # Check for collections table
            cursor.execute("SELECT COUNT(*) FROM collections")
            collection_count = cursor.fetchone()[0]
            logger.info(f"✓ Collections table accessible: {collection_count} collections found")

        finally:
            conn.close()

        logger.info("✓ All checks passed!")
        return 0

    except FileNotFoundError as e:
        logger.error(f"✗ Configuration error: {e}")
        return 1
    except sqlite3.Error as e:
        logger.error(f"✗ Database error: {e}")
        return 1
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
        return 1


def cmd_run() -> int:
    """Start the MCP server.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    import logging

    logger = logging.getLogger("zotero2ai.cli")

    try:
        # Import and create the real MCP server
        from zotero2ai.mcp_server.server import create_mcp_server

        mcp = create_mcp_server()

        logger.info("Starting MCP server...")

        # Start the server with stdio transport for ChatGPT Desktop integration
        mcp.run(transport="stdio")

        return 0

    except ImportError as e:
        logger.error(f"✗ MCP dependency error: {e}")
        logger.error("Please ensure 'mcp[cli]' is installed")
        return 1
    except Exception as e:
        logger.error(f"✗ Server initialization error: {e}")
        return 1


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    args = parse_args()

    # Setup logging based on flags
    setup_logging(debug=args.debug, quiet=args.quiet)

    # Route to appropriate command
    if args.command == "doctor":
        return cmd_doctor()
    elif args.command == "run":
        return cmd_run()
    else:
        # No command specified, show help
        parse_args(["--help"])
        return 1


if __name__ == "__main__":
    sys.exit(main())
