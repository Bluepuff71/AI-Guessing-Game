# client/handler.py
"""Message handler for processing server messages."""

from typing import Callable, Optional, Dict, Any
from server.protocol import ServerMessageType
from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase


class MessageHandler:
    """Handles incoming server messages and updates game state.

    This handler is now synchronous. It updates state directly without callbacks.
    The main loop should check state.phase changes after calling handle().
    """

    def __init__(self, state: GameState):
        self.state = state
        # Store last event data for the main loop to react to
        self.last_round_result: Optional[Dict[str, Any]] = None
        self.last_escape_required: Optional[Dict[str, Any]] = None
        self.last_escape_result: Optional[Dict[str, Any]] = None
        self.phase_changed: bool = False
        self.player_updated: bool = False
        self.game_over: bool = False

    def clear_events(self):
        """Clear event flags. Call this after processing events in main loop."""
        self.last_round_result = None
        self.last_escape_required = None
        self.last_escape_result = None
        self.phase_changed = False
        self.player_updated = False
        self.game_over = False

    def handle(self, message_type: str, data: Dict[str, Any]):
        """Handle an incoming message.

        Args:
            message_type: The type of message (e.g., "WELCOME", "GAME_STATE")
            data: The message payload data
        """
        if message_type == ServerMessageType.WELCOME.value:
            self._handle_welcome(data)

        elif message_type == ServerMessageType.LOBBY_STATE.value:
            self._handle_lobby_state(data)

        elif message_type == ServerMessageType.PLAYER_JOINED.value:
            self._handle_player_joined(data)

        elif message_type == ServerMessageType.PLAYER_LEFT.value:
            self._handle_player_left(data)

        elif message_type == ServerMessageType.PLAYER_READY.value:
            self._handle_player_ready(data)

        elif message_type == ServerMessageType.GAME_STATE.value:
            self._handle_game_state(data)

        elif message_type == ServerMessageType.GAME_STARTED.value:
            self._handle_game_started(data)

        elif message_type == ServerMessageType.ROUND_START.value:
            self._handle_round_start(data)

        elif message_type == ServerMessageType.PHASE_CHANGE.value:
            self._handle_phase_change(data)

        elif message_type == ServerMessageType.SHOP_STATE.value:
            self._handle_shop_state(data)

        elif message_type == ServerMessageType.PURCHASE_RESULT.value:
            self._handle_purchase_result(data)

        elif message_type == ServerMessageType.PLAYER_SUBMITTED.value:
            pass  # Could update UI to show who submitted

        elif message_type == ServerMessageType.ALL_CHOICES_LOCKED.value:
            pass  # All choices in, resolution coming

        elif message_type == ServerMessageType.AI_ANALYZING.value:
            pass  # Could show animation

        elif message_type == ServerMessageType.ROUND_RESULT.value:
            self._handle_round_result(data)

        elif message_type == ServerMessageType.PLAYER_CAUGHT.value:
            pass  # Handled via ESCAPE_PHASE

        elif message_type == ServerMessageType.ESCAPE_PHASE.value:
            self._handle_escape_phase(data)

        elif message_type == ServerMessageType.ESCAPE_RESULT.value:
            self._handle_escape_result(data)

        elif message_type == ServerMessageType.PLAYER_ELIMINATED.value:
            self._handle_player_eliminated(data)

        elif message_type == ServerMessageType.GAME_OVER.value:
            self._handle_game_over(data)

        elif message_type == ServerMessageType.ERROR.value:
            self._handle_error(data)

        elif message_type == ServerMessageType.PLAYER_TIMEOUT.value:
            pass  # No action needed, just acknowledge

    def _handle_welcome(self, data: dict):
        """Handle WELCOME message."""
        self.state.player_id = data.get("player_id")
        self.state.game_id = data.get("game_id")
        self.state.connected = True

    def _handle_lobby_state(self, data: dict):
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

        self.player_updated = True

    def _handle_player_joined(self, data: dict):
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

        self.player_updated = True

    def _handle_player_left(self, data: dict):
        """Handle PLAYER_LEFT message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].connected = False

        self.player_updated = True

    def _handle_player_ready(self, data: dict):
        """Handle PLAYER_READY message."""
        player_id = data.get("player_id")
        ready = data.get("ready", False)
        if player_id in self.state.players:
            self.state.players[player_id].ready = ready

        self.player_updated = True

    def _handle_game_state(self, data: dict):
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

    def _handle_game_started(self, data: dict):
        """Handle GAME_STARTED message."""
        self.state.game_id = data.get("game_id")
        self.state.round_num = 1  # Game starts at round 1

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

    def _handle_round_start(self, data: dict):
        """Handle ROUND_START message."""
        self.state.round_num = data.get("round_num", 0)
        self.state.timer_seconds = data.get("timer_seconds", 30)
        self.state.previous_ai_location = data.get("previous_ai_location")
        self.state.active_events = data.get("active_events", [])

        # Update locations if provided (ensures locations are always current)
        if "locations" in data:
            self.state.locations.clear()
            for loc in data.get("locations", []):
                self.state.locations.append(LocationInfo(
                    name=loc.get("name"),
                    emoji=loc.get("emoji"),
                    min_points=loc.get("min_points", 0),
                    max_points=loc.get("max_points", 0),
                ))

        self._apply_events_to_locations()

        self.state.phase = ClientPhase.CHOOSING
        self.state.current_local_player_index = 0
        self.phase_changed = True

    def _handle_phase_change(self, data: dict):
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

        self.phase_changed = True

    def _handle_shop_state(self, data: dict):
        """Handle SHOP_STATE message."""
        self.state.available_passives = data.get("available_passives", [])

        # Update player points
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].points = data.get("player_points", 0)

        self.state.phase = ClientPhase.SHOP
        self.phase_changed = True

    def _handle_purchase_result(self, data: dict):
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

    def _handle_round_result(self, data: dict):
        """Handle ROUND_RESULT message."""
        self.state.last_round_results = data
        self.state.phase = ClientPhase.RESULTS

        # Update player points from standings
        for standing in data.get("standings", []):
            pid = standing.get("player_id")
            if pid in self.state.players:
                self.state.players[pid].points = standing.get("points", 0)
                self.state.players[pid].alive = standing.get("alive", True)

        self.last_round_result = data

    def _handle_escape_phase(self, data: dict):
        """Handle ESCAPE_PHASE message."""
        player_id = data.get("player_id")

        # Only handle if this is for a local player
        if player_id in self.state.local_player_ids:
            self.state.escape_options = data.get("escape_options", [])
            self.state.caught_location = data.get("location")
            self.state.caught_points = data.get("location_points", 0)
            self.state.phase = ClientPhase.ESCAPE

            self.last_escape_required = data

    def _handle_escape_result(self, data: dict):
        """Handle ESCAPE_RESULT message."""
        self.state.last_escape_result = data

        # Update player state
        player_id = data.get("player_id")
        if player_id in self.state.players:
            if not data.get("escaped"):
                self.state.players[player_id].alive = False

        self.last_escape_result = data

    def _handle_player_eliminated(self, data: dict):
        """Handle PLAYER_ELIMINATED message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].alive = False
            self.state.players[player_id].points = data.get("final_score", 0)

    def _handle_game_over(self, data: dict):
        """Handle GAME_OVER message."""
        self.state.winner = data.get("winner")
        self.state.ai_wins = data.get("ai_wins", False)
        self.state.final_standings = data.get("final_standings", [])
        self.state.phase = ClientPhase.GAME_OVER

        self.game_over = True

    def _handle_error(self, data: dict):
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
