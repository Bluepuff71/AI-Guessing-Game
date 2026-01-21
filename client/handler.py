# client/handler.py
"""Message handler for processing server messages."""

from typing import Callable, Awaitable, Optional
from server.protocol import Message, ServerMessageType
from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase


class MessageHandler:
    """Handles incoming server messages and updates game state."""

    def __init__(self, state: GameState):
        self.state = state
        self._on_phase_change: Optional[Callable[[ClientPhase], Awaitable[None]]] = None
        self._on_round_result: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_escape_required: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_escape_result: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_game_over: Optional[Callable[[], Awaitable[None]]] = None
        self._on_player_update: Optional[Callable[[], Awaitable[None]]] = None

    def set_callbacks(
        self,
        on_phase_change: Optional[Callable[[ClientPhase], Awaitable[None]]] = None,
        on_round_result: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_escape_required: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_escape_result: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_game_over: Optional[Callable[[], Awaitable[None]]] = None,
        on_player_update: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Set callback functions for various events."""
        self._on_phase_change = on_phase_change
        self._on_round_result = on_round_result
        self._on_escape_required = on_escape_required
        self._on_escape_result = on_escape_result
        self._on_game_over = on_game_over
        self._on_player_update = on_player_update

    async def handle(self, msg: Message):
        """Handle an incoming message."""
        msg_type = msg.type
        data = msg.data

        if msg_type == ServerMessageType.WELCOME.value:
            await self._handle_welcome(data)

        elif msg_type == ServerMessageType.LOBBY_STATE.value:
            await self._handle_lobby_state(data)

        elif msg_type == ServerMessageType.PLAYER_JOINED.value:
            await self._handle_player_joined(data)

        elif msg_type == ServerMessageType.PLAYER_LEFT.value:
            await self._handle_player_left(data)

        elif msg_type == ServerMessageType.PLAYER_READY.value:
            await self._handle_player_ready(data)

        elif msg_type == ServerMessageType.GAME_STATE.value:
            await self._handle_game_state(data)

        elif msg_type == ServerMessageType.GAME_STARTED.value:
            await self._handle_game_started(data)

        elif msg_type == ServerMessageType.ROUND_START.value:
            await self._handle_round_start(data)

        elif msg_type == ServerMessageType.PHASE_CHANGE.value:
            await self._handle_phase_change(data)

        elif msg_type == ServerMessageType.SHOP_STATE.value:
            await self._handle_shop_state(data)

        elif msg_type == ServerMessageType.PURCHASE_RESULT.value:
            await self._handle_purchase_result(data)

        elif msg_type == ServerMessageType.PLAYER_SUBMITTED.value:
            pass  # Could update UI to show who submitted

        elif msg_type == ServerMessageType.ALL_CHOICES_LOCKED.value:
            pass  # All choices in, resolution coming

        elif msg_type == ServerMessageType.AI_ANALYZING.value:
            pass  # Could show animation

        elif msg_type == ServerMessageType.ROUND_RESULT.value:
            await self._handle_round_result(data)

        elif msg_type == ServerMessageType.PLAYER_CAUGHT.value:
            pass  # Handled via ESCAPE_PHASE

        elif msg_type == ServerMessageType.ESCAPE_PHASE.value:
            await self._handle_escape_phase(data)

        elif msg_type == ServerMessageType.ESCAPE_RESULT.value:
            await self._handle_escape_result(data)

        elif msg_type == ServerMessageType.PLAYER_ELIMINATED.value:
            await self._handle_player_eliminated(data)

        elif msg_type == ServerMessageType.GAME_OVER.value:
            await self._handle_game_over(data)

        elif msg_type == ServerMessageType.ERROR.value:
            await self._handle_error(data)

        elif msg_type == ServerMessageType.PLAYER_TIMEOUT.value:
            pass  # No action needed, just acknowledge

    async def _handle_welcome(self, data: dict):
        """Handle WELCOME message."""
        self.state.player_id = data.get("player_id")
        self.state.game_id = data.get("game_id")
        self.state.connected = True

    async def _handle_lobby_state(self, data: dict):
        """Handle LOBBY_STATE message."""
        self.state.game_id = data.get("game_id")
        self.state.phase = ClientPhase.LOBBY

        # Update players
        self.state.players.clear()
        for p in data.get("players", []):
            player = PlayerInfo(
                player_id=p.get("player_id"),
                username=p.get("username"),
                points=p.get("points", 0),
                alive=p.get("alive", True),
                connected=p.get("connected", True),
                ready=p.get("ready", False),
                passives=p.get("passives", []),
                color=p.get("color", "white"),
                is_local=(p.get("player_id") in self.state.local_player_ids)
            )
            self.state.players[player.player_id] = player

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_joined(self, data: dict):
        """Handle PLAYER_JOINED message."""
        p = data.get("player", {})
        player = PlayerInfo(
            player_id=p.get("player_id"),
            username=p.get("username"),
            points=p.get("points", 0),
            alive=p.get("alive", True),
            connected=p.get("connected", True),
            ready=p.get("ready", False),
            passives=p.get("passives", []),
            color=p.get("color", "white"),
            is_local=(p.get("player_id") in self.state.local_player_ids)
        )
        self.state.players[player.player_id] = player

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_left(self, data: dict):
        """Handle PLAYER_LEFT message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].connected = False

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_ready(self, data: dict):
        """Handle PLAYER_READY message."""
        player_id = data.get("player_id")
        ready = data.get("ready", False)
        if player_id in self.state.players:
            self.state.players[player_id].ready = ready

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_game_state(self, data: dict):
        """Handle full GAME_STATE sync."""
        self.state.round_num = data.get("round_num", 0)
        self.state.previous_ai_location = data.get("previous_ai_location")

        # Update locations
        self.state.locations.clear()
        for loc in data.get("locations", []):
            self.state.locations.append(LocationInfo(
                name=loc.get("name"),
                emoji=loc.get("emoji"),
                min_points=loc.get("min_points", 0),
                max_points=loc.get("max_points", 0),
            ))

        # Update events
        self.state.active_events = data.get("active_events", [])
        self._apply_events_to_locations()

        # Update players
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid in self.state.players:
                player = self.state.players[pid]
                player.points = p.get("points", 0)
                player.alive = p.get("alive", True)
                player.connected = p.get("connected", True)
                player.ready = p.get("ready", False)
                player.passives = p.get("passives", [])

    async def _handle_game_started(self, data: dict):
        """Handle GAME_STARTED message."""
        self.state.game_id = data.get("game_id")

        # Update locations
        self.state.locations.clear()
        for loc in data.get("locations", []):
            self.state.locations.append(LocationInfo(
                name=loc.get("name"),
                emoji=loc.get("emoji"),
                min_points=loc.get("min_points", 0),
                max_points=loc.get("max_points", 0),
            ))

        # Update players
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid in self.state.players:
                self.state.players[pid].points = p.get("points", 0)
                self.state.players[pid].alive = p.get("alive", True)

    async def _handle_round_start(self, data: dict):
        """Handle ROUND_START message."""
        self.state.round_num = data.get("round_num", 0)
        self.state.timer_seconds = data.get("timer_seconds", 30)
        self.state.previous_ai_location = data.get("previous_ai_location")
        self.state.active_events = data.get("active_events", [])
        self._apply_events_to_locations()

        self.state.phase = ClientPhase.CHOOSING
        self.state.current_local_player_index = 0

        if self._on_phase_change:
            await self._on_phase_change(ClientPhase.CHOOSING)

    async def _handle_phase_change(self, data: dict):
        """Handle PHASE_CHANGE message."""
        phase_str = data.get("phase", "")

        if phase_str == "shop":
            self.state.phase = ClientPhase.SHOP
        elif phase_str == "choosing":
            self.state.phase = ClientPhase.CHOOSING
        elif phase_str == "resolving":
            self.state.phase = ClientPhase.WAITING
        elif phase_str == "escape":
            self.state.phase = ClientPhase.ESCAPE

        if self._on_phase_change:
            await self._on_phase_change(self.state.phase)

    async def _handle_shop_state(self, data: dict):
        """Handle SHOP_STATE message."""
        self.state.available_passives = data.get("available_passives", [])

        # Update player points
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].points = data.get("player_points", 0)

        self.state.phase = ClientPhase.SHOP
        if self._on_phase_change:
            await self._on_phase_change(ClientPhase.SHOP)

    async def _handle_purchase_result(self, data: dict):
        """Handle PURCHASE_RESULT message."""
        if data.get("success"):
            player_id = data.get("player_id")
            if player_id in self.state.players:
                self.state.players[player_id].points = data.get("new_points", 0)
                passive_name = data.get("passive_name")
                if passive_name:
                    # Find passive ID by name and add to player
                    for p in self.state.available_passives:
                        if p.get("name") == passive_name:
                            self.state.players[player_id].passives.append(p.get("id"))
                            break

    async def _handle_round_result(self, data: dict):
        """Handle ROUND_RESULT message."""
        self.state.last_round_results = data
        self.state.phase = ClientPhase.RESULTS

        # Update player points from standings
        for standing in data.get("standings", []):
            pid = standing.get("player_id")
            if pid in self.state.players:
                self.state.players[pid].points = standing.get("points", 0)
                self.state.players[pid].alive = standing.get("alive", True)

        if self._on_round_result:
            await self._on_round_result(data)

    async def _handle_escape_phase(self, data: dict):
        """Handle ESCAPE_PHASE message."""
        player_id = data.get("player_id")

        # Only handle if this is for a local player
        if player_id in self.state.local_player_ids:
            self.state.escape_options = data.get("escape_options", [])
            self.state.caught_location = data.get("location")
            self.state.caught_points = data.get("location_points", 0)
            self.state.phase = ClientPhase.ESCAPE

            if self._on_escape_required:
                await self._on_escape_required(data)

    async def _handle_escape_result(self, data: dict):
        """Handle ESCAPE_RESULT message."""
        self.state.last_escape_result = data

        # Update player state
        player_id = data.get("player_id")
        if player_id in self.state.players:
            if not data.get("escaped"):
                self.state.players[player_id].alive = False

        if self._on_escape_result:
            await self._on_escape_result(data)

    async def _handle_player_eliminated(self, data: dict):
        """Handle PLAYER_ELIMINATED message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].alive = False
            self.state.players[player_id].points = data.get("final_score", 0)

    async def _handle_game_over(self, data: dict):
        """Handle GAME_OVER message."""
        self.state.winner = data.get("winner")
        self.state.ai_wins = data.get("ai_wins", False)
        self.state.final_standings = data.get("final_standings", [])
        self.state.phase = ClientPhase.GAME_OVER

        if self._on_game_over:
            await self._on_game_over()

    async def _handle_error(self, data: dict):
        """Handle ERROR message."""
        # Could display error to user
        pass

    def _apply_events_to_locations(self):
        """Apply active events to location info."""
        for loc in self.state.locations:
            loc.event = None

        for event in self.state.active_events:
            loc_name = event.get("location")
            for loc in self.state.locations:
                if loc.name == loc_name:
                    loc.event = event
                    break
