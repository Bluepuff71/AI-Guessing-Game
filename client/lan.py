# client/lan.py
"""LAN discovery for LOOT RUN multiplayer games."""

import asyncio
import json
import socket
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

DISCOVERY_PORT = 19132
BROADCAST_INTERVAL = 2.0
BUFFER_SIZE = 4096
DEFAULT_MAX_PLAYERS = 6


@dataclass
class DiscoveredGame:
    """Represents a discovered LAN game."""
    host: str
    port: int
    game_name: str
    host_name: str
    player_count: int
    max_players: int


class LANDiscovery:
    """Handles LAN game discovery via UDP broadcast."""

    def __init__(self):
        self._broadcasting = False
        self._broadcast_task: Optional[asyncio.Task] = None
        self._broadcast_socket: Optional[socket.socket] = None
        self._broadcast_data: Optional[Dict[str, Any]] = None

    async def start_broadcasting(
        self,
        port: int,
        game_name: str,
        host_name: str,
        player_count: int,
        max_players: int
    ) -> bool:
        """Start broadcasting game info over UDP.

        Args:
            port: The game server port
            game_name: Name of the game/lobby
            host_name: Name of the host player
            player_count: Current number of players
            max_players: Maximum number of players allowed

        Returns:
            True if broadcasting started successfully, False otherwise
        """
        if self._broadcasting:
            return True

        try:
            # Create UDP socket for broadcasting
            self._broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self._broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._broadcast_socket.setblocking(False)

            self._broadcasting = True

            # Store broadcast data
            self._broadcast_data = {
                "type": "LOOT_RUN_GAME",
                "port": port,
                "game_name": game_name,
                "host_name": host_name,
                "player_count": player_count,
                "max_players": max_players,
            }

            # Start broadcast loop
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            return True

        except OSError as e:
            self._broadcasting = False
            if self._broadcast_socket:
                self._broadcast_socket.close()
                self._broadcast_socket = None
            return False

    def update_player_count(self, player_count: int):
        """Update the player count in broadcast data."""
        if self._broadcasting and self._broadcast_data:
            self._broadcast_data["player_count"] = player_count

    async def _broadcast_loop(self):
        """Continuously broadcast game info."""
        while self._broadcasting:
            try:
                if self._broadcast_socket and self._broadcast_data:
                    message = json.dumps(self._broadcast_data).encode('utf-8')
                    # Broadcast to all addresses on the network
                    # Use 255.255.255.255 for cross-platform compatibility
                    self._broadcast_socket.sendto(
                        message,
                        ('255.255.255.255', DISCOVERY_PORT)
                    )
            except OSError:
                # Socket error, stop broadcasting
                break
            except Exception:
                # Ignore other errors and continue
                pass

            await asyncio.sleep(BROADCAST_INTERVAL)

    async def stop_broadcasting(self):
        """Stop broadcasting game info."""
        self._broadcasting = False

        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None

        if self._broadcast_socket:
            try:
                self._broadcast_socket.close()
            except OSError:
                pass
            self._broadcast_socket = None

    async def scan_for_games(self, timeout: float = 3.0) -> List[DiscoveredGame]:
        """Scan for LAN games.

        Args:
            timeout: How long to scan for games (seconds)

        Returns:
            List of discovered games
        """
        discovered: Dict[str, DiscoveredGame] = {}  # key: host:port to avoid duplicates
        sock: Optional[socket.socket] = None

        try:
            # Create UDP socket for receiving broadcasts
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setblocking(False)

            try:
                sock.bind(('', DISCOVERY_PORT))
            except OSError:
                # Port might be in use, try binding to any available port
                sock.bind(('', 0))

            loop = asyncio.get_running_loop()
            end_time = loop.time() + timeout

            while loop.time() < end_time:
                remaining = end_time - loop.time()
                if remaining <= 0:
                    break

                try:
                    # Wait for data with timeout
                    data, addr = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: sock.recvfrom(BUFFER_SIZE)),
                        timeout=min(remaining, 0.5)
                    )

                    # Parse the broadcast message
                    try:
                        message = json.loads(data.decode('utf-8'))
                        if message.get("type") == "LOOT_RUN_GAME":
                            host = addr[0]
                            port = message.get("port", 8765)
                            key = f"{host}:{port}"

                            if key not in discovered:
                                discovered[key] = DiscoveredGame(
                                    host=host,
                                    port=port,
                                    game_name=message.get("game_name", "Unknown"),
                                    host_name=message.get("host_name", "Unknown"),
                                    player_count=message.get("player_count", 0),
                                    max_players=message.get("max_players", DEFAULT_MAX_PLAYERS),
                                )
                    except (json.JSONDecodeError, KeyError):
                        # Invalid message, ignore
                        pass

                except asyncio.TimeoutError:
                    # No data received in this interval, continue scanning
                    continue
                except BlockingIOError:
                    # No data available, wait a bit
                    await asyncio.sleep(0.1)
                except OSError:
                    # Socket error
                    break

        except OSError:
            # Failed to create socket
            pass
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

        return list(discovered.values())
