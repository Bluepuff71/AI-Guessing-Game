"""
Version management and auto-update functionality for LOOT RUN.

This module provides:
- VERSION constant read from VERSION file (works with PyInstaller)
- get_version() function for reading the version
- check_for_update() function that queries GitHub releases and downloads updates
"""
import os
import sys
import platform
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Tuple, Optional


def _get_version_file_path() -> Path:
    """Get the path to the VERSION file.

    Handles both:
    - Running from source: reads VERSION from project root
    - Running from PyInstaller exe: reads bundled VERSION file

    Returns:
        Path to VERSION file
    """
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running from source - VERSION is in project root
        base_path = Path(__file__).parent

    return base_path / "VERSION"


def get_version() -> str:
    """Read and return the version string from VERSION file.

    Returns:
        Version string (e.g., "dev", "v2026.01.20")
    """
    version_path = _get_version_file_path()
    try:
        return version_path.read_text().strip()
    except FileNotFoundError:
        return "unknown"
    except Exception:
        return "unknown"


# Expose VERSION constant at module level
VERSION = get_version()


# GitHub repository information
GITHUB_REPO_OWNER = "Bluepuff71"
GITHUB_REPO_NAME = "AI-Guessing-Game"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

# Platform-specific asset names
ASSET_NAMES = {
    "Windows": "LootRun-Windows.exe",
    "Darwin": "LootRun-macOS",
    "Linux": "LootRun-Linux",
}


def _get_platform() -> str:
    """Get the current platform name.

    Returns:
        Platform name: "Windows", "Darwin" (macOS), or "Linux"
    """
    return platform.system()


def _parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a version string into comparable tuple.

    Handles formats like:
    - "v2026.01.20" -> (2026, 1, 20)
    - "dev" -> (0,)
    - "unknown" -> (0,)

    Args:
        version_str: Version string to parse

    Returns:
        Tuple of integers for comparison
    """
    if not version_str or version_str in ("dev", "unknown"):
        return (0,)

    # Strip leading 'v' if present
    version_str = version_str.lstrip("v")

    try:
        parts = version_str.split(".")
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0,)


def _is_newer_version(remote_version: str, local_version: str) -> bool:
    """Check if remote version is newer than local version.

    Args:
        remote_version: Version from GitHub release
        local_version: Local VERSION file content

    Returns:
        True if remote is newer, False otherwise
    """
    remote_tuple = _parse_version(remote_version)
    local_tuple = _parse_version(local_version)
    return remote_tuple > local_tuple


def _get_asset_download_url(release_data: dict, asset_name: str) -> Optional[str]:
    """Extract download URL for specific asset from release data.

    Args:
        release_data: JSON response from GitHub releases API
        asset_name: Name of the asset to find

    Returns:
        Download URL if found, None otherwise
    """
    assets = release_data.get("assets", [])
    for asset in assets:
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url")
    return None


def _download_file(url: str, destination: Path, timeout: int = 60) -> bool:
    """Download a file from URL to destination.

    Args:
        url: URL to download from
        destination: Path to save the file
        timeout: Request timeout in seconds

    Returns:
        True if download succeeded, False otherwise
    """
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"LootRun/{VERSION}"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            with open(destination, "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False


def check_for_update(timeout: int = 10) -> Tuple[bool, str]:
    """Check for updates and download if a newer version is available.

    Queries GitHub API for the latest release, compares with local version,
    and downloads the platform-specific executable if an update is available.

    Args:
        timeout: Timeout for API requests in seconds

    Returns:
        Tuple of (update_downloaded: bool, message: str)
        - (True, message) if update was downloaded successfully
        - (False, message) if no update needed or an error occurred
    """
    local_version = get_version()
    current_platform = _get_platform()

    # Check if platform is supported
    if current_platform not in ASSET_NAMES:
        return (False, f"Unsupported platform: {current_platform}")

    # Query GitHub API for latest release
    try:
        request = urllib.request.Request(
            GITHUB_API_URL,
            headers={
                "User-Agent": f"LootRun/{VERSION}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            release_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (False, "No releases found on GitHub")
        return (False, f"GitHub API error: HTTP {e.code}")
    except urllib.error.URLError as e:
        return (False, f"Network error: {e.reason}")
    except json.JSONDecodeError:
        return (False, "Invalid response from GitHub API")
    except Exception as e:
        return (False, f"Error checking for updates: {e}")

    # Get release tag name (version)
    remote_version = release_data.get("tag_name", "")
    if not remote_version:
        return (False, "Could not determine remote version")

    # Compare versions
    if not _is_newer_version(remote_version, local_version):
        return (False, f"You have the latest version ({local_version})")

    # Find platform-specific asset
    asset_name = ASSET_NAMES[current_platform]
    download_url = _get_asset_download_url(release_data, asset_name)

    if not download_url:
        return (False, f"No download available for {current_platform}")

    # Download the update
    # Save as LootRun_new.exe (or appropriate name) in current directory
    if current_platform == "Windows":
        new_exe_name = "LootRun_new.exe"
    else:
        new_exe_name = "LootRun_new"

    destination = Path.cwd() / new_exe_name

    print(f"Downloading update {remote_version}...")
    if _download_file(download_url, destination, timeout=60):
        return (True, f"Update downloaded: {remote_version} -> {destination}")
    else:
        return (False, "Failed to download update")
