"""Tests for the config module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from zotero2ai.config import (
    ZoteroDataDirNotFoundError,
    resolve_zotero_data_dir,
    validate_zotero_data_dir,
)


class TestValidateZoteroDataDir:
    """Tests for validate_zotero_data_dir function."""

    def test_valid_directory(self, tmp_path: Path) -> None:
        """Test that a valid directory passes validation."""
        # Create a valid Zotero data directory
        (tmp_path / "zotero.sqlite").touch()
        (tmp_path / "storage").mkdir()

        # Should not raise
        validate_zotero_data_dir(tmp_path)

    def test_missing_sqlite(self, tmp_path: Path) -> None:
        """Test that missing zotero.sqlite raises an error."""
        # Create storage but not sqlite
        (tmp_path / "storage").mkdir()

        with pytest.raises(ZoteroDataDirNotFoundError) as exc_info:
            validate_zotero_data_dir(tmp_path)

        assert "zotero.sqlite" in str(exc_info.value)
        assert "ZOTERO_DATA_DIR" in str(exc_info.value)

    def test_missing_storage(self, tmp_path: Path) -> None:
        """Test that missing storage/ directory raises an error."""
        # Create sqlite but not storage
        (tmp_path / "zotero.sqlite").touch()

        with pytest.raises(ZoteroDataDirNotFoundError) as exc_info:
            validate_zotero_data_dir(tmp_path)

        assert "storage" in str(exc_info.value)
        assert "ZOTERO_DATA_DIR" in str(exc_info.value)

    def test_storage_is_file_not_directory(self, tmp_path: Path) -> None:
        """Test that storage being a file (not directory) raises an error."""
        # Create sqlite and storage as a file
        (tmp_path / "zotero.sqlite").touch()
        (tmp_path / "storage").touch()  # File, not directory

        with pytest.raises(ZoteroDataDirNotFoundError) as exc_info:
            validate_zotero_data_dir(tmp_path)

        assert "storage" in str(exc_info.value)


class TestResolveZoteroDataDir:
    """Tests for resolve_zotero_data_dir function."""

    def test_env_var_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ZOTERO_DATA_DIR environment variable takes precedence."""
        # Create a valid directory
        zotero_dir = tmp_path / "custom_zotero"
        zotero_dir.mkdir()
        (zotero_dir / "zotero.sqlite").touch()
        (zotero_dir / "storage").mkdir()

        # Set environment variable
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(zotero_dir))

        result = resolve_zotero_data_dir()
        assert result == zotero_dir.resolve()

    def test_env_var_with_tilde_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ~ in ZOTERO_DATA_DIR is expanded."""
        # Create a valid directory in home
        home = Path.home()
        zotero_dir = home / ".test_zotero_temp"
        zotero_dir.mkdir(exist_ok=True)
        (zotero_dir / "zotero.sqlite").touch()
        (zotero_dir / "storage").mkdir(exist_ok=True)

        try:
            # Set environment variable with tilde
            monkeypatch.setenv("ZOTERO_DATA_DIR", "~/.test_zotero_temp")

            result = resolve_zotero_data_dir()
            assert result == zotero_dir.resolve()
        finally:
            # Cleanup
            import shutil

            if zotero_dir.exists():
                shutil.rmtree(zotero_dir)

    def test_fallback_to_home_zotero_capital(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fallback to ~/Zotero when env var is not set."""
        # Unset environment variable
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)

        # Mock Path.home() to return tmp_path
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            # Create ~/Zotero
            zotero_dir = tmp_path / "Zotero"
            zotero_dir.mkdir()
            (zotero_dir / "zotero.sqlite").touch()
            (zotero_dir / "storage").mkdir()

            result = resolve_zotero_data_dir()
            assert result == zotero_dir

    def test_fallback_to_home_zotero_lowercase(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test fallback to ~/zotero when ~/Zotero doesn't exist."""
        # Unset environment variable
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)

        # Mock Path.home() to return tmp_path
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            # Create ~/zotero (lowercase) - on case-insensitive filesystems this may create Zotero
            zotero_dir = tmp_path / "zotero"
            zotero_dir.mkdir()
            (zotero_dir / "zotero.sqlite").touch()
            (zotero_dir / "storage").mkdir()

            result = resolve_zotero_data_dir()
            # On case-insensitive filesystems, both paths resolve to the same directory
            # Compare case-insensitively
            assert result.resolve().as_posix().lower() == zotero_dir.resolve().as_posix().lower()

    def test_capital_zotero_takes_precedence_over_lowercase(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that ~/Zotero takes precedence over ~/zotero on case-sensitive filesystems."""
        # Unset environment variable
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)

        # Mock Path.home() to return tmp_path
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            # Create ~/Zotero first
            zotero_capital = tmp_path / "Zotero"
            zotero_capital.mkdir()
            (zotero_capital / "zotero.sqlite").touch()
            (zotero_capital / "storage").mkdir()

            # On case-insensitive filesystems (macOS default), ~/zotero is the same as ~/Zotero
            # On case-sensitive filesystems, we'd create a second directory
            zotero_lower = tmp_path / "zotero"
            if not zotero_lower.exists():
                zotero_lower.mkdir()
                (zotero_lower / "zotero.sqlite").touch()
                (zotero_lower / "storage").mkdir()

            result = resolve_zotero_data_dir()
            # Should prefer capital Z (or on case-insensitive FS, they're the same)
            assert result.resolve() == zotero_capital.resolve()

    def test_no_valid_directory_raises_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that an error is raised when no valid directory is found."""
        # Unset environment variable
        monkeypatch.delenv("ZOTERO_DATA_DIR", raising=False)

        # Mock Path.home() to return tmp_path with no Zotero directories
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            with pytest.raises(ZoteroDataDirNotFoundError) as exc_info:
                resolve_zotero_data_dir()

            error_msg = str(exc_info.value)
            assert "Could not find a valid Zotero data directory" in error_msg
            assert "ZOTERO_DATA_DIR" in error_msg
            assert "Searched locations:" in error_msg

    def test_invalid_env_var_falls_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid ZOTERO_DATA_DIR falls back to default locations."""
        # Set invalid environment variable
        invalid_dir = tmp_path / "invalid"
        invalid_dir.mkdir()
        # Don't create required files
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(invalid_dir))

        # Mock Path.home() to return tmp_path
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            # Create valid ~/Zotero
            zotero_dir = tmp_path / "Zotero"
            zotero_dir.mkdir()
            (zotero_dir / "zotero.sqlite").touch()
            (zotero_dir / "storage").mkdir()

            result = resolve_zotero_data_dir()
            # Should fall back to ~/Zotero
            assert result == zotero_dir

    def test_nonexistent_env_var_path_falls_back(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that non-existent ZOTERO_DATA_DIR path falls back to default locations."""
        # Set environment variable to non-existent path
        monkeypatch.setenv("ZOTERO_DATA_DIR", str(tmp_path / "does_not_exist"))

        # Mock Path.home() to return tmp_path
        with patch("zotero2ai.config.Path.home", return_value=tmp_path):
            # Create valid ~/zotero
            zotero_dir = tmp_path / "zotero"
            zotero_dir.mkdir()
            (zotero_dir / "zotero.sqlite").touch()
            (zotero_dir / "storage").mkdir()

            result = resolve_zotero_data_dir()
            # Should fall back to ~/zotero (or ~/Zotero on case-insensitive FS)
            # Compare case-insensitively
            assert result.resolve().as_posix().lower() == zotero_dir.resolve().as_posix().lower()
