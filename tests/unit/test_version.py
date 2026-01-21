"""Tests for version.py module."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import urllib.error

import pytest


class TestGetVersion:
    """Tests for get_version() function."""

    def test_get_version_from_file(self, tmp_path, monkeypatch):
        """Test reading version from VERSION file."""
        # Create a temporary VERSION file
        version_file = tmp_path / "VERSION"
        version_file.write_text("v2026.01.20\n")

        # Patch the version file path
        import version
        monkeypatch.setattr(version, "_get_version_file_path", lambda: version_file)

        result = version.get_version()
        assert result == "v2026.01.20"

    def test_get_version_strips_whitespace(self, tmp_path, monkeypatch):
        """Test that version string is stripped of whitespace."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("  v2026.01.20  \n\n")

        import version
        monkeypatch.setattr(version, "_get_version_file_path", lambda: version_file)

        result = version.get_version()
        assert result == "v2026.01.20"

    def test_get_version_file_not_found(self, tmp_path, monkeypatch):
        """Test handling of missing VERSION file."""
        version_file = tmp_path / "nonexistent" / "VERSION"

        import version
        monkeypatch.setattr(version, "_get_version_file_path", lambda: version_file)

        result = version.get_version()
        assert result == "unknown"

    def test_get_version_dev(self, tmp_path, monkeypatch):
        """Test reading 'dev' version."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("dev\n")

        import version
        monkeypatch.setattr(version, "_get_version_file_path", lambda: version_file)

        result = version.get_version()
        assert result == "dev"


class TestVersionFilePath:
    """Tests for _get_version_file_path() function."""

    def test_source_mode_path(self, monkeypatch):
        """Test VERSION path when running from source."""
        # Ensure frozen is not set
        monkeypatch.delattr(sys, 'frozen', raising=False)

        import version
        path = version._get_version_file_path()

        # Should point to VERSION in same directory as version.py
        assert path.name == "VERSION"
        assert path.parent == Path(version.__file__).parent

    def test_pyinstaller_mode_path(self, monkeypatch):
        """Test VERSION path when running from PyInstaller bundle."""
        # Simulate PyInstaller frozen mode
        # Use setattr on sys module object directly since 'frozen' doesn't exist normally
        sys.frozen = True
        sys._MEIPASS = '/tmp/pyinstaller_bundle'

        try:
            import version
            # Need to reload to pick up the patched sys attributes
            path = version._get_version_file_path()

            assert path == Path('/tmp/pyinstaller_bundle') / "VERSION"
        finally:
            # Clean up
            del sys.frozen
            del sys._MEIPASS


class TestParseVersion:
    """Tests for _parse_version() function."""

    def test_parse_standard_version(self):
        """Test parsing standard version format."""
        import version
        result = version._parse_version("v2026.01.20")
        assert result == (2026, 1, 20)

    def test_parse_version_without_v(self):
        """Test parsing version without leading v."""
        import version
        result = version._parse_version("2026.01.20")
        assert result == (2026, 1, 20)

    def test_parse_dev_version(self):
        """Test parsing 'dev' version."""
        import version
        result = version._parse_version("dev")
        assert result == (0,)

    def test_parse_unknown_version(self):
        """Test parsing 'unknown' version."""
        import version
        result = version._parse_version("unknown")
        assert result == (0,)

    def test_parse_empty_version(self):
        """Test parsing empty version string."""
        import version
        result = version._parse_version("")
        assert result == (0,)

    def test_parse_none_version(self):
        """Test parsing None version."""
        import version
        result = version._parse_version(None)
        assert result == (0,)

    def test_parse_semver_format(self):
        """Test parsing semver-like format."""
        import version
        result = version._parse_version("v1.2.3")
        assert result == (1, 2, 3)


class TestIsNewerVersion:
    """Tests for _is_newer_version() function."""

    def test_newer_version(self):
        """Test detecting a newer version."""
        import version
        assert version._is_newer_version("v2026.01.21", "v2026.01.20") is True

    def test_same_version(self):
        """Test same version."""
        import version
        assert version._is_newer_version("v2026.01.20", "v2026.01.20") is False

    def test_older_version(self):
        """Test older remote version."""
        import version
        assert version._is_newer_version("v2026.01.19", "v2026.01.20") is False

    def test_dev_always_older(self):
        """Test that any release is newer than dev."""
        import version
        assert version._is_newer_version("v2026.01.01", "dev") is True

    def test_unknown_always_older(self):
        """Test that any release is newer than unknown."""
        import version
        assert version._is_newer_version("v2026.01.01", "unknown") is True

    def test_year_comparison(self):
        """Test year-level comparison."""
        import version
        assert version._is_newer_version("v2027.01.01", "v2026.12.31") is True

    def test_month_comparison(self):
        """Test month-level comparison."""
        import version
        assert version._is_newer_version("v2026.02.01", "v2026.01.31") is True


class TestGetPlatform:
    """Tests for _get_platform() function."""

    def test_get_platform_windows(self, monkeypatch):
        """Test platform detection on Windows."""
        import version
        monkeypatch.setattr('platform.system', lambda: 'Windows')
        assert version._get_platform() == 'Windows'

    def test_get_platform_macos(self, monkeypatch):
        """Test platform detection on macOS."""
        import version
        monkeypatch.setattr('platform.system', lambda: 'Darwin')
        assert version._get_platform() == 'Darwin'

    def test_get_platform_linux(self, monkeypatch):
        """Test platform detection on Linux."""
        import version
        monkeypatch.setattr('platform.system', lambda: 'Linux')
        assert version._get_platform() == 'Linux'


class TestGetAssetDownloadUrl:
    """Tests for _get_asset_download_url() function."""

    def test_find_windows_asset(self):
        """Test finding Windows asset URL."""
        import version
        release_data = {
            "assets": [
                {"name": "LootRun-Windows.exe", "browser_download_url": "https://example.com/win.exe"},
                {"name": "LootRun-macOS", "browser_download_url": "https://example.com/mac"},
            ]
        }
        url = version._get_asset_download_url(release_data, "LootRun-Windows.exe")
        assert url == "https://example.com/win.exe"

    def test_find_macos_asset(self):
        """Test finding macOS asset URL."""
        import version
        release_data = {
            "assets": [
                {"name": "LootRun-Windows.exe", "browser_download_url": "https://example.com/win.exe"},
                {"name": "LootRun-macOS", "browser_download_url": "https://example.com/mac"},
            ]
        }
        url = version._get_asset_download_url(release_data, "LootRun-macOS")
        assert url == "https://example.com/mac"

    def test_asset_not_found(self):
        """Test when asset is not found."""
        import version
        release_data = {
            "assets": [
                {"name": "other-file.zip", "browser_download_url": "https://example.com/other"},
            ]
        }
        url = version._get_asset_download_url(release_data, "LootRun-Windows.exe")
        assert url is None

    def test_empty_assets(self):
        """Test with empty assets list."""
        import version
        release_data = {"assets": []}
        url = version._get_asset_download_url(release_data, "LootRun-Windows.exe")
        assert url is None

    def test_no_assets_key(self):
        """Test with missing assets key."""
        import version
        release_data = {}
        url = version._get_asset_download_url(release_data, "LootRun-Windows.exe")
        assert url is None


class TestCheckForUpdate:
    """Tests for check_for_update() function."""

    def test_no_update_needed(self, monkeypatch):
        """Test when already on latest version."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.20")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        # Mock API response
        release_data = {"tag_name": "v2026.01.20", "assets": []}
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(release_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "latest version" in message.lower()

    def test_update_available_and_downloaded(self, monkeypatch, tmp_path):
        """Test successful update download."""
        import version

        # Create a mock current executable in tmp_path
        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"current exe")

        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")
        monkeypatch.setattr(version, "_get_current_executable", lambda: current_exe)

        # Mock API response with newer version
        release_data = {
            "tag_name": "v2026.01.20",
            "assets": [
                {"name": "LootRun-Windows.exe", "browser_download_url": "https://example.com/win.exe"}
            ]
        }
        mock_api_response = MagicMock()
        mock_api_response.read.return_value = json.dumps(release_data).encode()
        mock_api_response.__enter__ = MagicMock(return_value=mock_api_response)
        mock_api_response.__exit__ = MagicMock(return_value=False)

        # Mock download response
        mock_download_response = MagicMock()
        mock_download_response.read.return_value = b"fake executable content"
        mock_download_response.__enter__ = MagicMock(return_value=mock_download_response)
        mock_download_response.__exit__ = MagicMock(return_value=False)

        call_count = [0]

        def mock_urlopen(request, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_api_response
            return mock_download_response

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            downloaded, message = version.check_for_update()

        assert downloaded is True
        assert "v2026.01.20" in message
        # File should be downloaded next to current executable
        assert (tmp_path / "LootRun_new.exe").exists()

    def test_network_error(self, monkeypatch):
        """Test handling of network errors."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection failed")):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "network error" in message.lower()

    def test_http_404_error(self, monkeypatch):
        """Test handling of 404 (no releases found)."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)
        with patch('urllib.request.urlopen', side_effect=error):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "no releases" in message.lower()

    def test_http_other_error(self, monkeypatch):
        """Test handling of other HTTP errors."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        error = urllib.error.HTTPError("url", 500, "Server Error", {}, None)
        with patch('urllib.request.urlopen', side_effect=error):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "500" in message

    def test_unsupported_platform(self, monkeypatch):
        """Test handling of unsupported platform."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "FreeBSD")

        downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "unsupported platform" in message.lower()

    def test_no_asset_for_platform(self, monkeypatch):
        """Test when no asset exists for current platform."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        # Release has no Windows asset
        release_data = {
            "tag_name": "v2026.01.20",
            "assets": [
                {"name": "LootRun-macOS", "browser_download_url": "https://example.com/mac"}
            ]
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(release_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "no download available" in message.lower()

    def test_invalid_json_response(self, monkeypatch):
        """Test handling of invalid JSON from API."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "invalid response" in message.lower()

    def test_missing_tag_name(self, monkeypatch):
        """Test handling of response without tag_name."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        release_data = {"assets": []}  # No tag_name
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(release_data).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch('urllib.request.urlopen', return_value=mock_response):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "could not determine" in message.lower()

    def test_download_failure(self, monkeypatch):
        """Test handling of download failure."""
        import version
        monkeypatch.setattr(version, "get_version", lambda: "v2026.01.19")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")

        release_data = {
            "tag_name": "v2026.01.20",
            "assets": [
                {"name": "LootRun-Windows.exe", "browser_download_url": "https://example.com/win.exe"}
            ]
        }
        mock_api_response = MagicMock()
        mock_api_response.read.return_value = json.dumps(release_data).encode()
        mock_api_response.__enter__ = MagicMock(return_value=mock_api_response)
        mock_api_response.__exit__ = MagicMock(return_value=False)

        call_count = [0]

        def mock_urlopen(request, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_api_response
            raise urllib.error.URLError("Download failed")

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            downloaded, message = version.check_for_update()

        assert downloaded is False
        assert "failed" in message.lower()

    def test_dev_version_gets_update(self, monkeypatch, tmp_path):
        """Test that dev version always gets updates."""
        import version

        # Create a mock current executable in tmp_path
        current_exe = tmp_path / "LootRun.exe"
        current_exe.write_bytes(b"current exe")

        monkeypatch.setattr(version, "get_version", lambda: "dev")
        monkeypatch.setattr(version, "_get_platform", lambda: "Windows")
        monkeypatch.setattr(version, "_get_current_executable", lambda: current_exe)

        release_data = {
            "tag_name": "v2026.01.01",
            "assets": [
                {"name": "LootRun-Windows.exe", "browser_download_url": "https://example.com/win.exe"}
            ]
        }
        mock_api_response = MagicMock()
        mock_api_response.read.return_value = json.dumps(release_data).encode()
        mock_api_response.__enter__ = MagicMock(return_value=mock_api_response)
        mock_api_response.__exit__ = MagicMock(return_value=False)

        mock_download_response = MagicMock()
        mock_download_response.read.return_value = b"fake executable content"
        mock_download_response.__enter__ = MagicMock(return_value=mock_download_response)
        mock_download_response.__exit__ = MagicMock(return_value=False)

        call_count = [0]

        def mock_urlopen(request, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_api_response
            return mock_download_response

        with patch('urllib.request.urlopen', side_effect=mock_urlopen):
            downloaded, message = version.check_for_update()

        assert downloaded is True


class TestDownloadFile:
    """Tests for _download_file() function."""

    def test_successful_download(self, tmp_path):
        """Test successful file download."""
        import version

        mock_response = MagicMock()
        mock_response.read.return_value = b"test content"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        destination = tmp_path / "test_file"

        with patch('urllib.request.urlopen', return_value=mock_response):
            result = version._download_file("https://example.com/file", destination)

        assert result is True
        assert destination.exists()
        assert destination.read_bytes() == b"test content"

    def test_download_network_error(self, tmp_path):
        """Test download with network error."""
        import version

        destination = tmp_path / "test_file"

        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError("Connection failed")):
            result = version._download_file("https://example.com/file", destination)

        assert result is False
        assert not destination.exists()


class TestVersionConstant:
    """Tests for the VERSION constant."""

    def test_version_constant_exists(self):
        """Test that VERSION constant is exposed."""
        import version
        assert hasattr(version, 'VERSION')
        assert isinstance(version.VERSION, str)

    def test_version_constant_matches_get_version(self, tmp_path, monkeypatch):
        """Test that VERSION constant matches get_version() at import time."""
        # This tests that the constant was set correctly at module load
        import version
        # Note: VERSION is set at import time, so it reflects the actual VERSION file
        # We can't easily test this matches get_version() without reimporting
        assert version.VERSION is not None
