"""
Unified server-side game engine for LOOT RUN multiplayer.

This engine:
- Has NO UI code - purely game logic
- Reuses existing game components (locations, events, hiding, AI)
- Handles all game phases via async message passing
- Communicates via WebSocket messages only
"""

import asyncio
import random
import uuid
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

# Import game components (no UI dependencies)
from game.locations import LocationManager, Location
from game.events import EventManager
from game.hiding import HidingManager
from game.passives import PassiveShop, PassiveType, Passive, PassiveManager
from game.config_loader import config
from ai.predictor import AIPredictor
from ai.escape_predictor import EscapePredictor

from server.protocol import (
    GamePhase, Message, ServerMessageType,
    game_state_message, game_started_message, round_start_message,
    phase_change_message, player_submitted_message, all_choices_locked_message,
    player_timeout_message, ai_analyzing_message, round_result_message,
    player_caught_message, escape_phase_message, escape_result_message,
    player_eliminated_message, shop_state_message, purchase_result_message,
    game_over_message, error_message
)


# Type alias for message broadcaster
MessageBroadcaster = Callable[[Message], Awaitable[None]]
PlayerMessageSender = Callable[[str, Message], Awaitable[None]]


# Player colors (same as game/player.py but without UI dependency)
PLAYER_COLORS = ["green", "cyan", "yellow", "magenta", "red", "blue", "bright_green", "bright_cyan"]


