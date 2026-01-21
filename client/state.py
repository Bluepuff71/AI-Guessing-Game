"""Client-side game state management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ClientPhase(Enum):
    """Client UI phases."""
    MAIN_MENU = "main_menu"
    CONNECTING = "connecting"
    LOBBY = "lobby"
    SHOP = "shop"
    CHOOSING = "choosing"
    WAITING = "waiting"
    RESULTS = "results"
    ESCAPE = "escape"
    GAME_OVER = "game_over"


@dataclass
class PlayerInfo:
    """Information about a player."""
    player_id: str
    username: str
    points: int = 0
    alive: bool = True
    connected: bool = True
    ready: bool = False
    passives: List[str] = field(default_factory=list)
    color: str = "white"
    is_local: bool = False  # True if this is a local player on this client


@dataclass
class LocationInfo:
    """Information about a location."""
    name: str
    emoji: str
    min_points: int
    max_points: int
    event: Optional[Dict[str, Any]] = None


@dataclass
class GameState:
    """Client-side game state."""

    # Connection state
    connected: bool = False
    player_id: Optional[str] = None
    game_id: Optional[str] = None

    # UI phase
    phase: ClientPhase = ClientPhase.MAIN_MENU

    # Game data
    round_num: int = 0
    players: Dict[str, PlayerInfo] = field(default_factory=dict)
    locations: List[LocationInfo] = field(default_factory=list)
    active_events: List[Dict[str, Any]] = field(default_factory=list)

    # Local player tracking (for hot-seat)
    local_player_ids: List[str] = field(default_factory=list)
    current_local_player_index: int = 0

    # Current round state
    timer_seconds: int = 0
    previous_ai_location: Optional[str] = None
    last_round_results: Optional[Dict[str, Any]] = None
    last_escape_result: Optional[Dict[str, Any]] = None

    # Shop state
    available_passives: List[Dict[str, Any]] = field(default_factory=list)

    # Escape state
    escape_options: List[Dict[str, Any]] = field(default_factory=list)
    caught_location: Optional[str] = None
    caught_points: int = 0

    # Game over state
    winner: Optional[Dict[str, Any]] = None
    ai_wins: bool = False
    final_standings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def current_local_player(self) -> Optional[PlayerInfo]:
        """Get the current local player for input."""
        if not self.local_player_ids:
            return None
        if self.current_local_player_index >= len(self.local_player_ids):
            return None
        pid = self.local_player_ids[self.current_local_player_index]
        return self.players.get(pid)

    def get_player(self, player_id: str) -> Optional[PlayerInfo]:
        """Get player by ID."""
        return self.players.get(player_id)

    def get_standings(self) -> List[PlayerInfo]:
        """Get players sorted by score."""
        return sorted(
            self.players.values(),
            key=lambda p: (-p.points, not p.alive)
        )

    def reset_for_new_game(self):
        """Reset state for a new game."""
        self.round_num = 0
        self.players.clear()
        self.locations.clear()
        self.active_events.clear()
        self.local_player_ids.clear()
        self.current_local_player_index = 0
        self.last_round_results = None
        self.last_escape_result = None
        self.winner = None
        self.ai_wins = False
        self.final_standings.clear()
