# server/events.py
"""Event types for the event-driven game engine."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class GameEventType(Enum):
    """All possible game events."""

    # Player connection events
    PLAYER_JOIN = auto()
    PLAYER_LEAVE = auto()
    PLAYER_READY = auto()
    PLAYER_UNREADY = auto()

    # Game lifecycle
    GAME_START = auto()
    ROUND_START = auto()
    ROUND_COMPLETE = auto()
    GAME_OVER = auto()

    # Shop phase
    SHOP_PURCHASE = auto()
    SHOP_SKIP = auto()
    SHOP_TIMEOUT = auto()

    # Choosing phase
    LOCATION_CHOICE = auto()
    CHOICE_TIMEOUT = auto()
    ALL_CHOICES_IN = auto()

    # Resolution
    AI_DECISION_COMPLETE = auto()

    # Escape phase
    ESCAPE_START = auto()
    ESCAPE_CHOICE = auto()
    ESCAPE_TIMEOUT = auto()
    ESCAPE_RESOLVED = auto()
    ALL_ESCAPES_RESOLVED = auto()


@dataclass
class GameEvent:
    """An event that triggers a state transition."""

    type: GameEventType
    data: Dict[str, Any] = field(default_factory=dict)
    player_id: Optional[str] = None
