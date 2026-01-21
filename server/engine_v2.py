# server/engine_v2.py
"""Event-driven game engine for LOOT RUN multiplayer.

This engine:
- Uses an event-driven state machine architecture
- Never blocks - handle_event returns immediately
- All timers fire events instead of blocking
- Processes one event at a time
"""

import random
from datetime import datetime, timezone
from typing import Callable, Awaitable, Dict, List, Optional, Any
from dataclasses import dataclass, field

from game.locations import LocationManager, Location
from game.events import EventManager
from game.hiding import HidingManager
from game.passives import PassiveManager
from ai.predictor import AIPredictor
from ai.escape_predictor import EscapePredictor

from server.protocol import (
    GamePhase, Message, ServerMessageType,
    game_started_message, round_start_message, phase_change_message,
    player_submitted_message, all_choices_locked_message, player_timeout_message,
    ai_analyzing_message, round_result_message, player_caught_message,
    escape_phase_message, escape_result_message, player_eliminated_message,
    shop_state_message, purchase_result_message, game_over_message
)
from server.events import GameEvent, GameEventType
from server.pending import PendingChoices, PendingEscapes
from server.timers import TimerManager


# Type aliases
MessageBroadcaster = Callable[[Message], Awaitable[None]]
PlayerMessageSender = Callable[[str, Message], Awaitable[None]]

# Player colors
PLAYER_COLORS = ["green", "cyan", "yellow", "magenta", "red", "blue", "bright_green", "bright_cyan"]


@dataclass(eq=False)
class ServerPlayer:
    """Server-side player representation."""

    player_id: str
    username: str
    player_index: int
    profile_id: Optional[str] = None

    # Game state
    points: int = 0
    alive: bool = True
    connected: bool = True
    ready: bool = False

    # Passive management
    passive_manager: PassiveManager = field(default_factory=PassiveManager)

    # History tracking
    choice_history: List[str] = field(default_factory=list)
    round_history: List[Dict[str, Any]] = field(default_factory=list)
    escape_option_history: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.player_id)

    def __eq__(self, other):
        if isinstance(other, ServerPlayer):
            return self.player_id == other.player_id
        return False

    @property
    def color(self) -> str:
        return PLAYER_COLORS[self.player_index % len(PLAYER_COLORS)]

    @property
    def owned_passives(self) -> List:
        """Get list of owned passives for compatibility."""
        return self.passive_manager.get_all()

    def add_points(self, points: int) -> None:
        self.points += points

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "username": self.username,
            "points": self.points,
            "alive": self.alive,
            "connected": self.connected,
            "ready": self.ready,
            "color": self.color,
            "passives": [p.type.value for p in self.passive_manager.get_all()]
        }


