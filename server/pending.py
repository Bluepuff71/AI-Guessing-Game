# server/pending.py
"""Pending state trackers for the game engine."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PendingChoices:
    """Tracks pending location choices for a round."""

    _choices: Dict[str, int] = field(default_factory=dict)
    _shop_done: Dict[str, bool] = field(default_factory=dict)

    def record_choice(self, player_id: str, location_index: int) -> None:
        """Record a player's location choice."""
        self._choices[player_id] = location_index

    def get_choice(self, player_id: str) -> Optional[int]:
        """Get a player's choice, or None if not yet made."""
        return self._choices.get(player_id)

    def has_all_choices(self, player_ids: List[str]) -> bool:
        """Check if all specified players have made choices."""
        return all(pid in self._choices for pid in player_ids)

    def get_all_choices(self) -> Dict[str, int]:
        """Get all recorded choices."""
        return dict(self._choices)

    def record_shop_done(self, player_id: str) -> None:
        """Record that a player is done shopping."""
        self._shop_done[player_id] = True

    def is_shop_done(self, player_id: str) -> bool:
        """Check if a player is done shopping."""
        return self._shop_done.get(player_id, False)

    def all_shop_done(self, player_ids: List[str]) -> bool:
        """Check if all specified players are done shopping."""
        return all(self._shop_done.get(pid, False) for pid in player_ids)

    def clear(self) -> None:
        """Clear all pending choices."""
        self._choices.clear()
        self._shop_done.clear()


@dataclass
class PendingEscape:
    """Tracks a single player's pending escape."""

    player_id: str
    location_name: str
    location_points: int
    escape_options: List[Dict[str, Any]]
    ai_prediction: str
    ai_reasoning: str
    choice_received: bool = False
    chosen_option_id: Optional[str] = None


@dataclass
class PendingEscapes:
    """Tracks all pending escapes for a round."""

    _escapes: Dict[str, PendingEscape] = field(default_factory=dict)

    def add_escape(
        self,
        player_id: str,
        location_name: str,
        location_points: int,
        escape_options: List[Dict[str, Any]],
        ai_prediction: str,
        ai_reasoning: str
    ) -> None:
        """Add a pending escape for a player."""
        self._escapes[player_id] = PendingEscape(
            player_id=player_id,
            location_name=location_name,
            location_points=location_points,
            escape_options=escape_options,
            ai_prediction=ai_prediction,
            ai_reasoning=ai_reasoning
        )

    def has_pending(self, player_id: str) -> bool:
        """Check if a player has a pending escape."""
        return player_id in self._escapes

    def get_escape(self, player_id: str) -> Optional[PendingEscape]:
        """Get a player's pending escape."""
        return self._escapes.get(player_id)

    def record_choice(self, player_id: str, option_id: str) -> bool:
        """Record a player's escape choice. Returns False if no pending escape."""
        escape = self._escapes.get(player_id)
        if not escape:
            return False
        escape.choice_received = True
        escape.chosen_option_id = option_id
        return True

    def all_resolved(self) -> bool:
        """Check if all pending escapes have choices."""
        return all(e.choice_received for e in self._escapes.values())

    def get_unresolved_player_ids(self) -> List[str]:
        """Get player IDs with unresolved escapes."""
        return [pid for pid, e in self._escapes.items() if not e.choice_received]

    def get_all(self) -> List[PendingEscape]:
        """Get all pending escapes."""
        return list(self._escapes.values())

    def clear(self) -> None:
        """Clear all pending escapes."""
        self._escapes.clear()
