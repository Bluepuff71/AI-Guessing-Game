"""
Server-side game engine for online multiplayer.

This is an adapted version of game/engine.py that:
- Removes all UI dependencies
- Uses event emission for client communication
- Handles simultaneous turns with timers
- Supports async operations
- Provides state serialization for reconnection
"""

import asyncio
import random
import uuid
import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

# Add parent directory to path to import game logic
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from game.locations import LocationManager, Location
from game.events import EventManager
from game.hiding import HidingManager
from game.passives import PassiveShop
from ai.predictor import AIPredictor
from ai.escape_predictor import EscapePredictor

from .player import ServerPlayer


# Type alias for event emitter callback
EventEmitter = Callable[[str, Dict[str, Any]], Awaitable[None]]


@dataclass
class PendingChoices:
    """Tracks pending player choices for a round."""
    location_choices: Dict[uuid.UUID, Optional[int]] = field(default_factory=dict)
    escape_choices: Dict[uuid.UUID, Optional[str]] = field(default_factory=dict)
    submitted_players: set = field(default_factory=set)


class ServerGameEngine:
    """
    Server-side game engine for LOOT RUN online multiplayer.

    Unlike the local GameEngine, this version:
    - Does not import or call any UI functions
    - Emits events via WebSocket instead of printing
    - Handles simultaneous turns with configurable timers
    - Is fully async
    - Serializes state for reconnection support
    """

    def __init__(
        self,
        game_id: uuid.UUID,
        players: List[ServerPlayer],
        emit: EventEmitter,
        turn_timer_seconds: int = 30,
        escape_timer_seconds: int = 15,
        win_threshold: int = 100,
    ):
        self.game_id = game_id
        self.players = players
        self.emit = emit  # Callback to emit events to clients

        # Game settings
        self.turn_timer_seconds = turn_timer_seconds
        self.escape_timer_seconds = escape_timer_seconds
        self.win_threshold = win_threshold

        # Game components (reuse existing game logic)
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.escape_predictor = EscapePredictor()
        self.event_manager = EventManager()
        self.hiding_manager = HidingManager()

        # Game state
        self.round_num = 0
        self.game_over = False
        self.winner: Optional[ServerPlayer] = None
        self.last_ai_search_location: Optional[Location] = None
        self.started_at = datetime.now(timezone.utc)
        self.finished_at: Optional[datetime] = None

        # Round state
        self.pending_choices = PendingChoices()
        self.current_phase = "waiting"  # waiting, choosing, resolving, escape, finished

    @property
    def alive_players(self) -> List[ServerPlayer]:
        """Get all alive players."""
        return [p for p in self.players if p.alive]

    @property
    def connected_players(self) -> List[ServerPlayer]:
        """Get all connected players."""
        return [p for p in self.players if p.connected]

    def get_player(self, user_id: uuid.UUID) -> Optional[ServerPlayer]:
        """Get player by user ID."""
        for player in self.players:
            if player.user_id == user_id:
                return player
        return None

    async def start_game(self):
        """Initialize and start the game."""
        # Get AI status
        ai_status = {
            "ml_active": self.ai.use_ml,
            "games_trained": 0,
        }
        if self.ai.use_ml and hasattr(self.ai, 'ml_trainer'):
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

        # Emit game started event
        await self.emit("GAME_STARTED", {
            "game_id": str(self.game_id),
            "players": [p.to_public_dict() for p in self.players],
            "locations": locations,
            "ai_status": ai_status,
            "settings": {
                "turn_timer": self.turn_timer_seconds,
                "escape_timer": self.escape_timer_seconds,
                "win_threshold": self.win_threshold,
            }
        })

        # Start first round
        await self.start_round()

    async def start_round(self):
        """Start a new round."""
        self.round_num += 1
        self.current_phase = "choosing"

        # Reset pending choices
        self.pending_choices = PendingChoices()
        for player in self.alive_players:
            self.pending_choices.location_choices[player.user_id] = None

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

        # Build standings
        standings = sorted(
            [p.to_public_dict() for p in self.players],
            key=lambda x: (-x['points'], not x['alive'])
        )

        # Emit round start
        await self.emit("ROUND_START", {
            "round_num": self.round_num,
            "timer_seconds": self.turn_timer_seconds,
            "server_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "active_events": active_events,
            "new_events": [{"name": e.name, "location": e.affected_location.name} for e in newly_spawned],
            "standings": standings,
            "previous_ai_location": self.last_ai_search_location.name if self.last_ai_search_location else None,
        })

    async def submit_location_choice(self, user_id: uuid.UUID, location_index: int) -> bool:
        """Submit a player's location choice."""
        if self.current_phase != "choosing":
            return False

        player = self.get_player(user_id)
        if not player or not player.alive:
            return False

        if user_id in self.pending_choices.submitted_players:
            return False  # Already submitted

        # Validate location index
        if location_index < 0 or location_index >= len(self.location_manager.get_all()):
            return False

        self.pending_choices.location_choices[user_id] = location_index
        self.pending_choices.submitted_players.add(user_id)

        # Emit that player has submitted (without revealing choice)
        await self.emit("PLAYER_SUBMITTED", {
            "user_id": str(user_id),
            "username": player.username,
        })

        # Check if all alive players have submitted
        all_submitted = all(
            player.user_id in self.pending_choices.submitted_players
            for player in self.alive_players
            if player.connected
        )

        if all_submitted:
            await self.emit("ALL_CHOICES_LOCKED", {
                "players_submitted": [p.username for p in self.alive_players if p.connected]
            })
            # Resolve round
            await self.resolve_round()

        return True

    async def handle_timer_expired(self):
        """Handle turn timer expiration - assign random choices to missing players."""
        if self.current_phase != "choosing":
            return

        # Assign random choices to players who haven't submitted
        for player in self.alive_players:
            if player.user_id not in self.pending_choices.submitted_players:
                # Random location
                random_index = random.randint(0, len(self.location_manager.get_all()) - 1)
                self.pending_choices.location_choices[player.user_id] = random_index
                self.pending_choices.submitted_players.add(player.user_id)

                await self.emit("PLAYER_TIMEOUT", {
                    "user_id": str(player.user_id),
                    "username": player.username,
                    "assigned_random": True,
                })

        # Now resolve
        await self.resolve_round()

    async def resolve_round(self):
        """Resolve the round after all choices are in."""
        self.current_phase = "resolving"

        # Build player choices map
        player_choices: Dict[ServerPlayer, Location] = {}
        for player in self.alive_players:
            location_index = self.pending_choices.location_choices.get(player.user_id)
            if location_index is not None:
                location = self.location_manager.get_location(location_index)
                player_choices[player] = location

        # AI thinking animation
        await self.emit("AI_ANALYZING", {"duration_ms": 2000})
        await asyncio.sleep(1)  # Brief pause for dramatic effect

        # AI decides where to search
        # Need to create wrapper players for AI predictor (it expects original Player objects)
        # For now, we'll use a simplified prediction based on player history
        search_location = self._ai_decide_search(player_choices)
        predictions = self._ai_predict_players(player_choices)

        # Build round result
        player_results = []
        caught_players = []

        for player in self.alive_players:
            chosen_location = player_choices.get(player)
            if not chosen_location:
                continue

            predicted_loc, confidence = predictions.get(player.user_id, (None, 0.0))

            # Roll points
            base_roll = chosen_location.roll_points()
            location_points = self.event_manager.apply_point_modifier(chosen_location, base_roll)

            # Check if caught
            caught = (chosen_location.name == search_location.name)

            # Check event effects
            special_effect = self.event_manager.get_special_effect(chosen_location)
            if special_effect == "guaranteed_catch" and not caught:
                if random.random() < 0.3:
                    caught = True
            if special_effect == "immunity" and caught:
                caught = False

            result = {
                "user_id": str(player.user_id),
                "username": player.username,
                "location": chosen_location.name,
                "location_emoji": chosen_location.emoji,
                "prediction": predicted_loc.name if predicted_loc else None,
                "confidence": confidence,
                "caught": caught,
                "base_points": base_roll,
                "modified_points": location_points,
            }

            if caught:
                caught_players.append((player, chosen_location, location_points))
                result["escape_required"] = True
            else:
                # Award points
                player.add_points(location_points)
                player.record_choice(chosen_location.name, self.round_num, False, location_points, base_roll)
                result["points_earned"] = location_points
                result["total_points"] = player.points

            player_results.append(result)

        # Emit round result
        await self.emit("ROUND_RESULT", {
            "round_num": self.round_num,
            "ai_search_location": search_location.name,
            "ai_search_emoji": search_location.emoji,
            "player_results": player_results,
            "standings": sorted([p.to_public_dict() for p in self.players], key=lambda x: -x['points']),
        })

        # Handle escape phases for caught players
        for player, location, points in caught_players:
            await self._handle_escape_phase(player, location, points)

        # Update AI search location for next round display
        self.last_ai_search_location = search_location

        # Tick events
        self.event_manager.tick_events()

        # Check game over
        if await self._check_game_over():
            return

        # Start next round
        await asyncio.sleep(2)  # Brief pause between rounds
        await self.start_round()

    def _ai_decide_search(self, player_choices: Dict[ServerPlayer, Location]) -> Location:
        """AI decides which location to search."""
        # Simple strategy: search the most popular location, weighted by player points
        location_weights = {}
        for player, location in player_choices.items():
            weight = 1 + (player.points / 20)  # Higher scoring players are more valuable targets
            location_weights[location.name] = location_weights.get(location.name, 0) + weight

        if not location_weights:
            # Random if no choices
            return random.choice(self.location_manager.get_all())

        # Pick highest weighted location
        best_location_name = max(location_weights.keys(), key=lambda x: location_weights[x])
        for loc in self.location_manager.get_all():
            if loc.name == best_location_name:
                return loc

        return random.choice(self.location_manager.get_all())

    def _ai_predict_players(self, player_choices: Dict[ServerPlayer, Location]) -> Dict[uuid.UUID, tuple]:
        """Generate AI predictions for each player."""
        predictions = {}
        for player in player_choices.keys():
            # Simple prediction based on history
            if player.choice_history:
                # Predict based on most common choice
                from collections import Counter
                counts = Counter(player.choice_history)
                most_common = counts.most_common(1)[0][0]
                confidence = counts[most_common] / len(player.choice_history)

                for loc in self.location_manager.get_all():
                    if loc.name == most_common:
                        predictions[player.user_id] = (loc, min(confidence + 0.2, 0.95))
                        break
                else:
                    predictions[player.user_id] = (random.choice(self.location_manager.get_all()), 0.3)
            else:
                predictions[player.user_id] = (random.choice(self.location_manager.get_all()), 0.2)

        return predictions

    async def _handle_escape_phase(self, player: ServerPlayer, location: Location, points: int):
        """Handle escape phase for a caught player."""
        self.current_phase = "escape"

        # Get escape options
        escape_options = self.hiding_manager.get_escape_options_for_location(location.name)

        if not escape_options:
            # No escape - eliminated
            player.alive = False
            await self.emit("PLAYER_ELIMINATED", {
                "user_id": str(player.user_id),
                "username": player.username,
                "final_score": player.points,
            })
            return

        # AI predicts escape choice
        ai_prediction = random.choice(escape_options)  # Simplified for now

        # Reset escape choice tracking
        self.pending_choices.escape_choices[player.user_id] = None

        # Emit escape phase start
        await self.emit("ESCAPE_PHASE", {
            "user_id": str(player.user_id),
            "username": player.username,
            "location": location.name,
            "location_points": points,
            "escape_options": [
                {
                    "id": opt["id"],
                    "name": opt["name"],
                    "type": opt.get("type", "hide"),
                    "emoji": opt.get("emoji", ""),
                }
                for opt in escape_options
            ],
            "timer_seconds": self.escape_timer_seconds,
        })

        # Wait for escape choice (with timeout)
        # In real implementation, this would be handled by the WebSocket handler
        # For now, we'll let the handler call submit_escape_choice

    async def submit_escape_choice(self, user_id: uuid.UUID, option_id: str) -> bool:
        """Submit a player's escape choice."""
        if self.current_phase != "escape":
            return False

        player = self.get_player(user_id)
        if not player:
            return False

        if self.pending_choices.escape_choices.get(user_id) is not None:
            return False  # Already submitted

        self.pending_choices.escape_choices[user_id] = option_id

        # Resolve escape
        await self._resolve_escape(player, option_id)
        return True

    async def _resolve_escape(self, player: ServerPlayer, chosen_option_id: str):
        """Resolve an escape attempt."""
        # Get the location and points from pending state
        # This is simplified - in full implementation would track this properly

        # Simplified resolution: 50% chance to escape
        escaped = random.random() > 0.5
        points_awarded = 0

        if escaped:
            # Keep some points
            points_awarded = int(20 * 0.8)  # Placeholder
            player.add_points(points_awarded)
        else:
            player.alive = False

        await self.emit("ESCAPE_RESULT", {
            "user_id": str(player.user_id),
            "username": player.username,
            "player_choice": chosen_option_id,
            "ai_prediction": "some_option",  # Placeholder
            "escaped": escaped,
            "points_awarded": points_awarded if escaped else 0,
        })

        if not escaped:
            await self.emit("PLAYER_ELIMINATED", {
                "user_id": str(player.user_id),
                "username": player.username,
                "final_score": player.points,
            })

        # Continue to next round or game over check
        self.current_phase = "resolving"

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

        return False

    async def _emit_game_over(self):
        """Emit game over event."""
        duration = (self.finished_at - self.started_at).total_seconds() if self.finished_at else 0

        await self.emit("GAME_OVER", {
            "winner": {
                "user_id": str(self.winner.user_id),
                "username": self.winner.username,
                "score": self.winner.points,
            } if self.winner else None,
            "ai_wins": self.winner is None,
            "final_standings": sorted([p.to_public_dict() for p in self.players], key=lambda x: -x['points']),
            "rounds_played": self.round_num,
            "game_duration_seconds": int(duration),
        })

    def _count_recent_catches(self) -> int:
        """Count catches in last 3 rounds."""
        count = 0
        for player in self.players:
            recent = player.round_history[-3:] if len(player.round_history) >= 3 else player.round_history
            for entry in recent:
                if entry.get('caught', False):
                    count += 1
        return count

    def to_dict(self) -> Dict[str, Any]:
        """Serialize game state for storage/reconnection."""
        return {
            "game_id": str(self.game_id),
            "round_num": self.round_num,
            "game_over": self.game_over,
            "winner_user_id": str(self.winner.user_id) if self.winner else None,
            "current_phase": self.current_phase,
            "players": [p.to_dict() for p in self.players],
            "last_ai_search_location": self.last_ai_search_location.name if self.last_ai_search_location else None,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "settings": {
                "turn_timer_seconds": self.turn_timer_seconds,
                "escape_timer_seconds": self.escape_timer_seconds,
                "win_threshold": self.win_threshold,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], emit: EventEmitter) -> 'ServerGameEngine':
        """Restore game state from dictionary."""
        players = [ServerPlayer.from_dict(p) for p in data['players']]

        engine = cls(
            game_id=uuid.UUID(data['game_id']),
            players=players,
            emit=emit,
            turn_timer_seconds=data['settings']['turn_timer_seconds'],
            escape_timer_seconds=data['settings']['escape_timer_seconds'],
            win_threshold=data['settings']['win_threshold'],
        )

        engine.round_num = data['round_num']
        engine.game_over = data['game_over']
        engine.current_phase = data['current_phase']
        engine.started_at = datetime.fromisoformat(data['started_at'])

        if data['finished_at']:
            engine.finished_at = datetime.fromisoformat(data['finished_at'])

        if data['winner_user_id']:
            engine.winner = engine.get_player(uuid.UUID(data['winner_user_id']))

        if data['last_ai_search_location']:
            for loc in engine.location_manager.get_all():
                if loc.name == data['last_ai_search_location']:
                    engine.last_ai_search_location = loc
                    break

        return engine
