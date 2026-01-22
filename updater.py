"""
Executable replacement logic for LOOT RUN auto-update.

This module handles the --replace-old flag flow:
1. Old exe downloads new exe as `LootRun_new.exe`
2. Old exe launches new exe with `--replace-old <path_to_old_exe>` flag
3. Old exe exits
4. New exe (running with --replace-old flag):
   - Waits briefly for old exe to fully exit
   - Deletes the old exe file
   - Renames itself from `LootRun_new.exe` to the original name
   - Restarts itself without the --replace-old flag
"""
import os
import sys
import time
import subprocess
import platform
from pathlib import Path
from typing import Optional, Tuple


# Constants
REPLACEMENT_WAIT_TIME = 1.5  # seconds to wait for old exe to exit
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY = 0.5  # seconds between retry attempts


def get_current_executable() -> Path:
    """Get the path to the currently running executable.

    Returns:
        Path to the current executable
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable)
    else:
        # Running from source
        return Path(sys.argv[0]).resolve()


def _wait_for_process_exit(timeout: float = REPLACEMENT_WAIT_TIME) -> None:
    """Wait for the old process to fully exit.

    Args:
        timeout: Time in seconds to wait
    """
    time.sleep(timeout)


def _delete_old_executable(old_path: Path) -> Tuple[bool, str]:
    """Delete the old executable file.

    Args:
        old_path: Path to the old executable to delete

    Returns:
        Tuple of (success: bool, message: str)
    """
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            if old_path.exists():
                old_path.unlink()
            return (True, f"Successfully deleted old executable: {old_path}")
        except PermissionError:
            # Process may still be running, wait and retry
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_DELAY)
                continue
            return (False, f"Permission denied deleting {old_path}. Process may still be running.")
        except FileNotFoundError:
            # Already deleted, that's fine
            return (True, f"Old executable already removed: {old_path}")
        except Exception as e:
            return (False, f"Error deleting old executable: {e}")

    return (False, f"Failed to delete {old_path} after {MAX_RETRY_ATTEMPTS} attempts")


def _rename_self_to_original(old_path: Path) -> Tuple[bool, str]:
    """Rename current executable (LootRun_new) to original name.

    Args:
        old_path: Path to the old executable (determines the target name)

    Returns:
        Tuple of (success: bool, message: str)
    """
    current_exe = get_current_executable()
    target_name = old_path.name
    target_path = current_exe.parent / target_name

    # If we're already at the target path, nothing to do
    if current_exe == target_path:
        return (True, f"Already at target path: {target_path}")

    try:
        # On Windows, we can't rename a running executable directly
        # But we can rename after we've started a new process
        # For now, we'll attempt the rename and handle errors
        current_exe.rename(target_path)
        return (True, f"Renamed {current_exe.name} to {target_name}")
    except PermissionError:
        return (False, f"Permission denied renaming to {target_name}. Executable may be locked.")
    except FileExistsError:
        # Target already exists, try to remove it first
        try:
            target_path.unlink()
            current_exe.rename(target_path)
            return (True, f"Replaced existing {target_name}")
        except Exception as e:
            return (False, f"Failed to replace existing {target_name}: {e}")
    except Exception as e:
        return (False, f"Error renaming executable: {e}")


def _restart_without_flag(new_path: Path) -> None:
    """Restart the executable without the --replace-old flag.

    Args:
        new_path: Path to the renamed executable to start
    """
    try:
        if platform.system() == "Windows":
            # Use CREATE_NEW_CONSOLE to spawn a new console window for the app.
            # DETACHED_PROCESS would create a process without a console, causing
            # blank screen since this is a terminal UI application.
            subprocess.Popen(
                [str(new_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True
            )
        else:
            # Unix: fork and exec
            subprocess.Popen(
                [str(new_path)],
                start_new_session=True,
                close_fds=True
            )
    except Exception as e:
        print(f"Warning: Could not restart application: {e}")
        print(f"Please manually start: {new_path}")


def handle_replace_old(old_exe_path: str) -> bool:
    """Handle the --replace-old flag: replace the old executable.

    This function:
    1. Waits for old exe to exit
    2. Deletes the old exe
    3. Renames self to original name
    4. Restarts without --replace-old flag
    5. Exits

    Args:
        old_exe_path: Path to the old executable to replace

    Returns:
        True if replacement was successful, False otherwise
    """
    old_path = Path(old_exe_path).resolve()
    print(f"Performing update: replacing {old_path.name}...")

    # Step 1: Wait for old process to exit
    print("  Waiting for previous version to exit...")
    _wait_for_process_exit()

    # Step 2: Delete old executable
    print("  Removing old version...")
    success, message = _delete_old_executable(old_path)
    if not success:
        print(f"  Warning: {message}")
        # Continue anyway - we might still be able to rename

    # Step 3: Rename self to original name
    print("  Finalizing update...")
    current_exe = get_current_executable()
    target_path = old_path.parent / old_path.name

    # Only rename if we're not already at the target
    if current_exe.name != old_path.name:
        success, message = _rename_self_to_original(old_path)
        if not success:
            print(f"  Error: {message}")
            print("  Update completed but executable was not renamed.")
            print(f"  You can manually rename {current_exe.name} to {old_path.name}")
            return False
        else:
            print(f"  {message}")
            target_path = current_exe.parent / old_path.name
    else:
        target_path = current_exe

    # Step 4: Restart without flag
    print("  Restarting application...")
    _restart_without_flag(target_path)

    print("Update complete!")
    return True


def launch_new_executable(new_exe_path: Path, old_exe_path: Path) -> bool:
    """Launch the new executable with --replace-old flag.

    Called by the old executable after downloading the update.

    Args:
        new_exe_path: Path to the newly downloaded executable
        old_exe_path: Path to the current (old) executable

    Returns:
        True if launch was successful, False otherwise
    """
    try:
        args = [str(new_exe_path), "--replace-old", str(old_exe_path)]

        if platform.system() == "Windows":
            # Use CREATE_NEW_CONSOLE to spawn a new console window for the app.
            # DETACHED_PROCESS would create a process without a console, causing
            # blank screen since this is a terminal UI application.
            subprocess.Popen(
                args,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True
            )
        else:
            subprocess.Popen(
                args,
                start_new_session=True,
                close_fds=True
            )
        return True
    except Exception as e:
        print(f"Error launching new executable: {e}")
        return False


def check_replace_old_arg() -> Optional[str]:
    """Check if --replace-old argument was provided.

    Returns:
        Path to old executable if --replace-old was provided, None otherwise
    """
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--replace-old" and i + 1 < len(args):
            return args[i + 1]
    return None
