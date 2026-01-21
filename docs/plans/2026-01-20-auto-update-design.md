# Auto-Update and Version Validation Design

## Overview

Automatic updates via GitHub releases, version display in menu, strict server-client version validation, and full CI/CD automation.

## Version System

**Format:** Date-based semantic versioning
- `v2026.01.20` - first release of the day
- `v2026.01.20.1` - second release same day

**Storage:** `VERSION` file at project root, baked into executable at build time.

**Access:** `version.py` reads VERSION file, exposes `VERSION` constant.

## Distribution

**Format:** Single PyInstaller executable per platform
- `LootRun-Windows.exe`
- `LootRun-macOS`
- `LootRun-Linux`

**Build:** PyInstaller bundles Python + all dependencies into one file.

## Auto-Update Flow

1. Game starts
2. Query GitHub API: `GET /repos/Bluepuff71/AI-Guessing-Game/releases/latest`
3. Compare local VERSION with release `tag_name`
4. If newer release exists:
   - Download platform-specific executable
   - Save as `LootRun_new.exe`
   - Launch new exe with `--replace-old` flag
   - Exit current process
   - New exe deletes old exe, renames itself
5. If up-to-date or failed: continue to menu

**Failure Handling:** Show error message, continue with current version.

## Server-Client Version Validation

**Strict match required** - client version must equal server version.

**Handshake:**
1. Client sends `join` with `version` field
2. Server compares versions
3. Mismatch: Send `version_mismatch` error, close connection
4. Match: Continue normal flow

**LAN Discovery:** Broadcast includes server version. Incompatible games shown dimmed.

## CI/CD Pipeline

**Trigger:** Push or merge to `main` branch

**Workflow Steps:**
1. Generate version tag from current date
2. Check if tag exists, add suffix if needed (`.1`, `.2`)
3. Write version to `VERSION` file
4. Build executables with PyInstaller for Windows, macOS, Linux
5. Create GitHub release with tag
6. Upload executables as release assets

## File Changes

| File | Change |
|------|--------|
| `VERSION` (new) | Version string |
| `version.py` (new) | Read version, update checker, replacement logic |
| `main.py` | Call update check at startup |
| `client/ui.py` | Show version in menu header |
| `client/connection.py` | Send version in join message |
| `server/protocol.py` | Add version to join message type |
| `server/main.py` | Validate client version on join |
| `client/lan.py` | Include version in broadcast |
| `.github/workflows/release.yml` (new) | CI/CD automation |
| `LootRun.spec` (new) | PyInstaller build spec |

## Implementation Tasks

1. Create VERSION file and version.py with update checker
2. Add --replace-old flag handling for executable replacement
3. Update main.py to call update check
4. Update client/ui.py to show version in menu
5. Update protocol and connection to include version in join
6. Add server-side version validation
7. Update LAN discovery to include version
8. Create PyInstaller spec file
9. Create GitHub Actions workflow for automated releases
10. Test update flow end-to-end
