"""
LOOT RUN - A strategic looting game with adaptive AI

Players compete to reach 100 points by looting locations,
while an AI learns their patterns and hunts them down.

Supports:
- Single player (1 human vs AI)
- Hot-seat local multiplayer (2-6 players, one terminal)
- LAN multiplayer with auto-discovery
- Online multiplayer
"""
import sys
import io

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import asyncio
from client.main import GameClient
from updater import check_replace_old_arg, handle_replace_old
from version import perform_update


def handle_startup_update() -> bool:
    """Handle update-related startup logic.

    Returns:
        True if the program should exit (replacement in progress), False otherwise
    """
    # Check if we're running with --replace-old flag (new exe replacing old)
    old_exe_path = check_replace_old_arg()
    if old_exe_path:
        # We are the new executable, perform replacement
        success = handle_replace_old(old_exe_path)
        # Always exit after replacement attempt - either we restart or user handles manually
        return True

    # Check for updates (only when running normally, not during replacement)
    try:
        should_exit, message = perform_update()
        if should_exit:
            print(message)
            return True
        elif message:
            # Print update status (e.g., "You have the latest version")
            # Only print if it's informational, not an error
            if "latest version" in message.lower():
                print(f"Version check: {message}")
    except Exception as e:
        # Don't let update check failures prevent game from running
        print(f"Update check skipped: {e}")

    return False


def main():
    """Main entry point for LOOT RUN."""
    # Handle update logic first
    if handle_startup_update():
        sys.exit(0)

    # Normal game startup
    client = GameClient()
    asyncio.run(client.run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGame interrupted. Thanks for playing!\n")
        sys.exit(0)
    except Exception as e:
        print(f"\nAn error occurred: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
