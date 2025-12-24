"""Event system for dynamic location effects."""
import random
from dataclasses import dataclass, field
from typing import Callable, Optional, List, Dict, Any
from game.locations import Location


@dataclass
class Event:
    """Represents a single location event with effects."""
    id: str
    name: str
    description: str
    emoji: str
    duration_rounds: int  # 1 or 2

    # Effect callbacks
    point_modifier: Optional[Callable[[int], int]] = None  # Modify points rolled
    risk_modifier: Optional[Callable[[float], float]] = None  # Modify AI prediction probability
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


class EventManager:
    """Manages active events and event generation."""

    def __init__(self, max_concurrent: Optional[int] = None):
        """
        Initialize EventManager.

        Args:
            max_concurrent: Maximum number of events that can be active simultaneously.
                          If None, loads from config (default: 2)
        """
        # Load config if not provided
        if max_concurrent is None:
            from game.config_loader import ConfigLoader
            config = ConfigLoader()
            max_concurrent = config.get('events', 'max_concurrent', default=2)

        self.max_concurrent = max_concurrent
        self.active_events: List[Event] = []
        self.event_pool = self._create_event_pool()

    def _create_event_pool(self) -> List[Event]:
        """Define all possible events with balanced distribution."""
        return [
            # Point modifier events (40% - 4 events)
            Event(
                id="jackpot",
                name="Jackpot Night",
                description="Points doubled at this location!",
                emoji="💰",
                duration_rounds=1,
                point_modifier=lambda pts: pts * 2
            ),
            Event(
                id="clearance",
                name="Clearance Sale",
                description="50% more points",
                emoji="🏷️",
                duration_rounds=2,
                point_modifier=lambda pts: int(pts * 1.5)
            ),
            Event(
                id="lockdown",
                name="Security Lockdown",
                description="Points reduced by 30%",
                emoji="🚨",
                duration_rounds=1,
                point_modifier=lambda pts: int(pts * 0.7)
            ),
            Event(
                id="bonus_stash",
                name="Bonus Stash",
                description="+20 flat bonus points",
                emoji="🎁",
                duration_rounds=1,
                point_modifier=lambda pts: pts + 20
            ),

            # Risk modifier events (40% - 4 events)
            Event(
                id="distraction",
                name="Major Distraction",
                description="AI 50% less likely to search here",
                emoji="🎭",
                duration_rounds=1,
                risk_modifier=lambda prob: prob * 0.5
            ),
            Event(
                id="tip_off",
                name="Anonymous Tip",
                description="AI highly likely to search here",
                emoji="📞",
                duration_rounds=1,
                risk_modifier=lambda prob: min(prob * 2.5, 0.95)
            ),
            Event(
                id="patrol",
                name="Police Patrol",
                description="AI moderately more likely to search",
                emoji="🚔",
                duration_rounds=2,
                risk_modifier=lambda prob: prob * 1.4
            ),
            Event(
                id="all_clear",
                name="All Clear",
                description="AI 30% less likely to search",
                emoji="✅",
                duration_rounds=2,
                risk_modifier=lambda prob: prob * 0.7
            ),

            # Special mechanics events (20% - 2 events)
            Event(
                id="insurance",
                name="Insurance Active",
                description="Can't be caught here (still get points)",
                emoji="🛡️",
                duration_rounds=1,
                special_effect="immunity"
            ),
            Event(
                id="silent_alarm",
                name="Silent Alarm",
                description="Guaranteed catch if chosen",
                emoji="⚠️",
                duration_rounds=1,
                special_effect="guaranteed_catch"
            ),
        ]

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

        # State-based triggers
        should_spawn = False

        # Round-based triggers (every 3 rounds)
        if round_num % 3 == 0 and round_num > 0:
            should_spawn = True

        # Score-based triggers (30% chance if someone over 50)
        if max_score > 50 and random.random() < 0.3:
            should_spawn = True

        # Catch-based triggers (40% chance after 2+ catches in last 3 rounds)
        if recent_catches >= 2 and random.random() < 0.4:
            should_spawn = True

        # First round trigger (50% chance to start with an event)
        if round_num == 1 and random.random() < 0.5:
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
            return event.point_modifier(base_points)

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
