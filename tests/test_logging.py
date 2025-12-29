"""Tests for zotero2ai.logging module."""

import logging
import sys
from typing import Any

from zotero2ai.logging import setup_logging


class TestSetupLogging:
    """Test suite for setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up logging configuration after each test."""
        # Reset logging to avoid test interference
        logging.root.handlers = []
        logging.root.setLevel(logging.WARNING)

    def test_default_logging_level_is_info(self, capfd: Any) -> None:
        """Test that default logging level is INFO."""
        setup_logging()

        logger = logging.getLogger("zotero2ai")
        logger.info("info message")
        logger.debug("debug message")

        captured = capfd.readouterr()
        assert "[INFO] info message" in captured.err
        assert "debug message" not in captured.err

    def test_debug_flag_enables_debug_level(self, capfd: Any) -> None:
        """Test that debug=True sets log level to DEBUG."""
        setup_logging(debug=True)

        logger = logging.getLogger("zotero2ai")
        logger.debug("debug message")
        logger.info("info message")

        captured = capfd.readouterr()
        assert "[DEBUG] debug message" in captured.err
        assert "[INFO] info message" in captured.err

    def test_quiet_flag_enables_warning_level(self, capfd: Any) -> None:
        """Test that quiet=True sets log level to WARNING."""
        setup_logging(quiet=True)

        logger = logging.getLogger("zotero2ai")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")

        captured = capfd.readouterr()
        assert "info message" not in captured.err
        assert "[WARNING] warning message" in captured.err
        assert "[ERROR] error message" in captured.err

    def test_quiet_overrides_debug(self, capfd: Any) -> None:
        """Test that quiet=True takes precedence over debug=True."""
        setup_logging(debug=True, quiet=True)

        logger = logging.getLogger("zotero2ai")
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")

        captured = capfd.readouterr()
        assert "debug message" not in captured.err
        assert "info message" not in captured.err
        assert "[WARNING] warning message" in captured.err

    def test_child_logger_propagates(self, capfd: Any) -> None:
        """Test that child loggers (e.g., zotero2ai.cli) propagate messages."""
        setup_logging()

        # Create a child logger
        child_logger = logging.getLogger("zotero2ai.cli")
        child_logger.info("child info message")

        captured = capfd.readouterr()
        assert "[INFO] child info message" in captured.err

    def test_nested_child_logger_propagates(self, capfd: Any) -> None:
        """Test that deeply nested child loggers propagate messages."""
        setup_logging()

        # Create a deeply nested child logger
        nested_logger = logging.getLogger("zotero2ai.zotero.db")
        nested_logger.info("nested info message")

        captured = capfd.readouterr()
        assert "[INFO] nested info message" in captured.err

    def test_output_goes_to_stderr(self, capfd: Any) -> None:
        """Test that log output goes to stderr, not stdout."""
        setup_logging()

        logger = logging.getLogger("zotero2ai")
        logger.info("test message")

        captured = capfd.readouterr()
        assert "test message" in captured.err
        assert captured.out == ""

    def test_log_format_includes_level(self, capfd: Any) -> None:
        """Test that log format includes the log level."""
        setup_logging()

        logger = logging.getLogger("zotero2ai")
        logger.info("test message")
        logger.warning("warning message")
        logger.error("error message")

        captured = capfd.readouterr()
        assert "[INFO] test message" in captured.err
        assert "[WARNING] warning message" in captured.err
        assert "[ERROR] error message" in captured.err

    def test_multiple_calls_reconfigure_logging(self, capfd: Any) -> None:
        """Test that calling setup_logging multiple times reconfigures logging."""
        # First call with INFO level
        setup_logging()
        logger = logging.getLogger("zotero2ai")
        logger.debug("debug1")
        logger.info("info1")

        captured = capfd.readouterr()
        assert "debug1" not in captured.err
        assert "[INFO] info1" in captured.err

        # Second call with DEBUG level
        setup_logging(debug=True)
        logger.debug("debug2")
        logger.info("info2")

        captured = capfd.readouterr()
        assert "[DEBUG] debug2" in captured.err
        assert "[INFO] info2" in captured.err

    def test_root_logger_is_configured(self) -> None:
        """Test that the root logger is properly configured."""
        setup_logging(debug=True)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert len(root_logger.handlers) > 0
        assert any(isinstance(h, logging.StreamHandler) and h.stream == sys.stderr for h in root_logger.handlers)

    def test_zotero2ai_logger_level_matches(self) -> None:
        """Test that zotero2ai logger level matches the configured level."""
        setup_logging(debug=True)
        zotero2ai_logger = logging.getLogger("zotero2ai")
        assert zotero2ai_logger.level == logging.DEBUG

        setup_logging(quiet=True)
        assert zotero2ai_logger.level == logging.WARNING

        setup_logging()
        assert zotero2ai_logger.level == logging.INFO
