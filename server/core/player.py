"""Server-side player state with serialization support."""

import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# Reuse color palette from original
PLAYER_COLORS = ["green", "cyan", "yellow", "magenta", "red", "blue", "bright_green", "bright_cyan"]


@dataclass
class ServerPlayer:
    """
    Server-side player representation with JSON serialization.

    This is a simplified, serializable version of the game/player.py Player class
    designed for network transmission and database storage.
    """

    user_id: uuid.UUID
    username: str
    player_index: int

    # Game state
    points: int = 0
    alive: bool = True
    connected: bool = True

    # Passives (stored as list of passive type names)
    passives: List[str] = field(default_factory=list)

    # History tracking for AI
    choice_history: List[str] = field(default_factory=list)  # Location names
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

    def has_passive(self, passive_name: str) -> bool:
        """Check if player has a specific passive."""
        return passive_name in self.passives

    def add_passive(self, passive_name: str, cost: int) -> bool:
        """Add a passive if player can afford it."""
        if self.points >= cost and passive_name not in self.passives:
            self.points -= cost
            self.passives.append(passive_name)
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
            'passives_held': self.passives.copy(),
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
            'choice_variety': unique_locations / 5.0,  # 5 total locations
            'high_value_preference': high_value_count / num_choices if num_choices > 0 else 0,
            'location_frequencies': location_counts,
            'total_choices': num_choices,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize player to dictionary for JSON/database storage."""
        return {
            'user_id': str(self.user_id),
            'username': self.username,
            'player_index': self.player_index,
            'points': self.points,
            'alive': self.alive,
            'connected': self.connected,
            'passives': self.passives,
            'choice_history': self.choice_history,
            'round_history': self.round_history,
            'escape_option_history': self.escape_option_history,
            'hide_run_history': self.hide_run_history,
            'hiding_stats': self.hiding_stats,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerPlayer':
        """Deserialize player from dictionary."""
        player = cls(
            user_id=uuid.UUID(data['user_id']) if isinstance(data['user_id'], str) else data['user_id'],
            username=data['username'],
            player_index=data['player_index'],
        )
        player.points = data.get('points', 0)
        player.alive = data.get('alive', True)
        player.connected = data.get('connected', True)
        player.passives = data.get('passives', [])
        player.choice_history = data.get('choice_history', [])
        player.round_history = data.get('round_history', [])
        player.escape_option_history = data.get('escape_option_history', [])
        player.hide_run_history = data.get('hide_run_history', [])
        player.hiding_stats = data.get('hiding_stats', cls.__dataclass_fields__['hiding_stats'].default_factory())
        return player

    def to_public_dict(self) -> Dict[str, Any]:
        """Get public player info (visible to all players)."""
        return {
            'user_id': str(self.user_id),
            'username': self.username,
            'player_index': self.player_index,
            'points': self.points,
            'alive': self.alive,
            'connected': self.connected,
            'passives': self.passives,
            'color': self.color,
        }
