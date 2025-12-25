"""Event system for dynamic location effects."""
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from game.locations import Location


@dataclass
class Event:
    """Represents a single location event with effects."""
    id: str
    name: str
    description: str
    emoji: str
    duration_rounds: int  # 1 or 2

    # Effect modifiers (config-based)
    point_modifier: Optional[Dict[str, Any]] = None  # {"type": "multiply"|"add", "value": number}
    risk_modifier: Optional[Dict[str, Any]] = None  # {"type": "multiply"|"multiply_capped", "value": number}
    special_effect: Optional[str] = None  # Special mechanics: "immunity", "guaranteed_catch"

    # State tracking (set when event is spawned)
    rounds_remaining: int = field(default=0, init=False)
    affected_location: Optional[Location] = field(default=None, init=False)

    def copy_with_location(self, location: Location) -> 'Event':
        """Create a copy of this event assigned to a location."""
        new_event = Event(
            id=self.id,
            name=self.name,
            description=self.description,
            emoji=self.emoji,
            duration_rounds=self.duration_rounds,
            point_modifier=self.point_modifier,
            risk_modifier=self.risk_modifier,
            special_effect=self.special_effect
        )
        new_event.rounds_remaining = self.duration_rounds
        new_event.affected_location = location
        return new_event

    def apply_point_modifier(self, points: int) -> int:
        """
        Apply point modifier to a point value.

        Args:
            points: Base points value

        Returns:
            Modified points value

        Supports:
            - {"type": "multiply", "value": 2.0}
            - {"type": "add", "value": 20}
        """
        if self.point_modifier is None:
            return points

        if isinstance(self.point_modifier, dict):
            modifier_type = self.point_modifier.get('type')
            value = self.point_modifier.get('value', 1.0)

            if modifier_type == 'multiply':
                return int(points * value)
            elif modifier_type == 'add':
                return points + int(value)
            else:
                return points

        return points

    def apply_risk_modifier(self, probability: float) -> float:
        """
        Apply risk modifier to a probability value.

        Args:
            probability: Base probability (0.0-1.0)

        Returns:
            Modified probability value

        Supports:
            - {"type": "multiply", "value": 0.5}
            - {"type": "multiply_capped", "value": 2.5, "cap": 0.95}
        """
        if self.risk_modifier is None:
            return probability

        if isinstance(self.risk_modifier, dict):
            modifier_type = self.risk_modifier.get('type')
            value = self.risk_modifier.get('value', 1.0)

            if modifier_type == 'multiply':
                return probability * value
            elif modifier_type == 'multiply_capped':
                cap = self.risk_modifier.get('cap', 1.0)
                return min(probability * value, cap)
            else:
                return probability

        return probability


