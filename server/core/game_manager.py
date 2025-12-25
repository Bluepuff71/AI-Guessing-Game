"""
Game session manager for handling active games.

Manages the lifecycle of game sessions, including:
- Starting games from lobbies
- Tracking active games
- Handling reconnections
- Cleaning up finished games
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

from .engine import ServerGameEngine
from .player import ServerPlayer


class GameSession:
    """Represents an active game session."""

    def __init__(
        self,
        game_id: uuid.UUID,
        lobby_code: str,
        engine: ServerGameEngine,
    ):
        self.game_id = game_id
        self.lobby_code = lobby_code
        self.engine = engine
        self.created_at = datetime.now(timezone.utc)
        self.timer_task: Optional[asyncio.Task] = None

    async def start_timer(self, seconds: int, callback):
        """Start a countdown timer."""
        if self.timer_task:
            self.timer_task.cancel()

        async def timer_loop():
            remaining = seconds
            while remaining > 0:
                await asyncio.sleep(1)
                remaining -= 1

                # Emit sync every 5 seconds
                if remaining % 5 == 0 and remaining > 0:
                    await self.engine.emit("TIMER_SYNC", {
                        "remaining_seconds": remaining,
                        "server_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    })

            # Timer expired
            await callback()

        self.timer_task = asyncio.create_task(timer_loop())

    def cancel_timer(self):
        """Cancel the current timer."""
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = None


class GameManager:
    """Manages all active game sessions."""

    def __init__(self):
        # Map game_id -> GameSession
        self._sessions: Dict[uuid.UUID, GameSession] = {}
        # Map lobby_code -> game_id
        self._lobby_to_game: Dict[str, uuid.UUID] = {}
        # Map user_id -> game_id
        self._user_to_game: Dict[uuid.UUID, uuid.UUID] = {}

    async def create_game(
        self,
        lobby_code: str,
        players: List[Dict[str, Any]],
        emit_callback,
        settings: Optional[Dict[str, Any]] = None,
    ) -> GameSession:
        """
        Create a new game from a lobby.

        Args:
            lobby_code: The lobby code
            players: List of player dicts with user_id, username
            emit_callback: Async callback to emit WebSocket messages
            settings: Optional game settings override

        Returns:
            The created GameSession
        """
        game_id = uuid.uuid4()
        settings = settings or {}

        # Create player objects
        server_players = []
        for i, player_data in enumerate(players):
            player = ServerPlayer(
                user_id=player_data['user_id'],
                username=player_data['username'],
                player_index=i,
            )
            server_players.append(player)

        # Create engine
        engine = ServerGameEngine(
            game_id=game_id,
            players=server_players,
            emit=emit_callback,
            turn_timer_seconds=settings.get('turn_timer', 30),
            escape_timer_seconds=settings.get('escape_timer', 15),
            win_threshold=settings.get('win_threshold', 100),
        )

        # Create session
        session = GameSession(game_id, lobby_code, engine)
        self._sessions[game_id] = session
        self._lobby_to_game[lobby_code] = game_id

        # Track users
        for player in server_players:
            self._user_to_game[player.user_id] = game_id

        return session

    def get_session(self, game_id: uuid.UUID) -> Optional[GameSession]:
        """Get a game session by ID."""
        return self._sessions.get(game_id)

    def get_session_by_lobby(self, lobby_code: str) -> Optional[GameSession]:
        """Get a game session by lobby code."""
        game_id = self._lobby_to_game.get(lobby_code)
        if game_id:
            return self._sessions.get(game_id)
        return None

    def get_user_game(self, user_id: uuid.UUID) -> Optional[GameSession]:
        """Get the game a user is currently in."""
        game_id = self._user_to_game.get(user_id)
        if game_id:
            return self._sessions.get(game_id)
        return None

    async def end_game(self, game_id: uuid.UUID):
        """Clean up a finished game."""
        session = self._sessions.get(game_id)
        if not session:
            return

        # Cancel any timers
        session.cancel_timer()

        # Remove user mappings
        for player in session.engine.players:
            self._user_to_game.pop(player.user_id, None)

        # Remove lobby mapping
        self._lobby_to_game.pop(session.lobby_code, None)

        # Remove session
        del self._sessions[game_id]

    def handle_disconnect(self, user_id: uuid.UUID):
        """Handle a player disconnecting."""
        session = self.get_user_game(user_id)
        if session:
            player = session.engine.get_player(user_id)
            if player:
                player.connected = False

    def handle_reconnect(self, user_id: uuid.UUID) -> Optional[GameSession]:
        """Handle a player reconnecting."""
        session = self.get_user_game(user_id)
        if session:
            player = session.engine.get_player(user_id)
            if player:
                player.connected = True
            return session
        return None

    @property
    def active_games(self) -> int:
        """Get count of active games."""
        return len(self._sessions)


# Global game manager instance
game_manager = GameManager()
