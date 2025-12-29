import os
import subprocess
import sys


def test_cli_help():
    """Verify that --help returns 0 and contains expected commands."""
    result = subprocess.run(
        [sys.executable, "-m", "zotero2ai.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "doctor" in result.stdout
    assert "run" in result.stdout


def test_doctor_fail_no_config(tmp_path):
    """Verify that doctor fails with clear error when no valid Zotero dir is found."""
    # Create an empty dir for HOME to avoid picking up real ~/Zotero
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()

    # Create an empty dir for ZOTERO_DATA_DIR
    empty_dir = tmp_path / "empty_zotero"
    empty_dir.mkdir()

    # Run with custom ENV
    env = {
        **os.environ,
        "ZOTERO_DATA_DIR": str(empty_dir),
        "HOME": str(fake_home),
        "USERPROFILE": str(fake_home),  # for Windows if needed
    }

    result = subprocess.run(
        [sys.executable, "-m", "zotero2ai.cli", "doctor"],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 1
    # Check that it mentions ZOTERO_DATA_DIR
    assert "ZOTERO_DATA_DIR" in result.stderr or "ZOTERO_DATA_DIR" in result.stdout


def test_run_stub():
    """Verify that run command starts the MCP server."""
    # Note: We can't actually test the full server startup in a subprocess
    # because it would block. Instead, we just verify it starts logging correctly.
    # The actual server functionality is tested via mocking in test_cli.py
    import time

    proc = subprocess.Popen(
        [sys.executable, "-m", "zotero2ai.cli", "run"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give it a moment to start and log
    time.sleep(0.5)

    # Terminate the process
    proc.terminate()
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()

    # Verify it started logging
    assert "Starting MCP server" in stderr or "Starting MCP server" in stdout
