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
    run_parser = subparsers.add_parser(
        "run",
        help="Start the MCP server",
    )
    run_parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol: 'stdio' (default, used by MCP hosts) or 'sse' (HTTP, for running the server yourself)",
    )
    run_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (SSE only, default: 127.0.0.1)",
    )
    run_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to listen on (SSE only, default: 8765)",
    )

    return parser.parse_args(args)


def cmd_doctor() -> int:
    """Validate Zotero setup, database access, and plugin connection.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    import logging

    from zotero2ai.config import resolve_zotero_mcp_token
    from zotero2ai.zotero.plugin_client import PluginClient

    logger = logging.getLogger("zotero2ai.cli")

    try:
        # Resolve Zotero data directory (Heritage check)
        logger.info("Resolving Zotero data directory...")
        zotero_dir = resolve_zotero_data_dir()
        logger.info(f"✓ Found Zotero data directory: {zotero_dir}")

        # Verify database exists
        db_path = zotero_dir / "zotero.sqlite"
        if not db_path.exists():
            logger.error(f"✗ Database not found: {db_path}")
            return 1
        logger.info(f"✓ Database found: {db_path}")

        # Test read-only database connection
        logger.info("Testing database connection...")
        db_uri = f"file:{db_path}?mode=ro"
        try:
            conn = sqlite3.connect(db_uri, uri=True, timeout=2.0)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM items")
                item_count = cursor.fetchone()[0]
                logger.info(f"✓ Database connection successful: {item_count} items found")
            finally:
                conn.close()
        except sqlite3.OperationalError as e:
            # Zotero can keep the DB busy/locked while running; this should not prevent plugin connectivity checks.
            if "database is locked" in str(e).lower():
                logger.warning("⚠️  Database is locked (Zotero may be actively writing). Skipping DB query and continuing.")
            else:
                raise

        # Check Plugin Connection (New Requirement)
        logger.info("Checking Zotero Bridge Plugin connection...")
        token = resolve_zotero_mcp_token()
        if not token:
            logger.error("✗ ZOTERO_MCP_TOKEN not found in environment")
            return 1
        logger.info("✓ ZOTERO_MCP_TOKEN found")

        try:
            with PluginClient(auth_token=token) as client:
                health = client.health_check()
                logger.info(f"✓ Successfully connected to Zotero Plugin (v{health.get('version', 'unknown')})")
        except Exception as e:
            logger.error(f"✗ Failed to connect to Zotero Plugin: {e}")
            logger.error("  Ensure Zotero is running and the Bridge Plugin is installed.")
            return 1

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


def cmd_run(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8765) -> int:
    """Start the MCP server.

    Args:
        transport: 'stdio' (default) or 'sse' for HTTP-based SSE transport.
        host: Hostname/IP to bind to when using SSE transport.
        port: Port to listen on when using SSE transport.

    Returns:
        Exit code: 0 on success, 1 on failure.
    """
    import logging

    logger = logging.getLogger("zotero2ai.cli")

    try:
        # Import and create the real MCP server
        import os
        from zotero2ai.mcp_server.server import create_mcp_server
        
        watch_dir = os.environ.get("ZOTERO2AI_QUEUE_WATCH_DIR")
        if watch_dir:
            from zotero2ai.queue.worker import start_queue_worker_in_background
            logger.info(f"Starting async queue worker thread on {watch_dir}...")
            # Assigning to a variable prevents the observer from being garbage collected
            # if we wanted to gracefully shutdown, but for daemon thread it's okay.
            _queue_observer = start_queue_worker_in_background(watch_dir)

        mcp = create_mcp_server()

        if transport == "sse":
            logger.info(f"Starting MCP server (SSE) on http://{host}:{port}/sse ...")
            logger.info("Add to your MCP config:")
            logger.info(f'  {{ "type": "sse", "url": "http://{host}:{port}/sse" }}')
            mcp.run(transport="sse", host=host, port=port)
        else:
            logger.info("Starting MCP server (stdio)...")
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
        return cmd_run(
            transport=getattr(args, "transport", "stdio"),
            host=getattr(args, "host", "127.0.0.1"),
            port=getattr(args, "port", 8765),
        )
    else:
        # No command specified, show help
        parse_args(["--help"])
        return 1


if __name__ == "__main__":
    sys.exit(main())