class EventManager:
    """Manages active events and event generation."""

    def __init__(self, max_concurrent: Optional[int] = None):
        """
        Initialize EventManager.

        Args:
            max_concurrent: Maximum number of events that can be active simultaneously.
                          If None, loads from config (default: 2)
        """
        # Load config
        from game.config_loader import config

        # Load settings
        if max_concurrent is None:
            max_concurrent = config.get_events_settings().get('max_concurrent', 2)

        self.max_concurrent = max_concurrent
        self.active_events: List[Event] = []

        # Load spawn triggers from config
        spawn_triggers = config.get_events_settings().get('spawn_triggers', {})
        self.round_interval = spawn_triggers.get('round_interval', 3)
        self.high_score_threshold = spawn_triggers.get('high_score_threshold', 50)
        self.high_score_chance = spawn_triggers.get('high_score_chance', 0.3)
        self.catch_threshold = spawn_triggers.get('catch_threshold', 2)
        self.catch_chance = spawn_triggers.get('catch_chance', 0.4)
        self.first_round_chance = spawn_triggers.get('first_round_chance', 0.5)

        # Load event pool from config
        self.event_pool = self._create_event_pool()

    def _create_event_pool(self) -> List[Event]:
        """Load all possible events from configuration."""
        from game.config_loader import config

        event_pool = []
        events_data = config.get_events_list()

        for event_data in events_data:
            event = Event(
                id=event_data['id'],
                name=event_data['name'],
                description=event_data['description'],
                emoji=event_data['emoji'],
                duration_rounds=event_data['duration_rounds'],
                point_modifier=event_data.get('point_modifier'),
                risk_modifier=event_data.get('risk_modifier'),
                special_effect=event_data.get('special_effect')
            )
            event_pool.append(event)

        return event_pool

    def generate_events(self, game_state: Dict[str, Any],
                       available_locations: List[Location]) -> List[Event]:
        """
        Generate new events based on game state triggers.

        Args:
            game_state: Dict with keys: round_num, max_player_score, catches_last_3_rounds
            available_locations: List of all locations in the game

        Returns:
            List of newly spawned events
        """
        # Don't exceed max concurrent
        if len(self.active_events) >= self.max_concurrent:
            return []

        round_num = game_state.get('round_num', 0)
        max_score = game_state.get('max_player_score', 0)
        recent_catches = game_state.get('catches_last_3_rounds', 0)

        # State-based triggers (loaded from config)
        should_spawn = False

        # Round-based triggers
        if round_num % self.round_interval == 0 and round_num > 0:
            should_spawn = True

        # Score-based triggers
        if max_score > self.high_score_threshold and random.random() < self.high_score_chance:
            should_spawn = True

        # Catch-based triggers
        if recent_catches >= self.catch_threshold and random.random() < self.catch_chance:
            should_spawn = True

        # First round trigger
        if round_num == 1 and random.random() < self.first_round_chance:
            should_spawn = True

        newly_spawned = []
        if should_spawn:
            event = self._spawn_event(available_locations)
            if event:
                newly_spawned.append(event)

        return newly_spawned

    def _spawn_event(self, available_locations: List[Location]) -> Optional[Event]:
        """
        Spawn a random event at a random location.

        Args:
            available_locations: List of all locations

        Returns:
            The spawned event, or None if no location available
        """
        # Choose location that doesn't already have an event
        occupied_locations = {e.affected_location for e in self.active_events}
        free_locations = [loc for loc in available_locations
                         if loc not in occupied_locations]

        if not free_locations:
            return None

        # Select random location and random event
        location = random.choice(free_locations)
        event_template = random.choice(self.event_pool)

        # Create event instance with location
        new_event = event_template.copy_with_location(location)
        self.active_events.append(new_event)

        return new_event

    def get_location_event(self, location: Location) -> Optional[Event]:
        """
        Get active event for a location, if any.

        Args:
            location: The location to check

        Returns:
            The active event at this location, or None
        """
        for event in self.active_events:
            if event.affected_location == location:
                return event
        return None

    def tick_events(self) -> List[Event]:
        """
        Decrease event durations by 1 round, remove expired events.

        Returns:
            List of expired events
        """
        expired = []

        for event in self.active_events[:]:  # Copy to allow removal during iteration
            event.rounds_remaining -= 1
            if event.rounds_remaining <= 0:
                expired.append(event)
                self.active_events.remove(event)

        return expired

    def apply_point_modifier(self, location: Location, base_points: int) -> int:
        """
        Apply event point modifier to rolled points.

        Args:
            location: The location being looted
            base_points: The base points rolled

        Returns:
            Modified points after event effects
        """
        event = self.get_location_event(location)

        if event and event.point_modifier:
            return event.apply_point_modifier(base_points)

        return base_points

    def get_special_effect(self, location: Location) -> Optional[str]:
        """
        Get special effect for a location, if any.

        Args:
            location: The location to check

        Returns:
            Special effect string ("immunity", "guaranteed_catch") or None
        """
        event = self.get_location_event(location)
        return event.special_effect if event else None

    def has_active_events(self) -> bool:
        """Check if any events are currently active."""
        return len(self.active_events) > 0
