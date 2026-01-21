"""Tests for updater.py module."""
import os
import sys
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestCheckReplaceOldArg:
    """Tests for check_replace_old_arg() function."""

    def test_no_replace_old_arg(self, monkeypatch):
        """Test when --replace-old is not provided."""
        monkeypatch.setattr(sys, 'argv', ['main.py'])

        import updater
        result = updater.check_replace_old_arg()
        assert result is None

    def test_with_replace_old_arg(self, monkeypatch):
        """Test when --replace-old is provided with path."""
        monkeypatch.setattr(sys, 'argv', ['main.py', '--replace-old', '/path/to/old.exe'])

        import updater
        result = updater.check_replace_old_arg()
        assert result == '/path/to/old.exe'

    def test_replace_old_without_path(self, monkeypatch):
        """Test when --replace-old is provided without path."""
        monkeypatch.setattr(sys, 'argv', ['main.py', '--replace-old'])

        import updater
        result = updater.check_replace_old_arg()
        assert result is None

    def test_other_args_present(self, monkeypatch):
        """Test with other args present."""
        monkeypatch.setattr(sys, 'argv', ['main.py', '--debug', '--replace-old', '/path/to/old.exe', '--verbose'])

        import updater
        result = updater.check_replace_old_arg()
        assert result == '/path/to/old.exe'


class TestGetCurrentExecutable:
    """Tests for get_current_executable() function."""

    def test_source_mode(self, monkeypatch):
        """Test getting executable path when running from source."""
        monkeypatch.delattr(sys, 'frozen', raising=False)
        monkeypatch.setattr(sys, 'argv', ['/path/to/main.py'])

        import updater
        result = updater.get_current_executable()
        assert result.name == 'main.py'

    def test_frozen_mode(self, monkeypatch):
        """Test getting executable path when running as frozen exe."""
        sys.frozen = True
        sys.executable = '/path/to/LootRun.exe'

        try:
            import updater
            result = updater.get_current_executable()
            assert result == Path('/path/to/LootRun.exe')
        finally:
            del sys.frozen


class TestDeleteOldExecutable:
    """Tests for _delete_old_executable() function."""

    def test_delete_existing_file(self, tmp_path):
        """Test deleting an existing file."""
        old_exe = tmp_path / "old.exe"
        old_exe.write_bytes(b"old content")

        import updater
        success, message = updater._delete_old_executable(old_exe)

        assert success is True
        assert not old_exe.exists()
        assert "successfully deleted" in message.lower()

    def test_delete_nonexistent_file(self, tmp_path):
        """Test deleting a file that doesn't exist."""
        old_exe = tmp_path / "nonexistent.exe"

        import updater
        success, message = updater._delete_old_executable(old_exe)

        assert success is True
        assert "already removed" in message.lower() or "successfully deleted" in message.lower()

    def test_delete_permission_denied(self, tmp_path, monkeypatch):
        """Test handling of permission denied error."""
        old_exe = tmp_path / "locked.exe"
        old_exe.write_bytes(b"locked content")

        import updater
        # Mock unlink to always raise PermissionError
        original_unlink = Path.unlink

        def mock_unlink(self, *args, **kwargs):
            if self == old_exe:
                raise PermissionError("File is locked")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", mock_unlink)
        # Speed up test by reducing retries
        monkeypatch.setattr(updater, "MAX_RETRY_ATTEMPTS", 2)
        monkeypatch.setattr(updater, "RETRY_DELAY", 0.01)

        success, message = updater._delete_old_executable(old_exe)

        assert success is False
        assert "permission denied" in message.lower() or "failed" in message.lower()


class TestRenameSelfToOriginal:
    """Tests for _rename_self_to_original() function."""

    def test_rename_successful(self, tmp_path, monkeypatch):
        """Test successful rename."""
        current_exe = tmp_path / "LootRun_new.exe"
        current_exe.write_bytes(b"new content")
        old_path = tmp_path / "LootRun.exe"

        import updater
        monkeypatch.setattr(updater, "get_current_executable", lambda: current_exe)

        success, message = updater._rename_self_to_original(old_path)

        assert success is True
        assert (tmp_path / "LootRun.exe").exists()
        assert not current_exe.exists()

    def test_rename_already_at_target(self, tmp_path, monkeypatch):
        """Test when already at target path."""
        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"content")

        import updater
        monkeypatch.setattr(updater, "get_current_executable", lambda: current_exe)

        success, message = updater._rename_self_to_original(current_exe)

        assert success is True
        assert "already at target" in message.lower()


