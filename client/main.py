# client/main.py
"""Main entry point for LOOT RUN terminal client.

This client uses a synchronous main thread with NetworkThread for async network I/O.
This allows questionary UI to work without asyncio conflicts.
"""

import asyncio
import subprocess
import sys
import threading
import time
from typing import Optional, Dict, List

from client.network_thread import NetworkThread
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from client.lan import LANDiscovery, DISCOVERY_PORT
from client import ui
from game.animations import play_elimination_animation, play_escape_animation
from utils.process import wait_for_server, is_server_running
from version import VERSION


def _is_frozen() -> bool:
    """Check if running from a PyInstaller bundled executable."""
    return getattr(sys, 'frozen', False)

DEFAULT_PORT = 8765

# Polling configuration
POLL_TIMEOUT = 0.1  # seconds
CONNECTION_TIMEOUT = 5.0  # seconds


class GameClient:
    """Main game client application.

    Architecture:
    - Main thread runs synchronously, handling all UI via questionary
    - NetworkThread runs in background, handling all network I/O
    - Communication via queues (poll incoming, send outgoing)
    """

    def __init__(self):
        self.state = GameState()
        self.handler = MessageHandler(self.state)
        self._running = False
        self._server_process = None  # For subprocess mode (non-frozen)
        self._server_thread = None   # For in-process mode (frozen exe)
        self._server_stop_event = None  # Event to signal server shutdown
        self._connection_lost = False

        # Hot-seat support: map player_id -> NetworkThread
        # Each local player has their own network connection to the server.
        self._local_networks: Dict[str, NetworkThread] = {}

        # Primary network connection (first player)
        self._network: Optional[NetworkThread] = None

        # LAN discovery (still uses asyncio internally but wrapped)
        self._lan_discovery = LANDiscovery()

    def run(self):
        """Run the main client loop."""
        self._running = True

        while self._running:
            choice = ui.print_main_menu()

            if choice == "1":
                self._play_single_player()
            elif choice == "2":
                self._play_local_multiplayer()
            elif choice == "3":
                self._play_online_host()
            elif choice == "4":
                self._play_online_join()
            elif choice == "5":
                self._running = False

    def _play_single_player(self):
        """Start single player game."""
        self.state.reset_for_new_game()
        self._reset_connection_state()

        # Get player name
        ui.clear_screen()
        ui.print_header("Single Player")
        name = ui.get_player_name(1)

        # Start local server and connect
        if not self._start_local_server():
            ui.wait_for_enter()
            return

        network = NetworkThread()
        if not self._connect_and_join(network, "localhost", DEFAULT_PORT, name):
            network.stop()
            self._stop_local_server()
            return

        self._network = network
        self.state.local_player_ids = [self.state.player_id]
        self._local_networks[self.state.player_id] = network

        # Set ready and wait for game
        network.send("READY", {})

        # Enter game loop
        self._game_loop()

        # Cleanup
        self._cleanup_current_game()

    def _play_local_multiplayer(self):
        """Start local multiplayer (hot-seat)."""
        self.state.reset_for_new_game()
        self._reset_connection_state()
        self._local_networks.clear()

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
        if not self._start_local_server():
            ui.wait_for_enter()
            return

        # Connect first player (primary connection receives state updates)
        network = NetworkThread()
        if not self._connect_and_join(network, "localhost", DEFAULT_PORT, names[0]):
            network.stop()
            self._stop_local_server()
            return

        self._network = network
        first_player_id = self.state.player_id
        self.state.local_player_ids = [first_player_id]
        self._local_networks[first_player_id] = network

        # Connect additional players for hot-seat
        connection_failed = False
        for i in range(1, num):
            player_id = self._connect_additional_player("localhost", DEFAULT_PORT, names[i])
            if player_id:
                self.state.local_player_ids.append(player_id)
            else:
                connection_failed = True
                ui.print_error("Failed to connect all players. Aborting.")
                break

        if connection_failed:
            self._cleanup_current_game()
            return

        # Mark all local player_ids as local in state
        for pid in self.state.local_player_ids:
            if pid in self.state.players:
                self.state.players[pid].is_local = True

        ui.print_info(f"All {num} players connected!")
        time.sleep(0.5)

        # All players ready up
        for pid, net in self._local_networks.items():
            net.send("READY", {})

        # Enter game loop
        self._game_loop()

        # Cleanup
        self._cleanup_current_game()

    def _play_online_host(self):
        """Host an online game."""
        self.state.reset_for_new_game()
        self._reset_connection_state()

        ui.clear_screen()
        ui.print_header("Host Online Game")
        name = ui.get_host_name()
        game_name = ui.get_game_name()

        # Start local server exposed to network
        ui.print_info("Starting server...")
        if not self._start_local_server(expose=True):
            ui.wait_for_enter()
            return

        network = NetworkThread()
        if not self._connect_and_join(network, "localhost", DEFAULT_PORT, name):
            network.stop()
            ui.print_error("Failed to connect to local server. Please try again.")
            ui.wait_for_enter()
            self._stop_local_server()
            return

        self._network = network
        self.state.local_player_ids = [self.state.player_id]
        self._local_networks[self.state.player_id] = network

        # Start LAN broadcasting (uses asyncio internally)
        broadcasting = asyncio.run(self._lan_discovery.start_broadcasting(
            port=DEFAULT_PORT,
            game_name=game_name,
            host_name=name,
            player_count=1,
            max_players=6
        ))
        if broadcasting:
            ui.print_info(f"Broadcasting game on LAN (port {DISCOVERY_PORT})")

        try:
            # Show lobby and wait for ready
            self._lobby_loop(is_host=True)
        finally:
            # Stop broadcasting when done
            asyncio.run(self._lan_discovery.stop_broadcasting())
            self._cleanup_current_game()

    def _play_online_join(self):
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
            games = asyncio.run(self._lan_discovery.scan_for_games(timeout=3.0))

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

        network = NetworkThread()
        if not self._connect_and_join(network, host, port, name):
            network.stop()
            return

        self._network = network
        self.state.local_player_ids = [self.state.player_id]
        self._local_networks[self.state.player_id] = network

        # Show lobby and wait for game start
        try:
            self._lobby_loop(is_host=False)
        finally:
            self._cleanup_current_game()

    def _start_local_server(self, expose: bool = False) -> bool:
        """Start local server.

        When running from source (not frozen), spawns server as subprocess.
        When running from PyInstaller bundle (frozen), runs server in background thread.

        Args:
            expose: If True, bind to 0.0.0.0 (network accessible).
                   If False, bind to 127.0.0.1 (localhost only).

        Returns:
            True if server started successfully, False otherwise.
        """
        # Check if a server is already running on this port
        if is_server_running(DEFAULT_PORT):
            ui.print_error(f"A server is already running on port {DEFAULT_PORT}.")
            ui.print_info("This could be from a previous game session.")
            ui.print_info("Please close any existing LOOT RUN servers and try again.")
            return False

        host = "0.0.0.0" if expose else "127.0.0.1"

        if _is_frozen():
            # Running from PyInstaller bundle - run server in background thread
            return self._start_server_in_thread(host)
        else:
            # Running from source - spawn as subprocess
            return self._start_server_subprocess(host)

    def _start_server_in_thread(self, host: str) -> bool:
        """Start server in a background thread (for frozen exe mode)."""
        from server.main import GameServer

        self._server_stop_event = threading.Event()

        def run_server():
            """Server thread function."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            server = GameServer(host=host, port=DEFAULT_PORT)

            async def serve_until_stopped():
                """Run server until stop event is set."""
                import websockets
                async with websockets.serve(
                    server.handle_connection, server.host, server.port,
                    reuse_address=True
                ):
                    # Check stop event periodically
                    while not self._server_stop_event.is_set():
                        await asyncio.sleep(0.1)

            try:
                loop.run_until_complete(serve_until_stopped())
            except Exception:
                pass
            finally:
                loop.close()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        # Wait for server to start accepting connections
        if not wait_for_server(DEFAULT_PORT, timeout=5.0):
            ui.print_error("Server did not start in time.")
            self._server_stop_event.set()
            self._server_thread = None
            self._server_stop_event = None
            return False

        return True

    def _start_server_subprocess(self, host: str) -> bool:
        """Start server as subprocess (for non-frozen mode)."""
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", host, "--port", str(DEFAULT_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start accepting connections
        if not wait_for_server(DEFAULT_PORT, timeout=5.0):
            # Server didn't start - check if process is still running
            poll_result = self._server_process.poll()
            if poll_result is not None:
                # Process exited - try to get error message
                try:
                    stdout, stderr = self._server_process.communicate(timeout=1)
                    error_output = stdout.decode().strip() if stdout else ""
                    if "already running" in error_output.lower():
                        ui.print_error("Another LOOT RUN server is already running.")
                    else:
                        ui.print_error(f"Server failed to start: {error_output}")
                except Exception:
                    ui.print_error("Server process exited unexpectedly.")
            else:
                ui.print_error("Server did not start in time.")
                self._server_process.terminate()
            self._server_process = None
            return False

        return True

    def _stop_local_server(self):
        """Stop the local server (subprocess or thread) if running."""
        # Stop thread-based server (frozen mode)
        if self._server_thread:
            if self._server_stop_event:
                self._server_stop_event.set()
            # Give thread time to stop gracefully
            self._server_thread.join(timeout=2.0)
            self._server_thread = None
            self._server_stop_event = None

        # Stop subprocess-based server (non-frozen mode)
        if self._server_process:
            self._server_process.terminate()
            try:
                # Wait for process to actually exit
                self._server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                self._server_process.kill()
                self._server_process.wait()
            self._server_process = None

    def _reset_connection_state(self):
        """Reset connection-related state for a new game."""
        self._connection_lost = False

    def _connect_and_join(self, network: NetworkThread, host: str, port: int, username: str) -> bool:
        """Connect to server and join the game.

        Args:
            network: NetworkThread to use for connection
            host: Server hostname
            port: Server port
            username: Player username

        Returns:
            True if connection and join succeeded, False otherwise.
        """
        ui.print_connecting(host, port)

        # Start the network thread
        if not network.start(f"ws://{host}:{port}"):
            ui.print_error("Failed to start network thread")
            return False

        # Wait for connection
        start_time = time.time()
        connected = False
        while time.time() - start_time < CONNECTION_TIMEOUT:
            msg = network.poll(timeout=POLL_TIMEOUT)
            if msg:
                if msg["type"] == "CONNECTED":
                    connected = True
                    break
                elif msg["type"] == "CONNECTION_LOST":
                    ui.print_error(f"Connection failed: {msg.get('error', 'Unknown error')}")
                    return False

        if not connected:
            ui.print_error("Connection timeout")
            return False

        # Send JOIN message
        network.send("JOIN", {"username": username, "version": VERSION})

        # Wait for WELCOME response
        start_time = time.time()
        while time.time() - start_time < CONNECTION_TIMEOUT:
            msg = network.poll(timeout=POLL_TIMEOUT)
            if msg:
                if msg["type"] == "SERVER_MESSAGE":
                    self.handler.handle(msg["message_type"], msg["data"])
                    if self.state.connected and self.state.player_id:
                        ui.print_info(f"Connected! Game ID: {self.state.game_id}")
                        return True
                elif msg["type"] == "CONNECTION_LOST":
                    ui.print_error(f"Connection lost: {msg.get('error', 'Unknown error')}")
                    return False

        ui.print_error("Connection timeout waiting for welcome")
        return False

    def _connect_additional_player(self, host: str, port: int, username: str) -> Optional[str]:
        """Connect an additional player for hot-seat mode.

        Returns the player_id if successful, None otherwise.
        """
        network = NetworkThread()

        if not network.start(f"ws://{host}:{port}"):
            ui.print_error(f"Failed to start network for {username}")
            return None

        # Wait for connection
        start_time = time.time()
        connected = False
        while time.time() - start_time < CONNECTION_TIMEOUT:
            msg = network.poll(timeout=POLL_TIMEOUT)
            if msg:
                if msg["type"] == "CONNECTED":
                    connected = True
                    break
                elif msg["type"] == "CONNECTION_LOST":
                    ui.print_error(f"Connection failed for {username}")
                    network.stop()
                    return None

        if not connected:
            ui.print_error(f"Connection timeout for {username}")
            network.stop()
            return None

        # Send JOIN message
        network.send("JOIN", {"username": username, "version": VERSION})

        # Wait for WELCOME response
        # We need to capture the player_id from WELCOME for this player specifically
        start_time = time.time()
        temp_player_id = None
        while time.time() - start_time < CONNECTION_TIMEOUT:
            msg = network.poll(timeout=POLL_TIMEOUT)
            if msg:
                if msg["type"] == "SERVER_MESSAGE":
                    if msg["message_type"] == "WELCOME":
                        temp_player_id = msg["data"].get("player_id")
                    # Also pass to main handler to update player list
                    self.handler.handle(msg["message_type"], msg["data"])

                    if temp_player_id:
                        self._local_networks[temp_player_id] = network
                        ui.print_info(f"  {username} connected!")
                        return temp_player_id

                elif msg["type"] == "CONNECTION_LOST":
                    ui.print_error(f"Connection lost for {username}")
                    network.stop()
                    return None

        ui.print_error(f"Timeout connecting {username}")
        network.stop()
        return None

    def _poll_all_networks(self):
        """Poll all network threads and process ALL pending messages.

        Returns True if connection is still good, False if connection lost.
        """
        # Poll primary network - drain all pending messages
        if self._network:
            while True:
                msg = self._network.poll(timeout=POLL_TIMEOUT)
                if not msg:
                    break
                if msg["type"] == "SERVER_MESSAGE":
                    self.handler.handle(msg["message_type"], msg["data"])
                elif msg["type"] == "CONNECTION_LOST":
                    self._connection_lost = True
                    return False

        # Poll additional networks (for hot-seat) - drain all pending messages
        for pid, network in self._local_networks.items():
            if network == self._network:
                continue  # Already polled

            while True:
                msg = network.poll(timeout=0.01)  # Quick poll for secondary connections
                if not msg:
                    break
                if msg["type"] == "SERVER_MESSAGE":
                    # Secondary connections mainly care about WELCOME and escape phases
                    if msg["message_type"] in ("WELCOME", "ESCAPE_PHASE", "ESCAPE_RESULT"):
                        self.handler.handle(msg["message_type"], msg["data"])
                elif msg["type"] == "CONNECTION_LOST":
                    # A secondary connection lost - could handle differently
                    pass

        return True

    def _lobby_loop(self, is_host: bool):
        """Run lobby waiting loop."""
        self.state.phase = ClientPhase.LOBBY

        while self.state.phase == ClientPhase.LOBBY:
            # Poll for messages
            if not self._poll_all_networks():
                ui.clear_screen()
                ui.print_error("Connection lost in lobby.")
                ui.print_info("Press Enter to return to main menu...")
                ui.wait_for_enter()
                return

            # Check if phase changed (game started by server)
            if self.state.phase != ClientPhase.LOBBY:
                break

            ui.print_lobby(self.state, is_host)

            # Get player's ready state
            player = self.state.players.get(self.state.player_id)
            is_ready = player.ready if player else False

            # Get lobby action using questionary menu
            action = ui.get_lobby_action(is_host, is_ready)

            if action == "ready":
                self._network.send("READY", {})
            elif action == "unready":
                self._network.send("UNREADY", {})
            elif action == "start" and is_host:
                # Start game (by setting ready, game auto-starts when all ready)
                self._network.send("READY", {})
            # "refresh" action just continues the loop to poll and redraw

            # Small delay to avoid spinning
            time.sleep(0.1)

        # Game started, enter game loop
        self._game_loop()

    def _game_loop(self):
        """Main game loop."""
        while self.state.phase not in [ClientPhase.GAME_OVER, ClientPhase.MAIN_MENU]:
            # Poll for messages
            if not self._poll_all_networks():
                ui.clear_screen()
                ui.print_error("Connection lost during game.")
                ui.print_info("Press Enter to return to main menu...")
                ui.wait_for_enter()
                return

            # Handle events from handler
            # IMPORTANT: Process escape results BEFORE phase changes (shop/choosing)
            # to ensure escape outcome is shown before the next round's shop appears.
            # This fixes a bug where SHOP_STATE and ESCAPE_RESULT arriving in the
            # same poll cycle would show the shop before the escape result.

            if self.handler.last_round_result:
                result = self.handler.last_round_result
                self.handler.last_round_result = None
                ui.print_round_results(self.state, result)
                ui.wait_for_enter()

            if self.handler.last_escape_required:
                data = self.handler.last_escape_required
                self.handler.last_escape_required = None
                self._handle_escape_phase(data)

            if self.handler.last_escape_result:
                result = self.handler.last_escape_result
                self.handler.last_escape_result = None
                # Play animation based on escape result
                if result.get("escaped"):
                    play_escape_animation()
                else:
                    play_elimination_animation()
                ui.print_escape_result(result)
                ui.wait_for_enter()

            # Process phase changes (shop/choosing) AFTER escape-related events
            if self.handler.phase_changed:
                self.handler.phase_changed = False
                if self.state.phase == ClientPhase.SHOP:
                    self._handle_shop_phase()
                elif self.state.phase == ClientPhase.CHOOSING:
                    self._handle_choosing_phase()

            # Small delay to avoid spinning
            time.sleep(0.05)

        # Show game over and return
        if self.state.phase == ClientPhase.GAME_OVER:
            ui.print_game_over(self.state)
            ui.wait_for_enter()

    def _handle_shop_phase(self):
        """Handle shop phase for all local players."""
        # For hot-seat, each local player gets a shop turn
        for i, pid in enumerate(self.state.local_player_ids):
            # Check for connection loss
            if self._connection_lost:
                return

            player = self.state.players.get(pid)
            network = self._local_networks.get(pid, self._network)

            if not player or not player.alive:
                network.send("SKIP_SHOP", {})
                continue

            # If multiple players, clear screen between turns
            if i > 0:
                ui.clear_screen()
                ui.print_info(f"{player.username}'s turn to shop...")
                ui.wait_for_enter()

            self.state.current_local_player_index = i
            ui.print_shop(self.state, player)

            # Shop using questionary
            choice = ui.get_shop_choice(self.state, player)

            if choice is None:
                # Skip shop
                network.send("SKIP_SHOP", {})
            else:
                # Purchase selected passive
                passive = self.state.available_passives[choice]
                network.send("SHOP_PURCHASE", {"passive_id": passive.get("id")})

                # Wait briefly for purchase result
                time.sleep(0.2)

                # Poll to process purchase result
                self._poll_all_networks()

                # Show updated shop
                ui.print_shop(self.state, player)
                ui.wait_for_enter()

                # Now skip to continue
                network.send("SKIP_SHOP", {})

    def _handle_choosing_phase(self):
        """Handle location choosing phase for all local players.

        Collects all choices first, then sends them together.
        This prevents the server from seeing partial submissions.
        """
        # Check for connection loss
        if self._connection_lost:
            return

        # Collect choices from all local players
        choices: Dict[str, int] = {}  # player_id -> location choice

        for i, pid in enumerate(self.state.local_player_ids):
            if self._connection_lost:
                return

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
            network = self._local_networks.get(pid, self._network)
            network.send("LOCATION_CHOICE", {"location_index": choice})

    def _handle_escape_phase(self, data: dict):
        """Handle escape phase for a caught player."""
        if self._connection_lost:
            return

        player_id = data.get("player_id")
        player = self.state.players.get(player_id)
        if not player:
            return

        # Use the correct network for this player
        network = self._local_networks.get(player_id, self._network)

        ui.print_escape_prompt(self.state, player)
        choice_idx = ui.get_escape_choice(self.state)
        option_id = self.state.escape_options[choice_idx].get("id")
        network.send("ESCAPE_CHOICE", {"option_id": option_id})

    def _cleanup_current_game(self):
        """Clean up current game resources without exiting."""
        # Stop all network threads
        for network in self._local_networks.values():
            network.stop()
        self._local_networks.clear()

        if self._network:
            # Already stopped via _local_networks
            self._network = None

        self._stop_local_server()
        self.state.reset_for_new_game()
        self._reset_connection_state()
        self.handler.clear_events()
