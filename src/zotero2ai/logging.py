"""Logging configuration for zotero2ai.

This module provides centralized logging setup that configures the root logger
to ensure all child loggers (e.g., zotero2ai.cli, zotero2ai.config) properly
propagate and emit log messages to stderr.
"""

import logging
import sys


def setup_logging(debug: bool = False, quiet: bool = False) -> None:
    """Configure logging for the zotero2ai application.

    This function configures the root logger to ensure all child loggers
    properly propagate and emit messages. Logging output is sent to stderr.

    Args:
        debug: If True, set log level to DEBUG. Otherwise INFO.
        quiet: If True, set log level to WARNING (overrides debug).

    Examples:
        >>> setup_logging()  # INFO level to stderr
        >>> setup_logging(debug=True)  # DEBUG level to stderr
        >>> setup_logging(quiet=True)  # WARNING level to stderr
    """
    # Determine log level based on flags
    if quiet:
        level = logging.WARNING
    elif debug:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Configure root logger with force=True to override any existing config
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stderr)],
        format="[%(levelname)s] %(message)s",
        force=True,
    )

    # Optionally set the zotero2ai logger level explicitly
    # (This is redundant if root is already configured, but makes intent clear)
    logging.getLogger("zotero2ai").setLevel(level)