class EventDrivenGameEngine:
    """Event-driven game engine using state machine architecture."""

    # Timer IDs
    TIMER_SHOP = "shop"
    TIMER_CHOICE = "choice"
    TIMER_ESCAPE = "escape"

    def __init__(
        self,
        game_id: str,
        broadcast: MessageBroadcaster,
        send_to_player: PlayerMessageSender,
        turn_timer_seconds: int = 30,
        escape_timer_seconds: int = 15,
        shop_timer_seconds: int = 20,
        win_threshold: int = 100
    ):
        self.game_id = game_id
        self.broadcast = broadcast
        self.send_to_player = send_to_player

        # Settings
        self.turn_timer_seconds = turn_timer_seconds
        self.escape_timer_seconds = escape_timer_seconds
        self.shop_timer_seconds = shop_timer_seconds
        self.win_threshold = win_threshold

        # Players
        self.players: Dict[str, ServerPlayer] = {}
        self.player_order: List[str] = []

        # Game components
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.escape_predictor = EscapePredictor()
        self.event_manager = EventManager()
        self.hiding_manager = HidingManager()

        # State
        self._phase = GamePhase.LOBBY
        self.round_num = 0
        self.game_over = False
        self.winner: Optional[ServerPlayer] = None
        self.last_ai_search_location: Optional[Location] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

        # Pending state
        self.pending_choices = PendingChoices()
        self.pending_escapes = PendingEscapes()

        # Timers
        self.timers = TimerManager(self._on_timer_event)

        # Event handlers by phase and event type
        self._handlers: Dict[GameEventType, Callable] = {
            GameEventType.PLAYER_JOIN: self._handle_player_join,
            GameEventType.PLAYER_LEAVE: self._handle_player_leave,
            GameEventType.PLAYER_READY: self._handle_player_ready,
            GameEventType.PLAYER_UNREADY: self._handle_player_unready,
            GameEventType.GAME_START: self._handle_game_start,
            GameEventType.SHOP_PURCHASE: self._handle_shop_purchase,
            GameEventType.SHOP_SKIP: self._handle_shop_skip,
            GameEventType.SHOP_TIMEOUT: self._handle_shop_timeout,
            GameEventType.LOCATION_CHOICE: self._handle_location_choice,
            GameEventType.CHOICE_TIMEOUT: self._handle_choice_timeout,
            GameEventType.ESCAPE_CHOICE: self._handle_escape_choice,
            GameEventType.ESCAPE_TIMEOUT: self._handle_escape_timeout,
        }

    @property
    def phase(self) -> GamePhase:
        """Current game phase."""
        return self._phase

    @property
    def alive_players(self) -> List[ServerPlayer]:
        """Get all alive players."""
        return [p for p in self.players.values() if p.alive]

    @property
    def connected_players(self) -> List[ServerPlayer]:
        """Get all connected players."""
        return [p for p in self.players.values() if p.connected]

    async def handle_event(self, event: GameEvent) -> None:
        """Handle an incoming event. Never blocks."""
        handler = self._handlers.get(event.type)
        if handler:
            await handler(event)

    async def _on_timer_event(self, event: GameEvent) -> None:
        """Called when a timer fires. Routes to handle_event."""
        await self.handle_event(event)

    # --- Player Events ---

    async def _handle_player_join(self, event: GameEvent) -> None:
        """Handle PLAYER_JOIN event."""
        player_id = event.player_id
        if not player_id or player_id in self.players:
            return

        username = event.data.get("username", f"Player_{player_id[:8]}")
        profile_id = event.data.get("profile_id")

        player = ServerPlayer(
            player_id=player_id,
            username=username,
            player_index=len(self.player_order),
            profile_id=profile_id
        )
        self.players[player_id] = player
        self.player_order.append(player_id)

    async def _handle_player_leave(self, event: GameEvent) -> None:
        """Handle PLAYER_LEAVE event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].connected = False

    async def _handle_player_ready(self, event: GameEvent) -> None:
        """Handle PLAYER_READY event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].ready = True

    async def _handle_player_unready(self, event: GameEvent) -> None:
        """Handle PLAYER_UNREADY event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].ready = False

    # --- Game Start ---

    async def _handle_game_start(self, event: GameEvent) -> None:
        """Handle GAME_START event."""
        if self._phase != GamePhase.LOBBY:
            return

        # Check all players ready
        connected = self.connected_players
        if not connected or not all(p.ready for p in connected):
            return

        self.started_at = datetime.now(timezone.utc)
        await self._start_round()

    # --- Shop Phase ---

    async def _handle_shop_purchase(self, event: GameEvent) -> None:
        """Handle SHOP_PURCHASE event."""
        if self._phase != GamePhase.SHOP:
            return
        # TODO: Implement shop purchase logic
        pass

    async def _handle_shop_skip(self, event: GameEvent) -> None:
        """Handle SHOP_SKIP event."""
        if self._phase != GamePhase.SHOP:
            return

        player_id = event.player_id
        if not player_id:
            return

        self.pending_choices.record_shop_done(player_id)
        await self._check_shop_complete()

    async def _handle_shop_timeout(self, event: GameEvent) -> None:
        """Handle SHOP_TIMEOUT event."""
        if self._phase != GamePhase.SHOP:
            return
        await self._start_choosing_phase()

    async def _check_shop_complete(self) -> None:
        """Check if all players are done shopping."""
        alive_ids = [p.player_id for p in self.alive_players if p.connected]
        if self.pending_choices.all_shop_done(alive_ids):
            self.timers.cancel_timer(self.TIMER_SHOP)
            await self._start_choosing_phase()

    # --- Choosing Phase ---

    async def _handle_location_choice(self, event: GameEvent) -> None:
        """Handle LOCATION_CHOICE event."""
        if self._phase != GamePhase.CHOOSING:
            return

        player_id = event.player_id
        location_index = event.data.get("location_index")

        if not player_id or location_index is None:
            return

        player = self.players.get(player_id)
        if not player or not player.alive:
            return

        # Already submitted?
        if self.pending_choices.get_choice(player_id) is not None:
            return

        # Validate location
        locations = self.location_manager.get_all()
        if location_index < 0 or location_index >= len(locations):
            return

        self.pending_choices.record_choice(player_id, location_index)

        # Notify others
        await self.broadcast(player_submitted_message(
            player_id=player_id,
            username=player.username
        ))

        await self._check_all_choices_in()

    async def _handle_choice_timeout(self, event: GameEvent) -> None:
        """Handle CHOICE_TIMEOUT event."""
        if self._phase != GamePhase.CHOOSING:
            return

        # Assign random choices to players who haven't submitted
        locations = self.location_manager.get_all()
        for player in self.alive_players:
            if self.pending_choices.get_choice(player.player_id) is None:
                random_index = random.randint(0, len(locations) - 1)
                self.pending_choices.record_choice(player.player_id, random_index)
                await self.broadcast(player_timeout_message(
                    player_id=player.player_id,
                    username=player.username
                ))

        await self._resolve_round()

    async def _check_all_choices_in(self) -> None:
        """Check if all players have submitted choices."""
        alive_ids = [p.player_id for p in self.alive_players if p.connected]
        if self.pending_choices.has_all_choices(alive_ids):
            self.timers.cancel_timer(self.TIMER_CHOICE)
            await self.broadcast(all_choices_locked_message(
                players_submitted=[p.username for p in self.alive_players if p.connected]
            ))
            await self._resolve_round()

    # --- Escape Phase ---

    async def _handle_escape_choice(self, event: GameEvent) -> None:
        """Handle ESCAPE_CHOICE event."""
        if self._phase != GamePhase.ESCAPE:
            return

        player_id = event.player_id
        option_id = event.data.get("option_id")

        if not player_id or not option_id:
            return

        if not self.pending_escapes.has_pending(player_id):
            return

        self.pending_escapes.record_choice(player_id, option_id)
        await self._check_all_escapes_resolved()

    async def _handle_escape_timeout(self, event: GameEvent) -> None:
        """Handle ESCAPE_TIMEOUT event."""
        if self._phase != GamePhase.ESCAPE:
            return

        # Assign random choices to unresolved escapes
        for player_id in self.pending_escapes.get_unresolved_player_ids():
            escape = self.pending_escapes.get_escape(player_id)
            if escape and escape.escape_options:
                random_option = random.choice(escape.escape_options)
                self.pending_escapes.record_choice(player_id, random_option["id"])

        await self._resolve_all_escapes()

    async def _check_all_escapes_resolved(self) -> None:
        """Check if all escape choices are in."""
        if self.pending_escapes.all_resolved():
            self.timers.cancel_timer(self.TIMER_ESCAPE)
            await self._resolve_all_escapes()

    # --- Phase Transitions ---

    async def _start_round(self) -> None:
        """Start a new round."""
        self.round_num += 1
        self.pending_choices.clear()
        self.pending_escapes.clear()

        # Roll new events
        self.event_manager.tick_events()

        # Go to shop phase (or skip if round 1)
        if self.round_num == 1:
            await self._start_choosing_phase()
        else:
            await self._start_shop_phase()

    async def _start_shop_phase(self) -> None:
        """Start the shop phase."""
        self._phase = GamePhase.SHOP

        # Send shop state to each player
        for player in self.alive_players:
            if player.connected:
                # TODO: Generate shop offerings
                await self.send_to_player(player.player_id, shop_state_message(
                    player_id=player.player_id,
                    player_points=player.points,
                    available_passives=[],
                    owned_passives=[p.type.value for p in player.owned_passives],
                    timer_seconds=self.shop_timer_seconds
                ))

        self.timers.start_timer(
            self.TIMER_SHOP,
            self.shop_timer_seconds,
            GameEventType.SHOP_TIMEOUT
        )

    async def _start_choosing_phase(self) -> None:
        """Start the location choosing phase."""
        self._phase = GamePhase.CHOOSING

        await self.broadcast(round_start_message(
            round_num=self.round_num,
            timer_seconds=self.turn_timer_seconds,
            server_timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            active_events=self._build_active_events(),
            new_events=[],
            standings=self._build_standings(),
            previous_ai_location=self.last_ai_search_location.name if self.last_ai_search_location else None
        ))

        self.timers.start_timer(
            self.TIMER_CHOICE,
            self.turn_timer_seconds,
            GameEventType.CHOICE_TIMEOUT
        )

    async def _resolve_round(self) -> None:
        """Resolve the round after all choices are in."""
        self._phase = GamePhase.RESOLVING

        await self.broadcast(phase_change_message(
            new_phase="resolving",
            round_num=self.round_num
        ))

        await self.broadcast(ai_analyzing_message(duration_ms=1000))

        # Build player choices map
        player_choices: Dict[ServerPlayer, Location] = {}
        for player in self.alive_players:
            location_index = self.pending_choices.get_choice(player.player_id)
            if location_index is not None:
                location = self.location_manager.get_location(location_index)
                player_choices[player] = location

        # AI decides where to search
        search_location, predictions, ai_reasoning = self._ai_decide_search(player_choices)
        self.last_ai_search_location = search_location

        # Build results and identify caught players
        player_results = []
        caught_players = []

        for player in self.alive_players:
            chosen_location = player_choices.get(player)
            if not chosen_location:
                continue

            # Roll points
            location_points = chosen_location.roll_points()
            caught = (chosen_location.name == search_location.name)

            result = {
                "player_id": player.player_id,
                "username": player.username,
                "location": chosen_location.name,
                "location_emoji": chosen_location.emoji,
                "caught": caught,
                "base_points": location_points,
                "modified_points": location_points,
            }

            if caught:
                caught_players.append((player, chosen_location, location_points))
                result["escape_required"] = True
            else:
                player.add_points(location_points)
                result["points_earned"] = location_points
                result["total_points"] = player.points

            player_results.append(result)

        # Broadcast round result
        await self.broadcast(round_result_message(
            round_num=self.round_num,
            ai_search_location=search_location.name,
            ai_search_emoji=search_location.emoji,
            ai_reasoning=ai_reasoning,
            player_results=player_results,
            standings=self._build_standings()
        ))

        # Handle escapes or finish round
        if caught_players:
            await self._start_escape_phase(caught_players)
        else:
            await self._finish_round()

    async def _start_escape_phase(self, caught_players: List[tuple]) -> None:
        """Start the escape phase for caught players."""
        self._phase = GamePhase.ESCAPE

        for player, location, points in caught_players:
            # Get escape options
            escape_options = self.hiding_manager.get_escape_options_for_location(location.name)

            if not escape_options:
                # No escape - eliminated
                player.alive = False
                await self.broadcast(player_eliminated_message(
                    player_id=player.player_id,
                    username=player.username,
                    final_score=player.points
                ))
                continue

            # AI predicts escape
            ai_prediction, _, ai_reasoning = self.escape_predictor.predict_escape_option(
                player, escape_options, None
            )

            # Track pending escape
            self.pending_escapes.add_escape(
                player_id=player.player_id,
                location_name=location.name,
                location_points=points,
                escape_options=escape_options,
                ai_prediction=ai_prediction,
                ai_reasoning=ai_reasoning
            )

            # Notify player
            await self.broadcast(player_caught_message(
                player_id=player.player_id,
                username=player.username,
                location=location.name,
                location_points=points
            ))

            await self.send_to_player(player.player_id, escape_phase_message(
                player_id=player.player_id,
                username=player.username,
                location=location.name,
                location_points=points,
                escape_options=[{
                    "id": opt["id"],
                    "name": opt["name"],
                    "type": opt.get("type", "hide"),
                    "emoji": opt.get("emoji", ""),
                    "description": opt.get("description", ""),
                } for opt in escape_options],
                timer_seconds=self.escape_timer_seconds
            ))

        # Start escape timer (if anyone has pending escapes)
        if self.pending_escapes.get_all():
            self.timers.start_timer(
                self.TIMER_ESCAPE,
                self.escape_timer_seconds,
                GameEventType.ESCAPE_TIMEOUT
            )
        else:
            # All caught players were eliminated (no escape options)
            await self._finish_round()

    async def _resolve_all_escapes(self) -> None:
        """Resolve all pending escapes."""
        for escape in self.pending_escapes.get_all():
            await self._resolve_single_escape(escape)

        await self._finish_round()

    async def _resolve_single_escape(self, escape) -> None:
        """Resolve a single escape attempt."""
        player = self.players.get(escape.player_id)
        if not player:
            return

        chosen_option_id = escape.chosen_option_id
        chosen_option = None
        for opt in escape.escape_options:
            if opt["id"] == chosen_option_id:
                chosen_option = opt
                break

        if not chosen_option:
            chosen_option = escape.escape_options[0] if escape.escape_options else None

        if not chosen_option:
            player.alive = False
            return

        # Resolve using hiding manager
        result = self.hiding_manager.resolve_escape_attempt(
            chosen_option,
            escape.ai_prediction,
            escape.location_points
        )

        # Update player state
        if result["escaped"]:
            player.add_points(result.get("points_awarded", 0))
        else:
            player.alive = False

        # Broadcast result
        await self.broadcast(escape_result_message(
            player_id=player.player_id,
            username=player.username,
            player_choice=chosen_option_id,
            player_choice_name=chosen_option.get("name", chosen_option_id),
            ai_prediction=escape.ai_prediction,
            ai_prediction_name=escape.ai_prediction,
            ai_reasoning=escape.ai_reasoning,
            escaped=result["escaped"],
            points_awarded=result.get("points_awarded", 0),
            passive_saved=False
        ))

        if not result["escaped"]:
            await self.broadcast(player_eliminated_message(
                player_id=player.player_id,
                username=player.username,
                final_score=player.points
            ))

    async def _finish_round(self) -> None:
        """Finish the current round."""
        self._phase = GamePhase.ROUND_END

        # Check for game over
        if await self._check_game_over():
            return

        # Start next round
        await self._start_round()

    async def _check_game_over(self) -> bool:
        """Check if game is over."""
        alive = self.alive_players

        # Score victory
        for player in alive:
            if player.points >= self.win_threshold:
                self.game_over = True
                self.winner = player
                self.finished_at = datetime.now(timezone.utc)
                await self._emit_game_over()
                return True

        # All eliminated
        if len(alive) == 0:
            self.game_over = True
            self.winner = None
            self.finished_at = datetime.now(timezone.utc)
            await self._emit_game_over()
            return True

        return False

    async def _emit_game_over(self) -> None:
        """Emit game over message."""
        self._phase = GamePhase.GAME_OVER

        duration = 0
        if self.finished_at and self.started_at:
            duration = int((self.finished_at - self.started_at).total_seconds())

        await self.broadcast(game_over_message(
            winner={
                "player_id": self.winner.player_id,
                "username": self.winner.username,
                "score": self.winner.points,
            } if self.winner else None,
            ai_wins=self.winner is None,
            final_standings=self._build_standings(),
            rounds_played=self.round_num,
            game_duration_seconds=duration
        ))

    # --- Helpers ---

    def _ai_decide_search(self, player_choices: Dict[ServerPlayer, Location]):
        """AI decides where to search."""
        predictions = {}
        for player, location in player_choices.items():
            predictions[player] = (location.name, 0.5, "Random guess")

        # Pick most popular location or random
        location_counts: Dict[str, int] = {}
        for loc in player_choices.values():
            location_counts[loc.name] = location_counts.get(loc.name, 0) + 1

        if location_counts:
            search_name = max(location_counts, key=location_counts.get)
            search_location = None
            for loc in self.location_manager.get_all():
                if loc.name == search_name:
                    search_location = loc
                    break
            if not search_location:
                search_location = random.choice(self.location_manager.get_all())
        else:
            search_location = random.choice(self.location_manager.get_all())

        return search_location, predictions, "AI searched the most popular location."

    def _build_standings(self) -> List[Dict[str, Any]]:
        """Build standings list."""
        sorted_players = sorted(
            self.players.values(),
            key=lambda p: (-p.points, not p.alive)
        )
        return [
            {
                "player_id": p.player_id,
                "username": p.username,
                "points": p.points,
                "alive": p.alive
            }
            for p in sorted_players
        ]

    def _build_active_events(self) -> List[Dict[str, Any]]:
        """Build active events list."""
        active_events = []
        for loc in self.location_manager.get_all():
            event = self.event_manager.get_location_event(loc)
            if event:
                active_events.append({
                    "location": loc.name,
                    "name": event.name,
                    "emoji": event.emoji,
                    "description": event.description,
                })
        return active_events
