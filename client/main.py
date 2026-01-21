# client/main.py
"""Main entry point for LOOT RUN terminal client."""

import asyncio
import subprocess
import sys
from typing import Optional, Dict, List

from client.connection import ConnectionManager
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from client.lan import LANDiscovery, DISCOVERY_PORT
from client import ui

DEFAULT_PORT = 8765


class ConnectionLostError(Exception):
    """Raised when connection to server is lost."""
    pass


class GameClient:
    """Main game client application."""

    def __init__(self):
        self.connection = ConnectionManager()  # Primary connection
        self.state = GameState()
        self.handler = MessageHandler(self.state)
        self._running = False
        self._server_process = None
        self._connection_lost = False
        self._should_return_to_menu = False

        # Hot-seat support: map player_id -> connection
        # In hot-seat mode, each local player has their own connection to the server.
        # The primary connection (self.connection) is also stored here for the first player.
        # This allows uniform message routing via _local_connections.get(pid, self.connection).
        self._local_connections: Dict[str, ConnectionManager] = {}

        # LAN discovery
        self._lan_discovery = LANDiscovery()

        # Set up callbacks
        self.handler.set_callbacks(
            on_phase_change=self._on_phase_change,
            on_round_result=self._on_round_result,
            on_escape_required=self._on_escape_required,
            on_escape_result=self._on_escape_result,
            on_game_over=self._on_game_over,
            on_player_update=self._on_player_update,
        )

    def run(self):
        """Run the main client loop."""
        self._running = True

        while self._running:
            # Menu runs outside asyncio to avoid event loop conflicts with questionary
            choice = ui.print_main_menu()

            if choice == "1":
                asyncio.run(self._play_single_player())
            elif choice == "2":
                asyncio.run(self._play_local_multiplayer())
            elif choice == "3":
                asyncio.run(self._play_online_host())
            elif choice == "4":
                asyncio.run(self._play_online_join())
            elif choice == "5":
                self._running = False

    async def _play_online_host(self):
        """Wrapper for hosting online game with cleanup."""
        try:
            await self._host_online_game()
        finally:
            await self._cleanup()

    async def _play_online_join(self):
        """Wrapper for joining online game with cleanup."""
        try:
            await self._join_online_game()
        finally:
            await self._cleanup()

    def _stop_local_server(self):
        """Stop the local server subprocess if running."""
        if self._server_process:
            self._server_process.terminate()
            self._server_process = None

    async def _on_connection_lost(self):
        """Handle connection loss."""
        self._connection_lost = True
        self.state.connected = False

    def _reset_connection_state(self):
        """Reset connection-related state for a new game."""
        self._connection_lost = False
        self._should_return_to_menu = False

    async def _handle_connection_error(self, context: str = "operation"):
        """Handle a connection error, show message and cleanup.

        Returns True if user wants to return to menu.
        """
        ui.clear_screen()
        ui.print_error(f"Connection lost during {context}.")
        ui.print_info("The server may have closed or network issues occurred.")
        ui.print_info("Press Enter to return to main menu...")
        ui.wait_for_enter()
        await self._cleanup_current_game()
        return True

    async def _cleanup_current_game(self):
        """Clean up current game resources without exiting."""
        # Disconnect all local connections (for hot-seat)
        for conn in self._local_connections.values():
            if conn != self.connection:
                try:
                    await conn.disconnect()
                except Exception:
                    pass
        self._local_connections.clear()

        try:
            await self.connection.disconnect()
        except Exception:
            pass

        self._stop_local_server()
        self.state.reset_for_new_game()
        self._reset_connection_state()

    async def _safe_send(self, conn: ConnectionManager, send_coro) -> bool:
        """Safely send a message, handling connection errors.

        Returns True if send succeeded, False if connection was lost.
        """
        try:
            await send_coro
            return True
        except RuntimeError as e:
            if "Not connected" in str(e):
                return False
            raise
        except Exception:
            return False

    async def _play_single_player(self):
        """Start single player game."""
        self.state.reset_for_new_game()
        self._reset_connection_state()

        # Get player name
        ui.clear_screen()
        ui.print_header("Single Player")
        name = ui.get_player_name(1)

        # Start local server and connect
        await self._start_local_server()
        if not await self._connect_to_server("localhost", DEFAULT_PORT, name):
            self._stop_local_server()
            return

        self.state.local_player_ids = [self.state.player_id]

        # Set ready and wait for game
        try:
            if not await self._safe_send(self.connection, self.connection.send_ready()):
                await self._handle_connection_error("game start")
                return
            await self._game_loop()
        except ConnectionLostError:
            await self._handle_connection_error("game")
        finally:
            await self._cleanup_current_game()

    async def _play_local_multiplayer(self):
        """Start local multiplayer (hot-seat)."""
        self.state.reset_for_new_game()
        self._reset_connection_state()
        self._local_connections.clear()

        ui.clear_screen()
        ui.print_header("Local Multiplayer")

        # Get number of players
        num = ui.get_player_count()

        # Get player names
        names = []
        for i in range(num):
            name = ui.get_player_name(i + 1)
            names.append(name)

        # Start local server
        await self._start_local_server()

        # Connect first player (primary connection receives state updates)
        if not await self._connect_to_server("localhost", DEFAULT_PORT, names[0]):
            self._stop_local_server()
            return

        first_player_id = self.state.player_id
        self.state.local_player_ids = [first_player_id]
        self._local_connections[first_player_id] = self.connection

        # Connect additional players for hot-seat
        connection_failed = False
        for i in range(1, num):
            player_id = await self._connect_additional_player("localhost", DEFAULT_PORT, names[i])
            if player_id:
                self.state.local_player_ids.append(player_id)
            else:
                connection_failed = True
                ui.print_error(f"Failed to connect all players. Aborting.")
                break

        # If any connection failed, clean up and abort
        if connection_failed:
            for conn in self._local_connections.values():
                try:
                    await conn.disconnect()
                except Exception:
                    pass
            self._local_connections.clear()
            self._stop_local_server()
            return

        # Mark all local player_ids as local in state
        for pid in self.state.local_player_ids:
            if pid in self.state.players:
                self.state.players[pid].is_local = True

        ui.print_info(f"All {num} players connected!")
        await asyncio.sleep(0.5)

        # All players ready up
        try:
            for pid, conn in self._local_connections.items():
                if not await self._safe_send(conn, conn.send_ready()):
                    await self._handle_connection_error("game start")
                    return

            await self._game_loop()
        except ConnectionLostError:
            await self._handle_connection_error("game")
        finally:
            await self._cleanup_current_game()

    async def _host_online_game(self):
        """Host an online game."""
        self.state.reset_for_new_game()
        self._reset_connection_state()
        ui.clear_screen()
        ui.print_header("Host Online Game")
        name = ui.get_host_name()
        game_name = ui.get_game_name()

        # Start local server exposed to network
        ui.print_info("Starting server...")
        await self._start_local_server(expose=True)

        # Give server more time to start
        await asyncio.sleep(1.0)

        if not await self._connect_to_server("localhost", DEFAULT_PORT, name):
            ui.print_error("Failed to connect to local server. Please try again.")
            ui.wait_for_enter()
            self._stop_local_server()
            return

        self.state.local_player_ids = [self.state.player_id]

        # Start LAN broadcasting
        broadcasting = await self._lan_discovery.start_broadcasting(
            port=DEFAULT_PORT,
            game_name=game_name,
            host_name=name,
            player_count=1,
            max_players=6
        )
        if broadcasting:
            ui.print_info(f"Broadcasting game on LAN (port {DISCOVERY_PORT})")

        try:
            # Show lobby and wait for ready
            await self._lobby_loop(is_host=True)
        except ConnectionLostError:
            await self._handle_connection_error("lobby")
        finally:
            # Stop broadcasting when done
            await self._lan_discovery.stop_broadcasting()
            await self._cleanup_current_game()

    async def _join_online_game(self):
        """Join an online game."""
        self.state.reset_for_new_game()
        self._reset_connection_state()
        ui.clear_screen()
        ui.print_header("Join Online Game")

        # Get server address
        host = ui.get_server_address()
        port = DEFAULT_PORT

        if host.lower() == "scan":
            # LAN discovery
            ui.print_info("Scanning for LAN games...")
            games = await self._lan_discovery.scan_for_games(timeout=3.0)

            if not games:
                ui.print_error("No games found on LAN.")
                ui.wait_for_enter()
                return
            else:
                # Let user select a game
                idx = ui.select_lan_game(games)
                if idx is None:
                    return  # User cancelled
                selected = games[idx]
                host = selected.host
                port = selected.port

        name = ui.get_player_name(1)

        if not await self._connect_to_server(host, port, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Show lobby and wait for game start
        try:
            await self._lobby_loop(is_host=False)
        except ConnectionLostError:
            await self._handle_connection_error("lobby")
        finally:
            await self._cleanup_current_game()

    async def _start_local_server(self, expose: bool = False):
        """Start local server subprocess."""
        host = "0.0.0.0" if expose else "127.0.0.1"
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", host, "--port", str(DEFAULT_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for server to start
        await asyncio.sleep(0.5)

    async def _connect_to_server(self, host: str, port: int, username: str) -> bool:
        """Connect to game server."""
        ui.print_connecting(host, port)

        try:
            await self.connection.connect(f"ws://{host}:{port}")
            self.connection.set_message_handler(self.handler.handle)
            self.connection.set_on_disconnect(self._on_connection_lost)
            await self.connection.start_receiving()

            await self.connection.send_join(username)

            # Wait for welcome
            for _ in range(50):  # 5 second timeout
                await asyncio.sleep(0.1)
                if self.state.connected and self.state.player_id:
                    ui.print_info(f"Connected! Game ID: {self.state.game_id}")
                    return True

            ui.print_error("Connection timeout")
            return False

        except ConnectionError as e:
            ui.print_error(f"Failed to connect: {e}")
            return False
        except Exception as e:
            ui.print_error(f"Failed to connect: {e}")
            return False

    async def _connect_additional_player(self, host: str, port: int, username: str) -> Optional[str]:
        """Connect an additional player for hot-seat mode.

        Returns the player_id if successful, None otherwise.
        """
        conn = ConnectionManager()

        # Temporary state to capture this player's ID
        temp_player_id = None

        async def capture_welcome(msg):
            nonlocal temp_player_id
            if msg.type == "WELCOME":
                temp_player_id = msg.data.get("player_id")
            # Also pass to main handler to update player list
            await self.handler.handle(msg)

        try:
            await conn.connect(f"ws://{host}:{port}")
            conn.set_message_handler(capture_welcome)
            await conn.start_receiving()

            await conn.send_join(username)

            # Wait for welcome
            for _ in range(50):  # 5 second timeout
                await asyncio.sleep(0.1)
                if temp_player_id:
                    self._local_connections[temp_player_id] = conn
                    ui.print_info(f"  {username} connected!")
                    return temp_player_id

            ui.print_error(f"Timeout connecting {username}")
            await conn.disconnect()
            return None

        except Exception as e:
            ui.print_error(f"Failed to connect {username}: {e}")
            await conn.disconnect()  # Ensure cleanup on exception
            return None

    async def _lobby_loop(self, is_host: bool):
        """Run lobby waiting loop."""
        self.state.phase = ClientPhase.LOBBY

        while self.state.phase == ClientPhase.LOBBY:
            # Check for connection loss
            if self._connection_lost:
                raise ConnectionLostError("Connection lost in lobby")

            ui.print_lobby(self.state, is_host)

            # Simple input handling
            inp = ui.get_input("> ").lower()

            if inp == "r":
                player = self.state.players.get(self.state.player_id)
                if player and player.ready:
                    if not await self._safe_send(self.connection, self.connection.send_unready()):
                        raise ConnectionLostError("Connection lost while updating ready status")
                else:
                    if not await self._safe_send(self.connection, self.connection.send_ready()):
                        raise ConnectionLostError("Connection lost while updating ready status")

            elif inp == "s" and is_host:
                # Start game (by setting ready, game auto-starts when all ready)
                if not await self._safe_send(self.connection, self.connection.send_ready()):
                    raise ConnectionLostError("Connection lost while starting game")

            await asyncio.sleep(0.1)

        # Game started, enter game loop
        await self._game_loop()

    async def _game_loop(self):
        """Main game loop."""
        while self.state.phase not in [ClientPhase.GAME_OVER, ClientPhase.MAIN_MENU]:
            # Check for connection loss
            if self._connection_lost:
                raise ConnectionLostError("Connection lost during game")
            await asyncio.sleep(0.1)

        # Show game over and return
        if self.state.phase == ClientPhase.GAME_OVER:
            ui.print_game_over(self.state)
            ui.wait_for_enter()

    async def _on_phase_change(self, phase: ClientPhase):
        """Handle phase change."""
        if phase == ClientPhase.SHOP:
            await self._handle_shop_phase()
        elif phase == ClientPhase.CHOOSING:
            await self._handle_choosing_phase()

    async def _handle_shop_phase(self):
        """Handle shop phase for all local players."""
        # For hot-seat, each local player gets a shop turn
        for i, pid in enumerate(self.state.local_player_ids):
            # Check for connection loss
            if self._connection_lost:
                raise ConnectionLostError("Connection lost during shop phase")

            player = self.state.players.get(pid)
            conn = self._local_connections.get(pid, self.connection)

            if not player or not player.alive:
                if not await self._safe_send(conn, conn.send_skip_shop()):
                    raise ConnectionLostError("Connection lost during shop phase")
                continue

            # If multiple players, clear screen between turns
            if i > 0:
                ui.clear_screen()
                ui.print_info(f"{player.username}'s turn to shop...")
                ui.wait_for_enter()

            self.state.current_local_player_index = i
            ui.print_shop(self.state, player)

            # Shop loop for this player
            shopping = True
            while shopping and self.state.phase == ClientPhase.SHOP:
                if self._connection_lost:
                    raise ConnectionLostError("Connection lost during shop phase")

                inp = ui.get_input("> ").lower()

                if inp == "skip" or inp == "s":
                    if not await self._safe_send(conn, conn.send_skip_shop()):
                        raise ConnectionLostError("Connection lost during shop phase")
                    shopping = False

                else:
                    try:
                        idx = int(inp) - 1
                        if 0 <= idx < len(self.state.available_passives):
                            passive = self.state.available_passives[idx]
                            if not await self._safe_send(conn, conn.send_shop_purchase(passive.get("id"))):
                                raise ConnectionLostError("Connection lost during shop phase")
                            await asyncio.sleep(0.2)  # Wait for result
                            ui.print_shop(self.state, player)
                    except ValueError:
                        pass

    async def _handle_choosing_phase(self):
        """Handle location choosing phase for all local players.

        Collects all choices first, then sends them together.
        This prevents the server from seeing partial submissions.
        """
        # Check for connection loss
        if self._connection_lost:
            raise ConnectionLostError("Connection lost during choosing phase")

        # Collect choices from all local players
        choices: Dict[str, int] = {}  # player_id -> location choice

        for i, pid in enumerate(self.state.local_player_ids):
            if self._connection_lost:
                raise ConnectionLostError("Connection lost during choosing phase")

            player = self.state.players.get(pid)

            if not player or not player.alive:
                continue

            # If multiple players, clear screen between turns
            if i > 0:
                ui.clear_screen()
                ui.print_info(f"Pass to {player.username}...")
                ui.wait_for_enter()

            self.state.current_local_player_index = i
            ui.print_location_choice_prompt(self.state, player)

            choice = ui.get_location_choice(self.state)
            choices[pid] = choice

        # All choices collected - now send them all
        for pid, choice in choices.items():
            conn = self._local_connections.get(pid, self.connection)
            if not await self._safe_send(conn, conn.send_location_choice(choice)):
                raise ConnectionLostError("Connection lost while submitting choices")

    async def _on_round_result(self, results: dict):
        """Handle round results."""
        ui.print_round_results(self.state, results)
        ui.wait_for_enter()

    async def _on_escape_required(self, data: dict):
        """Handle escape phase for a caught player."""
        if self._connection_lost:
            raise ConnectionLostError("Connection lost during escape phase")

        player_id = data.get("player_id")
        player = self.state.players.get(player_id)
        if not player:
            return

        # Use the correct connection for this player
        conn = self._local_connections.get(player_id, self.connection)

        ui.print_escape_prompt(self.state, player)
        choice_idx = ui.get_escape_choice(self.state)
        option_id = self.state.escape_options[choice_idx].get("id")
        if not await self._safe_send(conn, conn.send_escape_choice(option_id)):
            raise ConnectionLostError("Connection lost while submitting escape choice")

    async def _on_escape_result(self, result: dict):
        """Handle escape result."""
        ui.print_escape_result(result)
        ui.wait_for_enter()

    async def _on_game_over(self):
        """Handle game over."""
        self.state.phase = ClientPhase.GAME_OVER

    async def _on_player_update(self):
        """Handle player list update."""
        # Could refresh lobby display
        pass

    async def _cleanup(self):
        """Clean up resources."""
        # Disconnect all local connections (for hot-seat)
        for conn in self._local_connections.values():
            if conn != self.connection:  # Don't disconnect primary twice
                await conn.disconnect()
        self._local_connections.clear()

        await self.connection.disconnect()

        if self._server_process:
            self._server_process.terminate()
            self._server_process = None


def main():
    """Main entry point."""
    client = GameClient()
    try:
        client.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
