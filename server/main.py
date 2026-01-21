"""
WebSocket server entry point for LOOT RUN multiplayer.

This module provides:
- WebSocket server using websockets library
- Game lobby management
- Message routing to game engine
- Connection handling and reconnection support
"""

import asyncio
import json
import uuid
import argparse
from typing import Dict, Set, Optional
from dataclasses import dataclass, field

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None

from server.protocol import (
    Message, ClientMessageType, ServerMessageType,
    welcome_message, error_message, lobby_state_message,
    player_joined_message, player_left_message, player_ready_message,
    parse_join_message, parse_reconnect_message, parse_location_choice_message,
    parse_escape_choice_message, parse_shop_purchase_message
)
from server.engine import ServerGameEngine
from version import VERSION


@dataclass
class ConnectedClient:
    """Represents a connected WebSocket client."""
    websocket: WebSocketServerProtocol
    player_id: str
    username: str
    game_id: Optional[str] = None


class GameServer:
    """
    WebSocket game server managing multiple game lobbies.

    Handles:
    - Client connections and disconnections
    - Game lobby creation and joining
    - Message routing to game engines
    - Reconnection support
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port

        # Connection tracking
        self.clients: Dict[str, ConnectedClient] = {}  # player_id -> client
        self.websocket_to_player: Dict[WebSocketServerProtocol, str] = {}

        # Game management
        self.games: Dict[str, ServerGameEngine] = {}  # game_id -> engine
        self.player_to_game: Dict[str, str] = {}  # player_id -> game_id

        # Lobby (players waiting to be matched or creating games)
        self.lobby_players: Set[str] = set()

    async def start(self):
        """Start the WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            print("ERROR: websockets library not installed.")
            print("Install with: pip install websockets")
            return

        print(f"Starting LOOT RUN server on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handle_connection, self.host, self.port):
            await asyncio.Future()  # Run forever

    async def handle_connection(self, websocket: WebSocketServerProtocol):
        """Handle a new WebSocket connection."""
        player_id = str(uuid.uuid4())
        print(f"New connection: {player_id}")

        try:
            async for message in websocket:
                await self.handle_message(websocket, player_id, message)
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed: {player_id}")
        finally:
            await self.handle_disconnect(player_id)

    async def handle_message(self, websocket: WebSocketServerProtocol, player_id: str, raw_message: str):
        """Handle an incoming message."""
        try:
            msg = Message.from_json(raw_message)
        except json.JSONDecodeError:
            await self.send_to_websocket(websocket, error_message("INVALID_JSON", "Invalid JSON message"))
            return

        msg_type = msg.type

        # Handle message based on type
        if msg_type == ClientMessageType.JOIN.value:
            await self.handle_join(websocket, player_id, msg.data)

        elif msg_type == ClientMessageType.RECONNECT.value:
            await self.handle_reconnect(websocket, msg.data)

        elif msg_type == ClientMessageType.READY.value:
            await self.handle_ready(player_id, True)

        elif msg_type == ClientMessageType.UNREADY.value:
            await self.handle_ready(player_id, False)

        elif msg_type == ClientMessageType.LOCATION_CHOICE.value:
            await self.handle_location_choice(player_id, msg.data)

        elif msg_type == ClientMessageType.ESCAPE_CHOICE.value:
            await self.handle_escape_choice(player_id, msg.data)

        elif msg_type == ClientMessageType.SHOP_PURCHASE.value:
            await self.handle_shop_purchase(player_id, msg.data)

        elif msg_type == ClientMessageType.SKIP_SHOP.value:
            await self.handle_skip_shop(player_id)

        else:
            await self.send_to_websocket(websocket, error_message("UNKNOWN_TYPE", f"Unknown message type: {msg_type}"))

    async def handle_join(self, websocket: WebSocketServerProtocol, player_id: str, data: dict):
        """Handle JOIN message - player joining the server."""
        parsed = parse_join_message(data)
        username = parsed["username"] or f"Player_{player_id[:8]}"
        profile_id = parsed.get("profile_id")
        client_version = parsed.get("version")

        # Validate client version
        if client_version != VERSION:
            await self.send_to_websocket(
                websocket,
                Message(
                    type=ServerMessageType.ERROR.value,
                    data={
                        "error_type": "version_mismatch",
                        "message": f"Version mismatch. Server: {VERSION}, Client: {client_version}"
                    }
                )
            )
            await websocket.close()
            return

        # Create client
        client = ConnectedClient(
            websocket=websocket,
            player_id=player_id,
            username=username
        )
        self.clients[player_id] = client
        self.websocket_to_player[websocket] = player_id

        # For now, auto-create or join a game
        # In a full implementation, this would have lobby/matchmaking
        game_id = await self.find_or_create_game(player_id, username, profile_id)

        client.game_id = game_id
        self.player_to_game[player_id] = game_id

        # Send welcome
        await self.send_to_websocket(websocket, welcome_message(player_id, game_id))

        # Send lobby state
        game = self.games[game_id]
        await self.send_lobby_state(game)

        # Notify others
        await self.broadcast_to_game(game_id, player_joined_message(
            game.players[player_id].to_public_dict()
        ), exclude=player_id)

    async def find_or_create_game(self, player_id: str, username: str, profile_id: Optional[str] = None) -> str:
        """Find an existing game to join or create a new one."""
        # Look for a game that hasn't started yet and has room
        for game_id, game in self.games.items():
            if game.current_phase.value == "lobby" and len(game.players) < 6:
                # Join this game
                await game.add_player(player_id, username, profile_id)
                return game_id

        # Create new game
        game_id = str(uuid.uuid4())[:8]
        game = ServerGameEngine(
            game_id=game_id,
            broadcast=lambda msg: self.broadcast_to_game(game_id, msg),
            send_to_player=lambda pid, msg: self.send_to_player(pid, msg)
        )
        await game.add_player(player_id, username, profile_id)
        self.games[game_id] = game

        return game_id

    async def handle_reconnect(self, websocket: WebSocketServerProtocol, data: dict):
        """Handle RECONNECT message - player reconnecting to existing game."""
        parsed = parse_reconnect_message(data)
        player_id = parsed["player_id"]
        game_id = parsed["game_id"]

        if game_id not in self.games:
            await self.send_to_websocket(websocket, error_message("GAME_NOT_FOUND", "Game not found"))
            return

        game = self.games[game_id]
        player = game.get_player(player_id)

        if not player:
            await self.send_to_websocket(websocket, error_message("PLAYER_NOT_FOUND", "Player not found in game"))
            return

        # Update connection
        old_client = self.clients.get(player_id)
        if old_client and old_client.websocket != websocket:
            # Remove old websocket mapping
            if old_client.websocket in self.websocket_to_player:
                del self.websocket_to_player[old_client.websocket]

        client = ConnectedClient(
            websocket=websocket,
            player_id=player_id,
            username=player.username,
            game_id=game_id
        )
        self.clients[player_id] = client
        self.websocket_to_player[websocket] = player_id

        player.connected = True

        # Send welcome and game state
        await self.send_to_websocket(websocket, welcome_message(player_id, game_id))
        await game.send_game_state(player_id)

    async def handle_ready(self, player_id: str, ready: bool):
        """Handle READY/UNREADY message."""
        game_id = self.player_to_game.get(player_id)
        if not game_id or game_id not in self.games:
            return

        game = self.games[game_id]
        await game.set_player_ready(player_id, ready)

        player = game.get_player(player_id)
        if player:
            await self.broadcast_to_game(game_id, player_ready_message(
                player_id=player_id,
                username=player.username,
                ready=ready
            ))

        # Check if all ready and can start
        if game.all_players_ready():
            await game.start_game()

    async def handle_location_choice(self, player_id: str, data: dict):
        """Handle LOCATION_CHOICE message."""
        game_id = self.player_to_game.get(player_id)
        if not game_id or game_id not in self.games:
            return

        parsed = parse_location_choice_message(data)
        game = self.games[game_id]
        await game.submit_location_choice(player_id, parsed["location_index"])

    async def handle_escape_choice(self, player_id: str, data: dict):
        """Handle ESCAPE_CHOICE message."""
        game_id = self.player_to_game.get(player_id)
        if not game_id or game_id not in self.games:
            return

        parsed = parse_escape_choice_message(data)
        game = self.games[game_id]
        await game.submit_escape_choice(player_id, parsed["option_id"])

    async def handle_shop_purchase(self, player_id: str, data: dict):
        """Handle SHOP_PURCHASE message."""
        game_id = self.player_to_game.get(player_id)
        if not game_id or game_id not in self.games:
            return

        parsed = parse_shop_purchase_message(data)
        game = self.games[game_id]
        await game.handle_shop_purchase(player_id, parsed["passive_id"])

    async def handle_skip_shop(self, player_id: str):
        """Handle SKIP_SHOP message."""
        game_id = self.player_to_game.get(player_id)
        if not game_id or game_id not in self.games:
            return

        game = self.games[game_id]
        await game.handle_shop_done(player_id)

    async def handle_disconnect(self, player_id: str):
        """Handle player disconnection."""
        client = self.clients.get(player_id)
        if not client:
            return

        game_id = client.game_id
        if game_id and game_id in self.games:
            game = self.games[game_id]
            await game.remove_player(player_id)

            # Notify others
            await self.broadcast_to_game(game_id, player_left_message(
                player_id=player_id,
                username=client.username
            ), exclude=player_id)

            # Clean up empty games
            if not game.connected_players:
                del self.games[game_id]

        # Clean up client
        if client.websocket in self.websocket_to_player:
            del self.websocket_to_player[client.websocket]
        if player_id in self.clients:
            del self.clients[player_id]
        if player_id in self.player_to_game:
            del self.player_to_game[player_id]

    async def send_to_websocket(self, websocket: WebSocketServerProtocol, message: Message):
        """Send a message to a specific websocket."""
        try:
            await websocket.send(message.to_json())
        except Exception:
            pass

    async def send_to_player(self, player_id: str, message: Message):
        """Send a message to a specific player."""
        client = self.clients.get(player_id)
        if client:
            await self.send_to_websocket(client.websocket, message)

    async def broadcast_to_game(self, game_id: str, message: Message, exclude: Optional[str] = None):
        """Broadcast a message to all players in a game."""
        game = self.games.get(game_id)
        if not game:
            return

        for player_id in game.players.keys():
            if player_id != exclude:
                await self.send_to_player(player_id, message)

    async def send_lobby_state(self, game: ServerGameEngine):
        """Send lobby state to all players in a game."""
        players_list = [p.to_public_dict() for p in game.players.values()]
        host_id = game.player_order[0] if game.player_order else ""

        msg = lobby_state_message(
            game_id=game.game_id,
            players=players_list,
            host_id=host_id,
            settings={
                "turn_timer": game.turn_timer_seconds,
                "escape_timer": game.escape_timer_seconds,
                "shop_timer": game.shop_timer_seconds,
                "win_threshold": game.win_threshold,
            }
        )

        for player_id in game.players.keys():
            await self.send_to_player(player_id, msg)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="LOOT RUN Multiplayer Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    args = parser.parse_args()

    if not WEBSOCKETS_AVAILABLE:
        print("ERROR: websockets library not installed.")
        print("Install with: pip install websockets")
        return 1

    server = GameServer(host=args.host, port=args.port)
    asyncio.run(server.start())
    return 0


if __name__ == "__main__":
    exit(main())
