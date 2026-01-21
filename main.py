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


def main():
    """Main entry point for LOOT RUN."""
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
