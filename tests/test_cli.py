"""Tests for CLI module."""

import sqlite3
import sys
from unittest.mock import MagicMock, patch

import pytest

from zotero2ai.cli import cmd_doctor, cmd_run, main, parse_args


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_args_doctor(self):
        """Test parsing doctor command."""
        args = parse_args(["doctor"])
        assert args.command == "doctor"
        assert args.debug is False
        assert args.quiet is False

    def test_parse_args_run(self):
        """Test parsing run command."""
        args = parse_args(["run"])
        assert args.command == "run"
        assert args.debug is False
        assert args.quiet is False

    def test_parse_args_with_debug(self):
        """Test parsing with --debug flag."""
        args = parse_args(["--debug", "doctor"])
        assert args.command == "doctor"
        assert args.debug is True
        assert args.quiet is False

    def test_parse_args_with_quiet(self):
        """Test parsing with --quiet flag."""
        args = parse_args(["--quiet", "run"])
        assert args.command == "run"
        assert args.debug is False
        assert args.quiet is True

    def test_parse_args_both_flags(self):
        """Test parsing with both --debug and --quiet flags."""
        args = parse_args(["--debug", "--quiet", "doctor"])
        assert args.command == "doctor"
        assert args.debug is True
        assert args.quiet is True

    def test_parse_args_no_command(self):
        """Test parsing with no command shows help and exits."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args([])
        # Should exit with error code 2 (argparse error)
        assert exc_info.value.code == 2

    def test_parse_args_help(self):
        """Test parsing --help flag."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0


class TestCmdDoctor:
    """Tests for doctor command."""

    def test_doctor_success(self, tmp_path, monkeypatch):
        """Test doctor command with valid Zotero setup."""
        # Create mock Zotero directory structure
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        # Create a minimal SQLite database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE collections (collectionID INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO items (itemID) VALUES (1), (2), (3)")
        conn.execute("INSERT INTO collections (collectionID) VALUES (1)")
        conn.commit()
        conn.close()

        # Mock resolve_zotero_data_dir to return our test directory
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))
        monkeypatch.setenv("ZOTERO_MCP_TOKEN", "test-token")

        import respx
        from httpx import Response

        with respx.mock(base_url="http://127.0.0.1:23119") as respx_mock:
            respx_mock.get("/health").mock(return_value=Response(200, json={"status": "ok", "version": "0.1.0"}))
            # Run doctor command
            exit_code = cmd_doctor()
            assert exit_code == 0

    def test_doctor_missing_directory(self, monkeypatch):
        """Test doctor command with missing Zotero directory."""
        # Remove ZOTERO_DATA_DIR and HOME to prevent fallback
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", "/nonexistent/home")

        # Run doctor command
        exit_code = cmd_doctor()
        assert exit_code == 1

    def test_doctor_missing_database(self, tmp_path, monkeypatch):
        """Test doctor command with missing database file."""
        # Create Zotero directory without database
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        # Ensure no fallback to real Zotero
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        # Explicitly set to our test directory
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))

        # Run doctor command
        exit_code = cmd_doctor()
        assert exit_code == 1

    def test_doctor_missing_storage(self, tmp_path, monkeypatch):
        """Test doctor command with missing storage directory."""
        # Create Zotero directory with database but no storage
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"

        # Create a minimal SQLite database
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        # Ensure no fallback to real Zotero
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        # Explicitly set to our test directory
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))

        # Run doctor command
        exit_code = cmd_doctor()
        assert exit_code == 1

    def test_doctor_corrupted_database(self, tmp_path, monkeypatch):
        """Test doctor command with corrupted database."""
        # Create Zotero directory with invalid database
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        # Create an invalid database file
        db_path.write_text("This is not a valid SQLite database")

        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))

        # Run doctor command
        exit_code = cmd_doctor()
        assert exit_code == 1

    def test_doctor_missing_tables(self, tmp_path, monkeypatch):
        """Test doctor command with database missing required tables."""
        # Create Zotero directory with database missing tables
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        # Create a database without required tables
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE dummy (id INTEGER)")
        conn.commit()
        conn.close()

        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))

        # Run doctor command
        exit_code = cmd_doctor()
        assert exit_code == 1