@dataclass(eq=False)
class ServerPlayer:
    """Server-side player representation with JSON serialization."""

    player_id: str
    username: str
    player_index: int
    profile_id: Optional[str] = None

    def __hash__(self):
        """Hash based on player_id for use in dicts."""
        return hash(self.player_id)

    def __eq__(self, other):
        """Equality based on player_id."""
        if isinstance(other, ServerPlayer):
            return self.player_id == other.player_id
        return False

    # Game state
    points: int = 0
    alive: bool = True
    connected: bool = True
    ready: bool = False

    # Passive management
    passive_manager: PassiveManager = field(default_factory=PassiveManager)

    # History tracking for AI
    choice_history: List[str] = field(default_factory=list)
    round_history: List[Dict[str, Any]] = field(default_factory=list)

    # Escape tracking
    escape_option_history: List[str] = field(default_factory=list)
    hide_run_history: List[Dict[str, Any]] = field(default_factory=list)
    hiding_stats: Dict[str, Any] = field(default_factory=lambda: {
        'total_escape_attempts': 0,
        'successful_escapes': 0,
        'total_hide_attempts': 0,
        'successful_hides': 0,
        'total_run_attempts': 0,
        'successful_runs': 0,
        'favorite_escape_options': {},
        'hide_vs_run_ratio': 0.0
    })

    @property
    def color(self) -> str:
        """Get player color based on index."""
        return PLAYER_COLORS[self.player_index % len(PLAYER_COLORS)]

    def add_points(self, points: int):
        """Add points to player."""
        self.points += points

    def has_passive(self, passive_type: PassiveType) -> bool:
        """Check if player has a specific passive."""
        return self.passive_manager.has_passive(passive_type)

    def get_passives(self) -> List[Passive]:
        """Get all owned passives."""
        return self.passive_manager.get_all()

    def buy_passive(self, passive: Passive) -> bool:
        """Attempt to buy a passive. Returns True if successful."""
        if self.points >= passive.cost:
            if self.passive_manager.add_passive(passive):
                self.points -= passive.cost
                return True
        return False

    def record_choice(self, location_name: str, round_num: int,
                      caught: bool, points_earned: int, location_value: int = None):
        """Record a location choice for AI learning."""
        self.choice_history.append(location_name)

        if location_value is None:
            location_value = points_earned

        self.round_history.append({
            'round': round_num,
            'location': location_name,
            'location_value': location_value,
            'points_before': self.points - points_earned,
            'points_earned': points_earned,
            'caught': caught,
            'passives_held': [p.name for p in self.get_passives()],
        })

    def record_escape_attempt(self, escape_result: Dict[str, Any], round_num: int):
        """Record an escape attempt for AI learning."""
        choice_type = escape_result.get('choice_type', 'hide')
        escaped = escape_result['escaped']
        option_id = escape_result.get('player_choice_id')

        if option_id:
            self.escape_option_history.append(option_id)

        self.hide_run_history.append({
            'round': round_num,
            'choice_type': choice_type,
            'escaped': escaped,
            'option_id': option_id,
            'option_name': escape_result.get('player_choice_name'),
            'ai_prediction_id': escape_result.get('ai_prediction_id'),
            'ai_was_correct': escape_result.get('ai_was_correct', False),
            'points_before': self.points,
            'points_awarded': escape_result.get('points_awarded', 0)
        })

        # Update statistics
        self.hiding_stats['total_escape_attempts'] += 1
        if escaped:
            self.hiding_stats['successful_escapes'] += 1

        if choice_type == 'hide':
            self.hiding_stats['total_hide_attempts'] += 1
            if escaped:
                self.hiding_stats['successful_hides'] += 1
        else:
            self.hiding_stats['total_run_attempts'] += 1
            if escaped:
                self.hiding_stats['successful_runs'] += 1

        if option_id:
            if option_id not in self.hiding_stats['favorite_escape_options']:
                self.hiding_stats['favorite_escape_options'][option_id] = 0
            self.hiding_stats['favorite_escape_options'][option_id] += 1

        total = self.hiding_stats['total_hide_attempts'] + self.hiding_stats['total_run_attempts']
        if total > 0:
            self.hiding_stats['hide_vs_run_ratio'] = self.hiding_stats['total_hide_attempts'] / total

    def get_behavior_summary(self) -> Dict[str, Any]:
        """Get summary of player behavior for AI analysis."""
        if not self.choice_history:
            return {
                'avg_location_value': 0,
                'choice_variety': 0,
                'high_value_preference': 0,
                'location_frequencies': {},
                'total_choices': 0,
            }

        location_counts = {}
        total_value = 0

        for round_data in self.round_history:
            loc = round_data['location']
            location_counts[loc] = location_counts.get(loc, 0) + 1
            total_value += round_data['location_value']

        num_choices = len(self.choice_history)
        unique_locations = len(location_counts)
        avg_value = total_value / num_choices if num_choices > 0 else 0

        high_value_count = sum(1 for r in self.round_history if r['location_value'] >= 15)

        return {
            'avg_location_value': avg_value,
            'choice_variety': unique_locations / 8.0,  # 8 total locations
            'high_value_preference': high_value_count / num_choices if num_choices > 0 else 0,
            'location_frequencies': location_counts,
            'total_choices': num_choices,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize player to dictionary."""
        return {
            'player_id': self.player_id,
            'username': self.username,
            'player_index': self.player_index,
            'profile_id': self.profile_id,
            'points': self.points,
            'alive': self.alive,
            'connected': self.connected,
            'ready': self.ready,
            'passives': [p.type.value for p in self.get_passives()],
            'color': self.color,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Get public player info (visible to all players)."""
        return {
            'player_id': self.player_id,
            'username': self.username,
            'player_index': self.player_index,
            'points': self.points,
            'alive': self.alive,
            'connected': self.connected,
            'ready': self.ready,
            'passives': [p.type.value for p in self.get_passives()],
            'color': self.color,
        }


@dataclass
class PendingChoices:
    """Tracks pending player choices for a round."""
    location_choices: Dict[str, Optional[int]] = field(default_factory=dict)
    escape_choices: Dict[str, Optional[str]] = field(default_factory=dict)
    shop_done: Dict[str, bool] = field(default_factory=dict)


class ServerGameEngine:
    """
    Unified server-side game engine for LOOT RUN multiplayer.

    This engine:
    - Has NO UI dependencies
    - Communicates via async message callbacks
    - Handles all game phases and player actions
    - Reuses existing game components
    """

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
        self.broadcast = broadcast  # Broadcast to all players
        self.send_to_player = send_to_player  # Send to specific player

        # Game settings
        self.turn_timer_seconds = turn_timer_seconds
        self.escape_timer_seconds = escape_timer_seconds
        self.shop_timer_seconds = shop_timer_seconds
        self.win_threshold = win_threshold

        # Players
        self.players: Dict[str, ServerPlayer] = {}
        self.player_order: List[str] = []  # Maintains join order

        # Game components
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.escape_predictor = EscapePredictor()
        self.event_manager = EventManager()
        self.hiding_manager = HidingManager()

        # Game state
        self.round_num = 0
        self.current_phase = GamePhase.LOBBY
        self.game_over = False
        self.winner: Optional[ServerPlayer] = None
        self.last_ai_search_location: Optional[Location] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

        # Round state
        self.pending_choices = PendingChoices()
        self.caught_players_this_round: List[tuple] = []  # (player, location, points)

        # Timers
        self._timer_task: Optional[asyncio.Task] = None

    @property
    def alive_players(self) -> List[ServerPlayer]:
        """Get all alive players."""
        return [p for p in self.players.values() if p.alive]

    @property
    def connected_players(self) -> List[ServerPlayer]:
        """Get all connected players."""
        return [p for p in self.players.values() if p.connected]

    def get_player(self, player_id: str) -> Optional[ServerPlayer]:
        """Get player by ID."""
        return self.players.get(player_id)

    async def add_player(self, player_id: str, username: str, profile_id: Optional[str] = None) -> ServerPlayer:
        """Add a player to the game."""
        if player_id in self.players:
            # Player reconnecting
            self.players[player_id].connected = True
            return self.players[player_id]

        player_index = len(self.player_order)
        player = ServerPlayer(
            player_id=player_id,
            username=username,
            player_index=player_index,
            profile_id=profile_id
        )
        self.players[player_id] = player
        self.player_order.append(player_id)

        return player

    async def remove_player(self, player_id: str):
        """Mark player as disconnected."""
        if player_id in self.players:
            self.players[player_id].connected = False

    async def set_player_ready(self, player_id: str, ready: bool) -> bool:
        """Set player ready status."""
        if player_id not in self.players:
            return False
        self.players[player_id].ready = ready
        return True

    def all_players_ready(self) -> bool:
        """Check if all connected players are ready.

        Allows single player mode (1 player) or multiplayer (2+ players).
        """
        connected = self.connected_players
        return len(connected) >= 1 and all(p.ready for p in connected)

    async def start_game(self):
        """Start the game."""
        if self.current_phase != GamePhase.LOBBY:
            return

        self.started_at = datetime.now(timezone.utc)

        # Get AI status
        ai_status = {
            "ml_active": self.ai.use_ml,
            "games_trained": 0,
        }
        if self.ai.use_ml and hasattr(self.ai, 'ml_trainer') and self.ai.ml_trainer:
            info = self.ai.ml_trainer.get_model_info()
            ai_status["games_trained"] = info.get('num_games', 0)

        # Build location info
        locations = []
        for loc in self.location_manager.get_all():
            locations.append({
                "name": loc.name,
                "emoji": loc.emoji,
                "min_points": loc.min_points,
                "max_points": loc.max_points,
            })

        # Broadcast game started
        await self.broadcast(game_started_message(
            game_id=self.game_id,
            players=[p.to_public_dict() for p in self.players.values()],
            locations=locations,
            ai_status=ai_status,
            settings={
                "turn_timer": self.turn_timer_seconds,
                "escape_timer": self.escape_timer_seconds,
                "shop_timer": self.shop_timer_seconds,
                "win_threshold": self.win_threshold,
            }
        ))

        # Start first round
        await self.start_round()

    async def start_round(self):
        """Start a new round."""
        self.round_num += 1
        self.caught_players_this_round = []

        # Reset pending choices
        self.pending_choices = PendingChoices()
        for player in self.alive_players:
            self.pending_choices.location_choices[player.player_id] = None
            self.pending_choices.shop_done[player.player_id] = False

        # Generate events
        game_state = {
            'round_num': self.round_num,
            'max_player_score': max((p.points for p in self.alive_players), default=0),
            'catches_last_3_rounds': self._count_recent_catches()
        }
        newly_spawned = self.event_manager.generate_events(
            game_state,
            self.location_manager.get_all()
        )

        # Build active events list
        active_events = self._build_active_events_list()

        # Build standings
        standings = self._build_standings()

        # Start shop phase
        self.current_phase = GamePhase.SHOP

        await self.broadcast(phase_change_message(
            new_phase=GamePhase.SHOP.value,
            round_num=self.round_num,
            data={
                "new_events": [{"name": e.name, "location": e.affected_location.name, "emoji": e.emoji} for e in newly_spawned],
            }
        ))

        # Send shop state to each player
        await self._send_shop_states()

        # Start shop timer
        await self._start_timer(self.shop_timer_seconds, self._on_shop_timer_expired)

    async def _send_shop_states(self):
        """Send shop state to each alive player."""
        available_passives = []
        for passive in PassiveShop.get_all_passives():
            available_passives.append({
                "id": passive.type.value,
                "name": passive.name,
                "cost": passive.cost,
                "description": passive.description,
                "emoji": passive.emoji,
                "category": passive.category,
            })

        for player in self.alive_players:
            owned = [p.type.value for p in player.get_passives()]
            await self.send_to_player(player.player_id, shop_state_message(
                player_id=player.player_id,
                player_points=player.points,
                available_passives=available_passives,
                owned_passives=owned,
                timer_seconds=self.shop_timer_seconds
            ))

    async def handle_shop_purchase(self, player_id: str, passive_id: str) -> bool:
        """Handle a shop purchase request."""
        player = self.get_player(player_id)
        if not player or not player.alive:
            return False

        if self.current_phase != GamePhase.SHOP:
            await self.send_to_player(player_id, error_message("INVALID_PHASE", "Shop is not open"))
            return False

        try:
            passive_type = PassiveType(passive_id)
            passive = PassiveShop.get_passive(passive_type)
        except (ValueError, KeyError):
            await self.send_to_player(player_id, purchase_result_message(
                player_id=player_id,
                success=False,
                error="Invalid passive"
            ))
            return False

        if passive is None:
            await self.send_to_player(player_id, purchase_result_message(
                player_id=player_id,
                success=False,
                error="Passive not found"
            ))
            return False

        if player.has_passive(passive_type):
            await self.send_to_player(player_id, purchase_result_message(
                player_id=player_id,
                success=False,
                error="Already owned"
            ))
            return False

        if player.points < passive.cost:
            await self.send_to_player(player_id, purchase_result_message(
                player_id=player_id,
                success=False,
                error="Not enough points"
            ))
            return False

        # Purchase successful
        player.buy_passive(passive)

        await self.send_to_player(player_id, purchase_result_message(
            player_id=player_id,
            success=True,
            passive_name=passive.name,
            new_points=player.points
        ))

        return True

    async def handle_shop_done(self, player_id: str) -> bool:
        """Handle player finishing shopping."""
        if self.current_phase != GamePhase.SHOP:
            return False

        player = self.get_player(player_id)
        if not player or not player.alive:
            return False

        self.pending_choices.shop_done[player_id] = True

        # Check if all players done shopping
        all_done = all(
            self.pending_choices.shop_done.get(p.player_id, False)
            for p in self.alive_players
            if p.connected
        )

        if all_done:
            await self._cancel_timer()
            await self._start_choosing_phase()

        return True

    async def _on_shop_timer_expired(self):
        """Handle shop timer expiration."""
        if self.current_phase != GamePhase.SHOP:
            return
        await self._start_choosing_phase()

    async def _start_choosing_phase(self):
        """Start the location choosing phase."""
        self.current_phase = GamePhase.CHOOSING

        # Build active events and standings
        active_events = self._build_active_events_list()
        standings = self._build_standings()

        await self.broadcast(round_start_message(
            round_num=self.round_num,
            timer_seconds=self.turn_timer_seconds,
            server_timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            active_events=active_events,
            new_events=[],
            standings=standings,
            previous_ai_location=self.last_ai_search_location.name if self.last_ai_search_location else None
        ))

        # Start turn timer
        await self._start_timer(self.turn_timer_seconds, self._on_turn_timer_expired)

    async def submit_location_choice(self, player_id: str, location_index: int) -> bool:
        """Submit a player's location choice."""
        if self.current_phase != GamePhase.CHOOSING:
            return False

        player = self.get_player(player_id)
        if not player or not player.alive:
            return False

        if self.pending_choices.location_choices.get(player_id) is not None:
            return False  # Already submitted

        # Validate location index
        if location_index < 0 or location_index >= len(self.location_manager.get_all()):
            return False

        self.pending_choices.location_choices[player_id] = location_index

        # Broadcast that player submitted (without revealing choice)
        await self.broadcast(player_submitted_message(
            player_id=player_id,
            username=player.username
        ))

        # Check if all alive players have submitted
        all_submitted = all(
            self.pending_choices.location_choices.get(p.player_id) is not None
            for p in self.alive_players
            if p.connected
        )

        if all_submitted:
            await self._cancel_timer()
            await self.broadcast(all_choices_locked_message(
                players_submitted=[p.username for p in self.alive_players if p.connected]
            ))
            await self.resolve_round()

        return True

    async def _on_turn_timer_expired(self):
        """Handle turn timer expiration - assign random choices."""
        if self.current_phase != GamePhase.CHOOSING:
            return

        # Assign random choices to players who haven't submitted
        for player in self.alive_players:
            if self.pending_choices.location_choices.get(player.player_id) is None:
                random_index = random.randint(0, len(self.location_manager.get_all()) - 1)
                self.pending_choices.location_choices[player.player_id] = random_index

                await self.broadcast(player_timeout_message(
                    player_id=player.player_id,
                    username=player.username
                ))

        await self.resolve_round()

    async def resolve_round(self):
        """Resolve the round after all choices are in."""
        self.current_phase = GamePhase.AI_THINKING

        await self.broadcast(phase_change_message(
            new_phase=GamePhase.AI_THINKING.value,
            round_num=self.round_num
        ))

        await self.broadcast(ai_analyzing_message(duration_ms=2000))
        await asyncio.sleep(1)  # Brief pause for dramatic effect

        self.current_phase = GamePhase.RESOLVING

        # Build player choices map
        player_choices: Dict[ServerPlayer, Location] = {}
        for player in self.alive_players:
            location_index = self.pending_choices.location_choices.get(player.player_id)
            if location_index is not None:
                location = self.location_manager.get_location(location_index)
                player_choices[player] = location

        # AI decides where to search
        search_location, predictions, ai_reasoning = self._ai_decide_search(player_choices)

        # Build round results
        player_results = []
        self.caught_players_this_round = []

        for player in self.alive_players:
            chosen_location = player_choices.get(player)
            if not chosen_location:
                continue

            prediction = predictions.get(player, (None, 0.0, ""))
            # AI predictor returns (location_name_str, confidence, reasoning)
            predicted_loc_name = prediction[0] if prediction[0] else None
            confidence = prediction[1] if len(prediction) > 1 else 0.0
            pred_reasoning = prediction[2] if len(prediction) > 2 else ""

            # Roll points
            base_roll = chosen_location.roll_points()
            location_points = self.event_manager.apply_point_modifier(chosen_location, base_roll)

            # Apply High Roller passive effect
            high_roller_effect = player.passive_manager.get_high_roller_effect(chosen_location.name)
            high_roller_result = None
            if high_roller_effect:
                if random.random() < high_roller_effect['bust_chance']:
                    location_points = 0
                    high_roller_result = "bust"
                else:
                    bonus = int(location_points * high_roller_effect['point_bonus'])
                    location_points += bonus
                    high_roller_result = "win"

            # Check if caught
            caught = (chosen_location.name == search_location.name)

            # Check event effects
            special_effect = self.event_manager.get_special_effect(chosen_location)
            immunity_triggered = False
            alarm_triggered = False

            if special_effect == "guaranteed_catch" and not caught:
                if random.random() < 0.3:
                    caught = True
                    alarm_triggered = True

            if special_effect == "immunity" and caught:
                caught = False
                immunity_triggered = True

            result = {
                "player_id": player.player_id,
                "username": player.username,
                "location": chosen_location.name,
                "location_emoji": chosen_location.emoji,
                "prediction": predicted_loc_name,
                "confidence": confidence,
                "prediction_reasoning": pred_reasoning,
                "caught": caught,
                "base_points": base_roll,
                "modified_points": location_points,
                "high_roller_result": high_roller_result,
                "immunity_triggered": immunity_triggered,
                "alarm_triggered": alarm_triggered,
            }

            if caught:
                self.caught_players_this_round.append((player, chosen_location, location_points))
                result["escape_required"] = True
            else:
                # Award points
                player.add_points(location_points)
                player.record_choice(chosen_location.name, self.round_num, False, location_points, base_roll)
                result["points_earned"] = location_points
                result["total_points"] = player.points

            player_results.append(result)

        # Update last AI search location for next round display
        self.last_ai_search_location = search_location

        # Broadcast round result
        await self.broadcast(round_result_message(
            round_num=self.round_num,
            ai_search_location=search_location.name,
            ai_search_emoji=search_location.emoji,
            ai_reasoning=ai_reasoning,
            player_results=player_results,
            standings=self._build_standings()
        ))

        # Handle escape phases for caught players
        if self.caught_players_this_round:
            await self._handle_escape_phases()
        else:
            await self._finish_round()

    def _ai_decide_search(self, player_choices: Dict[ServerPlayer, Location]) -> tuple:
        """AI decides where to search using the existing AI predictor."""
        # Build list of players in format expected by predictor
        # We need to create wrapper objects that match the Player interface
        class PlayerWrapper:
            """Wrapper to make ServerPlayer compatible with AI predictor."""
            def __init__(self, server_player: ServerPlayer):
                self.sp = server_player
                self.name = server_player.username
                self.points = server_player.points
                self.alive = server_player.alive
                self.profile_id = server_player.profile_id
                self.choice_history = server_player.choice_history
                self.round_history = server_player.round_history
                self.hiding_stats = server_player.hiding_stats
                self.passive_manager = server_player.passive_manager

            def has_passive(self, passive_type: PassiveType) -> bool:
                return self.sp.has_passive(passive_type)

            def get_passives(self):
                return self.sp.get_passives()

            def get_behavior_summary(self):
                return self.sp.get_behavior_summary()

        wrapped_players = [PlayerWrapper(p) for p in player_choices.keys()]

        if not wrapped_players:
            random_loc = random.choice(self.location_manager.get_all())
            return random_loc, {}, "No players to search for"

        # Use the AI predictor
        search_location, predictions_raw, ai_reasoning = self.ai.decide_search_location(
            wrapped_players,
            event_manager=self.event_manager
        )

        # Convert predictions to use ServerPlayer keys
        predictions = {}
        for wrapped, pred in predictions_raw.items():
            for server_player in player_choices.keys():
                if server_player.username == wrapped.name:
                    predictions[server_player] = pred
                    break

        return search_location, predictions, ai_reasoning

    async def _handle_escape_phases(self):
        """Handle escape phases for all caught players."""
        self.current_phase = GamePhase.ESCAPE

        for player, location, points in self.caught_players_this_round:
            await self._handle_single_escape(player, location, points)

        await self._finish_round()

    async def _handle_single_escape(self, player: ServerPlayer, location: Location, points: int):
        """Handle escape phase for a single caught player."""
        # Get escape options
        escape_options = self.hiding_manager.get_escape_options_for_location(location.name)

        if not escape_options:
            # No escape options - eliminated
            player.alive = False
            await self.broadcast(player_eliminated_message(
                player_id=player.player_id,
                username=player.username,
                final_score=player.points
            ))
            return

        # Reset escape choice tracking
        self.pending_choices.escape_choices[player.player_id] = None

        # AI predicts escape choice
        ai_prediction, ai_confidence, ai_reasoning = self.escape_predictor.predict_escape_option(
            player, escape_options, None  # No profile for now
        )

        # Notify player they're caught and need to escape
        await self.broadcast(player_caught_message(
            player_id=player.player_id,
            username=player.username,
            location=location.name,
            location_points=points
        ))

        # Send escape phase to player
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

        # Wait for escape choice with timeout
        try:
            choice = await asyncio.wait_for(
                self._wait_for_escape_choice(player.player_id),
                timeout=self.escape_timer_seconds
            )
        except asyncio.TimeoutError:
            # Random choice on timeout
            choice = random.choice(escape_options)['id']

        # Resolve escape
        await self._resolve_escape(player, location, points, choice, ai_prediction, ai_reasoning, escape_options)

    async def _wait_for_escape_choice(self, player_id: str) -> str:
        """Wait for a player's escape choice."""
        while True:
            await asyncio.sleep(0.1)
            choice = self.pending_choices.escape_choices.get(player_id)
            if choice is not None:
                return choice

    async def submit_escape_choice(self, player_id: str, option_id: str) -> bool:
        """Submit a player's escape choice."""
        if self.current_phase != GamePhase.ESCAPE:
            return False

        player = self.get_player(player_id)
        if not player:
            return False

        # Verify player is actually in escape phase
        caught_player_ids = [p.player_id for p, _, _ in self.caught_players_this_round]
        if player_id not in caught_player_ids:
            return False

        self.pending_choices.escape_choices[player_id] = option_id
        return True

    async def _resolve_escape(
        self,
        player: ServerPlayer,
        location: Location,
        location_points: int,
        chosen_option_id: str,
        ai_prediction_id: str,
        ai_reasoning: str,
        escape_options: List[Dict[str, Any]]
    ):
        """Resolve an escape attempt."""
        # Find the chosen option
        chosen_option = None
        for opt in escape_options:
            if opt['id'] == chosen_option_id:
                chosen_option = opt
                break

        if not chosen_option:
            chosen_option = escape_options[0]

        # Find AI prediction option name
        ai_prediction_name = ai_prediction_id
        for opt in escape_options:
            if opt['id'] == ai_prediction_id:
                ai_prediction_name = opt['name']
                break

        # Resolve using hiding manager
        result = self.hiding_manager.resolve_escape_attempt(
            chosen_option,
            ai_prediction_id,
            location_points
        )

        choice_type = chosen_option.get('type', 'hide')
        passive_saved = False

        # Apply passive escape bonuses if AI predicted correctly
        if not result['escaped']:
            if choice_type == 'hide':
                bonus = player.passive_manager.get_hide_bonus()
            else:
                bonus = player.passive_manager.get_run_bonus()

            if bonus > 0 and random.random() < bonus:
                result['escaped'] = True
                passive_saved = True
                base_retention = self.hiding_manager.get_option_keep_amount(chosen_option)
                if choice_type == 'run':
                    passive_retention = player.passive_manager.get_run_retention()
                    if passive_retention is not None:
                        quick_feet_bonus = passive_retention - 0.8
                        base_retention = min(base_retention + quick_feet_bonus, 1.0)
                result['points_awarded'] = int(location_points * base_retention)

        # Apply Quick Feet bonus for successful runs
        if result['escaped'] and choice_type == 'run' and not passive_saved:
            passive_retention = player.passive_manager.get_run_retention()
            if passive_retention is not None:
                base_retention = self.hiding_manager.get_option_keep_amount(chosen_option)
                quick_feet_bonus = passive_retention - 0.8
                retention = min(base_retention + quick_feet_bonus, 1.0)
                result['points_awarded'] = int(location_points * retention)

        # Update player state
        if result['escaped']:
            player.add_points(result['points_awarded'])
            player.record_choice(location.name, self.round_num, False, result['points_awarded'], location_points)
        else:
            player.alive = False
            player.record_choice(location.name, self.round_num, True, 0, location_points)

        # Add to result
        result['choice_type'] = choice_type
        result['passive_saved'] = passive_saved

        # Record escape attempt
        player.record_escape_attempt(result, self.round_num)
        self.escape_predictor.record_escape_choice(player, chosen_option_id)

        # Broadcast escape result
        await self.broadcast(escape_result_message(
            player_id=player.player_id,
            username=player.username,
            player_choice=chosen_option_id,
            player_choice_name=chosen_option.get('name', chosen_option_id),
            ai_prediction=ai_prediction_id,
            ai_prediction_name=ai_prediction_name,
            ai_reasoning=ai_reasoning,
            escaped=result['escaped'],
            points_awarded=result.get('points_awarded', 0),
            passive_saved=passive_saved
        ))

        if not result['escaped']:
            await self.broadcast(player_eliminated_message(
                player_id=player.player_id,
                username=player.username,
                final_score=player.points
            ))

    async def _finish_round(self):
        """Finish the current round."""
        self.current_phase = GamePhase.ROUND_END

        # Tick events
        self.event_manager.tick_events()

        # Check for game over
        if await self._check_game_over():
            return

        # Brief pause then start next round
        await asyncio.sleep(2)
        await self.start_round()

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

        # All eliminated - AI wins
        if len(alive) == 0:
            self.game_over = True
            self.winner = None
            self.finished_at = datetime.now(timezone.utc)
            await self._emit_game_over()
            return True

        # Last player standing with < win threshold continues
        # (In multiplayer, we don't ask - they keep playing)

        return False

    async def _emit_game_over(self):
        """Emit game over message."""
        self.current_phase = GamePhase.GAME_OVER

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

    def _build_active_events_list(self) -> List[Dict[str, Any]]:
        """Build list of active events for messages."""
        active_events = []
        for loc in self.location_manager.get_all():
            event = self.event_manager.get_location_event(loc)
            if event:
                active_events.append({
                    "location": loc.name,
                    "name": event.name,
                    "emoji": event.emoji,
                    "description": event.description,
                    "rounds_remaining": event.rounds_remaining,
                })
        return active_events

    def _build_standings(self) -> List[Dict[str, Any]]:
        """Build sorted standings list."""
        return sorted(
            [p.to_public_dict() for p in self.players.values()],
            key=lambda x: (-x['points'], not x['alive'])
        )

    def _count_recent_catches(self) -> int:
        """Count catches in last 3 rounds."""
        count = 0
        for player in self.players.values():
            recent = player.round_history[-3:] if len(player.round_history) >= 3 else player.round_history
            for entry in recent:
                if entry.get('caught', False):
                    count += 1
        return count

    async def _start_timer(self, seconds: int, callback: Callable[[], Awaitable[None]]):
        """Start a timer that calls callback when expired."""
        await self._cancel_timer()

        async def timer_task():
            await asyncio.sleep(seconds)
            await callback()

        self._timer_task = asyncio.create_task(timer_task())

    async def _cancel_timer(self):
        """Cancel the current timer."""
        if self._timer_task:
            self._timer_task.cancel()
            try:
                await self._timer_task
            except asyncio.CancelledError:
                pass
            self._timer_task = None

    async def send_game_state(self, player_id: str):
        """Send full game state to a player (for reconnection)."""
        await self.send_to_player(player_id, game_state_message(
            game_id=self.game_id,
            phase=self.current_phase.value,
            round_num=self.round_num,
            players=[p.to_public_dict() for p in self.players.values()],
            locations=[{
                "name": loc.name,
                "emoji": loc.emoji,
                "min_points": loc.min_points,
                "max_points": loc.max_points,
            } for loc in self.location_manager.get_all()],
            active_events=self._build_active_events_list(),
            settings={
                "turn_timer": self.turn_timer_seconds,
                "escape_timer": self.escape_timer_seconds,
                "shop_timer": self.shop_timer_seconds,
                "win_threshold": self.win_threshold,
            },
            previous_ai_location=self.last_ai_search_location.name if self.last_ai_search_location else None
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize game state for storage."""
        return {
            "game_id": self.game_id,
            "round_num": self.round_num,
            "game_over": self.game_over,
            "winner_id": self.winner.player_id if self.winner else None,
            "current_phase": self.current_phase.value,
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "player_order": self.player_order,
            "last_ai_search_location": self.last_ai_search_location.name if self.last_ai_search_location else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "settings": {
                "turn_timer_seconds": self.turn_timer_seconds,
                "escape_timer_seconds": self.escape_timer_seconds,
                "shop_timer_seconds": self.shop_timer_seconds,
                "win_threshold": self.win_threshold,
            }
        }