class TestLaunchNewExecutable:
    """Tests for launch_new_executable() function."""

    def test_launch_windows(self, tmp_path, monkeypatch):
        """Test launching new executable on Windows."""
        import updater
        monkeypatch.setattr('platform.system', lambda: 'Windows')

        new_exe = tmp_path / "LootRun_new.exe"
        new_exe.write_bytes(b"new exe")
        old_exe = tmp_path / "LootRun.exe"

        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            result = updater.launch_new_executable(new_exe, old_exe)

        assert result is True
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert str(new_exe) in call_args[0][0]
        assert "--replace-old" in call_args[0][0]
        assert str(old_exe) in call_args[0][0]

    def test_launch_unix(self, tmp_path, monkeypatch):
        """Test launching new executable on Unix."""
        import updater
        monkeypatch.setattr('platform.system', lambda: 'Linux')

        new_exe = tmp_path / "LootRun_new"
        new_exe.write_bytes(b"new exe")
        old_exe = tmp_path / "LootRun"

        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            result = updater.launch_new_executable(new_exe, old_exe)

        assert result is True
        mock_popen.assert_called_once()

    def test_launch_failure(self, tmp_path, monkeypatch):
        """Test handling of launch failure."""
        import updater
        monkeypatch.setattr('platform.system', lambda: 'Windows')

        new_exe = tmp_path / "LootRun_new.exe"
        old_exe = tmp_path / "LootRun.exe"

        with patch('subprocess.Popen', side_effect=Exception("Launch failed")):
            result = updater.launch_new_executable(new_exe, old_exe)

        assert result is False


class TestHandleReplaceOld:
    """Tests for handle_replace_old() function."""

    def test_full_replacement_flow(self, tmp_path, monkeypatch, capsys):
        """Test the full replacement flow."""
        import updater

        # Create mock files - use different directories to simulate real scenario
        # Old exe in one location, new exe in same location
        old_exe = tmp_path / "old_dir" / "LootRun.exe"
        old_exe.parent.mkdir(parents=True, exist_ok=True)
        old_exe.write_bytes(b"old content")

        new_exe = tmp_path / "old_dir" / "LootRun_new.exe"
        new_exe.write_bytes(b"new content")

        monkeypatch.setattr(updater, "get_current_executable", lambda: new_exe)
        monkeypatch.setattr(updater, "REPLACEMENT_WAIT_TIME", 0.01)

        # Mock the restart to avoid actually starting a process
        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            result = updater.handle_replace_old(str(old_exe))

        assert result is True
        # The target path (LootRun.exe) should exist - it's the renamed new exe
        target_exe = tmp_path / "old_dir" / "LootRun.exe"
        assert target_exe.exists()
        # The content should be from the new exe (not old content)
        assert target_exe.read_bytes() == b"new content"
        # LootRun_new.exe should no longer exist (was renamed)
        assert not new_exe.exists()

        captured = capsys.readouterr()
        assert "update complete" in captured.out.lower()

    def test_replacement_with_delete_failure(self, tmp_path, monkeypatch, capsys):
        """Test replacement continues even if delete fails."""
        import updater

        old_exe = tmp_path / "LootRun.exe"
        # Don't create old_exe - simulate it was already deleted
        new_exe = tmp_path / "LootRun_new.exe"
        new_exe.write_bytes(b"new content")

        monkeypatch.setattr(updater, "get_current_executable", lambda: new_exe)
        monkeypatch.setattr(updater, "REPLACEMENT_WAIT_TIME", 0.01)

        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            result = updater.handle_replace_old(str(old_exe))

        # Should still succeed - old exe was already gone
        assert result is True


class TestWaitForProcessExit:
    """Tests for _wait_for_process_exit() function."""

    def test_wait_default_time(self, monkeypatch):
        """Test waiting for default time."""
        import updater
        import time

        start = time.time()
        updater._wait_for_process_exit(0.1)
        elapsed = time.time() - start

        assert elapsed >= 0.1


