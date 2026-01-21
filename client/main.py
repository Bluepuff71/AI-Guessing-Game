# client/main.py
"""Main entry point for LOOT RUN terminal client."""

import asyncio
import sys
from typing import Optional

from client.connection import ConnectionManager
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from client import ui


class GameClient:
    """Main game client application."""

    def __init__(self):
        self.connection = ConnectionManager()
        self.state = GameState()
        self.handler = MessageHandler(self.state)
        self._running = False
        self._server_process = None

        # Set up callbacks
        self.handler.set_callbacks(
            on_phase_change=self._on_phase_change,
            on_round_result=self._on_round_result,
            on_escape_required=self._on_escape_required,
            on_escape_result=self._on_escape_result,
            on_game_over=self._on_game_over,
            on_player_update=self._on_player_update,
        )

    async def run(self):
        """Run the main client loop."""
        self._running = True

        while self._running:
            choice = ui.print_main_menu()

            if choice == "1":
                await self._play_single_player()
            elif choice == "2":
                await self._play_local_multiplayer()
            elif choice == "3":
                await self._host_online_game()
            elif choice == "4":
                await self._join_online_game()
            elif choice == "5":
                self._running = False

        await self._cleanup()

    async def _play_single_player(self):
        """Start single player game."""
        # Get player name
        ui.clear_screen()
        ui.print_header("Single Player")
        name = ui.get_input("Enter your name: ") or "Player"

        # Start local server and connect
        await self._start_local_server()
        if not await self._connect_to_server("localhost", 8765, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Set ready and wait for game
        await self.connection.send_ready()
        await self._game_loop()

    async def _play_local_multiplayer(self):
        """Start local multiplayer (hot-seat)."""
        ui.clear_screen()
        ui.print_header("Local Multiplayer")

        # Get number of players
        while True:
            try:
                num = int(ui.get_input("Number of players (2-6): "))
                if 2 <= num <= 6:
                    break
                ui.print_error("Please enter a number between 2 and 6")
            except ValueError:
                ui.print_error("Please enter a valid number")

        # Get player names
        names = []
        for i in range(num):
            name = ui.get_input(f"Player {i+1} name: ") or f"Player {i+1}"
            names.append(name)

        # Start local server
        await self._start_local_server()

        # Connect first player
        if not await self._connect_to_server("localhost", 8765, names[0]):
            return

        self.state.local_player_ids = [self.state.player_id]

        # For hot-seat, we track all players but use one connection
        # The server treats each "join" as a new player
        # We need to modify this for proper hot-seat...

        # For now, single connection handles multiple local players
        # Server needs modification to support this properly
        # This is a placeholder implementation

        await self.connection.send_ready()
        await self._game_loop()

    async def _host_online_game(self):
        """Host an online game."""
        ui.clear_screen()
        ui.print_header("Host Online Game")
        name = ui.get_input("Enter your name: ") or "Host"

        # Start local server exposed to network
        await self._start_local_server(expose=True)
        if not await self._connect_to_server("localhost", 8765, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Show lobby and wait for ready
        await self._lobby_loop(is_host=True)

    async def _join_online_game(self):
        """Join an online game."""
        ui.clear_screen()
        ui.print_header("Join Online Game")

        # Get server address
        host = ui.get_input("Server IP (or 'scan' for LAN): ") or "localhost"
        if host == "scan":
            # TODO: LAN discovery
            ui.print_info("LAN discovery not yet implemented. Using localhost.")
            host = "localhost"

        port = 8765
        port_str = ui.get_input("Port (default 8765): ")
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                pass

        name = ui.get_input("Enter your name: ") or "Player"

        if not await self._connect_to_server(host, port, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Show lobby and wait for game start
        await self._lobby_loop(is_host=False)

    async def _start_local_server(self, expose: bool = False):
        """Start local server subprocess."""
        import subprocess

        host = "0.0.0.0" if expose else "127.0.0.1"
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", host, "--port", "8765"],
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

        except Exception as e:
            ui.print_error(f"Failed to connect: {e}")
            return False

    async def _lobby_loop(self, is_host: bool):
        """Run lobby waiting loop."""
        self.state.phase = ClientPhase.LOBBY

        while self.state.phase == ClientPhase.LOBBY:
            ui.print_lobby(self.state, is_host)

            # Simple input handling
            inp = ui.get_input("> ").lower()

            if inp == "r":
                player = self.state.players.get(self.state.player_id)
                if player and player.ready:
                    await self.connection.send_unready()
                else:
                    await self.connection.send_ready()

            elif inp == "s" and is_host:
                # Start game (by setting ready, game auto-starts when all ready)
                await self.connection.send_ready()

            await asyncio.sleep(0.1)

        # Game started, enter game loop
        await self._game_loop()

    async def _game_loop(self):
        """Main game loop."""
        while self.state.phase not in [ClientPhase.GAME_OVER, ClientPhase.MAIN_MENU]:
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
        """Handle shop phase."""
        player = self.state.current_local_player
        if not player or not player.alive:
            await self.connection.send_skip_shop()
            return

        ui.print_shop(self.state, player)

        while self.state.phase == ClientPhase.SHOP:
            inp = ui.get_input("> ").lower()

            if inp == "skip" or inp == "s":
                await self.connection.send_skip_shop()
                break

            try:
                idx = int(inp) - 1
                if 0 <= idx < len(self.state.available_passives):
                    passive = self.state.available_passives[idx]
                    await self.connection.send_shop_purchase(passive.get("id"))
                    await asyncio.sleep(0.2)  # Wait for result
                    ui.print_shop(self.state, player)
            except ValueError:
                pass

    async def _handle_choosing_phase(self):
        """Handle location choosing phase."""
        # For each local player
        for i, pid in enumerate(self.state.local_player_ids):
            player = self.state.players.get(pid)
            if not player or not player.alive:
                continue

            self.state.current_local_player_index = i
            ui.print_location_choice_prompt(self.state, player)

            choice = ui.get_location_choice(len(self.state.locations))
            await self.connection.send_location_choice(choice)

            # If more players, clear screen for next
            if i < len(self.state.local_player_ids) - 1:
                ui.clear_screen()
                ui.print_info("Pass to next player...")
                ui.wait_for_enter()

    async def _on_round_result(self, results: dict):
        """Handle round results."""
        ui.print_round_results(self.state, results)
        ui.wait_for_enter()

    async def _on_escape_required(self, data: dict):
        """Handle escape phase."""
        player_id = data.get("player_id")
        player = self.state.players.get(player_id)
        if not player:
            return

        ui.print_escape_prompt(self.state, player)
        choice_idx = ui.get_escape_choice(len(self.state.escape_options))
        option_id = self.state.escape_options[choice_idx].get("id")
        await self.connection.send_escape_choice(option_id)

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
        await self.connection.disconnect()

        if self._server_process:
            self._server_process.terminate()
            self._server_process = None


def main():
    """Main entry point."""
    client = GameClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