class TestCmdRun:
    """Tests for run command."""

    @patch("zotero2ai.mcp_server.server.create_mcp_server")
    def test_run_success(self, mock_create_server):
        """Test run command initializes MCP server."""
        mock_instance = MagicMock()
        mock_create_server.return_value = mock_instance

        exit_code = cmd_run()
        assert exit_code == 0
        mock_instance.run.assert_called_once_with(transport="stdio")

    @patch("zotero2ai.mcp_server.server.create_mcp_server")
    def test_run_mcp_initialization(self, mock_create_server):
        """Test run command initializes FastMCP correctly."""
        mock_instance = MagicMock()
        mock_create_server.return_value = mock_instance

        exit_code = cmd_run()

        # Verify create_mcp_server was called
        mock_create_server.assert_called_once()
        mock_instance.run.assert_called_once_with(transport="stdio")
        assert exit_code == 0

    @patch("zotero2ai.mcp_server.server.create_mcp_server", side_effect=ImportError("mcp not found"))
    def test_run_missing_mcp_dependency(self, mock_create_server):
        """Test run command handles missing MCP dependency."""
        exit_code = cmd_run()
        assert exit_code == 1


class TestMain:
    """Tests for main entry point."""

    def test_main_doctor(self, tmp_path, monkeypatch):
        """Test main with doctor command."""
        # Create valid Zotero setup
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE collections (collectionID INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))
        monkeypatch.setenv("ZOTERO_MCP_TOKEN", "test-token")
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai", "doctor"])

        import respx
        from httpx import Response

        with respx.mock(base_url="http://127.0.0.1:23119") as respx_mock:
            respx_mock.get("/health").mock(return_value=Response(200, json={"status": "ok", "version": "0.1.0"}))
            exit_code = main()
            assert exit_code == 0

    @patch("zotero2ai.mcp_server.server.create_mcp_server")
    def test_main_run(self, mock_create_server, monkeypatch):
        """Test main with run command."""
        mock_instance = MagicMock()
        mock_create_server.return_value = mock_instance
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai", "run"])

        exit_code = main()
        assert exit_code == 0

    def test_main_with_debug_flag(self, tmp_path, monkeypatch):
        """Test main with --debug flag."""
        # Create valid Zotero setup
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE collections (collectionID INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))
        monkeypatch.setenv("ZOTERO_MCP_TOKEN", "test-token")
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai", "--debug", "doctor"])

        import respx
        from httpx import Response

        with respx.mock(base_url="http://127.0.0.1:23119") as respx_mock:
            respx_mock.get("/health").mock(return_value=Response(200, json={"status": "ok", "version": "0.1.0"}))
            exit_code = main()
            assert exit_code == 0

    @patch("zotero2ai.mcp_server.server.create_mcp_server")
    def test_main_with_quiet_flag(self, mock_create_server, monkeypatch):
        """Test main with --quiet flag."""
        mock_instance = MagicMock()
        mock_create_server.return_value = mock_instance
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai", "--quiet", "run"])

        exit_code = main()
        assert exit_code == 0

    def test_main_no_command(self, monkeypatch):
        """Test main with no command shows help."""
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai"])

        with pytest.raises(SystemExit):
            main()

    def test_main_invalid_command(self, monkeypatch):
        """Test main with invalid command."""
        monkeypatch.setattr(sys, "argv", ["mcp-zotero2ai", "invalid"])

        with pytest.raises(SystemExit):
            main()


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_help_output(self, capsys):
        """Test --help output contains expected information."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])

        captured = capsys.readouterr()
        assert "mcp-zotero2ai" in captured.out
        assert "doctor" in captured.out
        assert "run" in captured.out
        assert "--debug" in captured.out
        assert "--quiet" in captured.out
        assert exc_info.value.code == 0

    def test_doctor_output_success(self, tmp_path, monkeypatch):
        """Test doctor command succeeds with valid setup."""
        # Create valid Zotero setup
        zotero_dir = tmp_path / "Zotero"
        zotero_dir.mkdir()
        db_path = zotero_dir / "zotero.sqlite"
        storage_path = zotero_dir / "storage"
        storage_path.mkdir()

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE items (itemID INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE collections (collectionID INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO items (itemID) VALUES (1), (2)")
        conn.commit()
        conn.close()

        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))
        monkeypatch.setenv("ZOTERO_MCP_TOKEN", "test-token")

        import respx
        from httpx import Response

        with respx.mock(base_url="http://127.0.0.1:23119") as respx_mock:
            respx_mock.get("/health").mock(return_value=Response(200, json={"status": "ok", "version": "0.1.0"}))
            exit_code = cmd_doctor()
            assert exit_code == 0

    def test_doctor_output_failure(self, monkeypatch):
        """Test doctor command fails with invalid setup."""
        # Remove ZOTERO_DATA_DIR and HOME to prevent fallback
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)
        monkeypatch.setenv("HOME", "/nonexistent/home")

        exit_code = cmd_doctor()
        assert exit_code == 1