class TestRestartWithoutFlag:
    """Tests for _restart_without_flag() function."""

    def test_restart_windows(self, tmp_path, monkeypatch):
        """Test restart on Windows."""
        import updater
        monkeypatch.setattr('platform.system', lambda: 'Windows')

        new_path = tmp_path / "LootRun.exe"

        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            updater._restart_without_flag(new_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert str(new_path) in call_args[0][0]
        # Should have Windows-specific flags
        assert 'creationflags' in call_args[1]

    def test_restart_unix(self, tmp_path, monkeypatch):
        """Test restart on Unix."""
        import updater
        monkeypatch.setattr('platform.system', lambda: 'Linux')

        new_path = tmp_path / "LootRun"

        mock_popen = MagicMock()
        with patch('subprocess.Popen', mock_popen):
            updater._restart_without_flag(new_path)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        # Should have Unix-specific flags
        assert 'start_new_session' in call_args[1]

    def test_restart_error_handling(self, tmp_path, monkeypatch, capsys):
        """Test restart error handling."""
        import updater

        new_path = tmp_path / "nonexistent.exe"

        with patch('subprocess.Popen', side_effect=Exception("Cannot start")):
            updater._restart_without_flag(new_path)

        captured = capsys.readouterr()
        assert "warning" in captured.out.lower() or "could not restart" in captured.out.lower()


class TestVersionPerformUpdate:
    """Tests for version.py perform_update() function."""

    def test_no_update_available(self, monkeypatch):
        """Test when no update is available."""
        import version
        monkeypatch.setattr(version, "check_for_update", lambda timeout=10: (False, "You have the latest version"))

        should_exit, message = version.perform_update()

        assert should_exit is False
        assert "latest version" in message.lower()

    def test_update_downloaded_and_launched(self, tmp_path, monkeypatch):
        """Test successful update download and launch."""
        import version

        # Create mock new exe
        new_exe = tmp_path / "LootRun_new.exe"
        new_exe.write_bytes(b"new exe")
        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"current exe")

        monkeypatch.setattr(version, "check_for_update", lambda timeout=10: (True, "Update downloaded"))
        monkeypatch.setattr(version, "_get_current_executable", lambda: current_exe)
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        # Mock the launch function
        with patch('updater.launch_new_executable', return_value=True) as mock_launch:
            should_exit, message = version.perform_update()

        assert should_exit is True
        mock_launch.assert_called_once()

    def test_update_downloaded_but_file_missing(self, tmp_path, monkeypatch):
        """Test when update is downloaded but file is missing."""
        import version

        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"current exe")

        monkeypatch.setattr(version, "check_for_update", lambda timeout=10: (True, "Update downloaded"))
        monkeypatch.setattr(version, "_get_current_executable", lambda: current_exe)
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        should_exit, message = version.perform_update()

        assert should_exit is False
        assert "not found" in message.lower()

    def test_launch_failure(self, tmp_path, monkeypatch):
        """Test when launch fails."""
        import version

        new_exe = tmp_path / "LootRun_new.exe"
        new_exe.write_bytes(b"new exe")
        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"current exe")

        monkeypatch.setattr(version, "check_for_update", lambda timeout=10: (True, "Update downloaded"))
        monkeypatch.setattr(version, "_get_current_executable", lambda: current_exe)
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        with patch('updater.launch_new_executable', return_value=False):
            should_exit, message = version.perform_update()

        assert should_exit is False
        assert "failed" in message.lower()


class TestVersionDownloadWithExecutablePermissions:
    """Tests for executable permission setting after download."""

    def test_download_sets_executable_on_unix(self, tmp_path, monkeypatch):
        """Test that download sets executable permissions on Unix."""
        import version

        destination = tmp_path / "LootRun_new"
        monkeypatch.setattr(version, "_get_platform", lambda: "Linux")

        # Mock the URL download
        mock_response = MagicMock()
        mock_response.read.return_value = b"executable content"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        # Mock os.chmod to verify it's called with correct permissions
        with patch('urllib.request.urlopen', return_value=mock_response):
            with patch('os.chmod') as mock_chmod:
                result = version._download_file("https://example.com/exe", destination, set_executable=True)

        assert result is True
        assert destination.exists()
        # Verify chmod was called with 0o755 equivalent
        mock_chmod.assert_called_once()
        call_args = mock_chmod.call_args
        assert call_args[0][0] == destination
        # 0o755 = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        expected_mode = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        assert call_args[0][1] == expected_mode

    def test_download_no_executable_on_windows(self, tmp_path, monkeypatch):
        """Test that download doesn't try to set executable on Windows."""
        import version

        destination = tmp_path / "LootRun_new.exe"
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        mock_response = MagicMock()
        mock_response.read.return_value = b"executable content"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            with patch('os.chmod') as mock_chmod:
                result = version._download_file("https://example.com/exe", destination, set_executable=True)

        assert result is True
        # chmod should not be called on Windows
        mock_chmod.assert_not_called()


class TestGetCurrentExecutableInVersion:
    """Tests for _get_current_executable() in version.py."""

    def test_source_mode(self, monkeypatch):
        """Test getting executable path when running from source."""
        monkeypatch.delattr(sys, 'frozen', raising=False)
        monkeypatch.setattr(sys, 'argv', ['/path/to/main.py'])

        import version
        result = version._get_current_executable()
        assert result.name == 'main.py'

    def test_frozen_mode(self, monkeypatch):
        """Test getting executable path when running as frozen exe."""
        sys.frozen = True
        sys.executable = '/path/to/LootRun.exe'

        try:
            import version
            result = version._get_current_executable()
            assert result == Path('/path/to/LootRun.exe')
        finally:
            del sys.frozen
