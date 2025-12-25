"""Player class and management."""
from typing import List, Optional, Dict, Any
from game.locations import Location
from game.passives import Passive, PassiveType, PassiveManager


# Color palette for players
PLAYER_COLORS = ["green", "cyan", "yellow", "magenta", "red", "blue", "bright_green", "bright_cyan"]


class Player:
    """Represents a player in the game."""

    def __init__(self, player_id: int, name: str, profile_id: Optional[str] = None):
        self.id = player_id
        self.name = name
        self.profile_id = profile_id  # UUID of player's profile (None for guests)
        self.color = PLAYER_COLORS[player_id % len(PLAYER_COLORS)]  # Assign unique color
        self.points = 0
        self.alive = True
        self.passive_manager = PassiveManager()

        # History tracking for AI
        self.choice_history: List[str] = []  # Location names chosen
        self.round_history: List[Dict[str, Any]] = []  # Full round data

        # Escape option tracking (for prediction-based mechanics)
        self.escape_option_history: List[str] = []  # Escape option IDs chosen this game
        self.hide_run_history: List[Dict[str, Any]] = []  # All escape attempts
        self.hiding_stats: Dict[str, Any] = {
            'total_escape_attempts': 0,
            'successful_escapes': 0,
            'total_hide_attempts': 0,
            'successful_hides': 0,
            'total_run_attempts': 0,
            'successful_runs': 0,
            'favorite_escape_options': {},  # {option_id: count}
            'hide_vs_run_ratio': 0.0  # Preference for hiding vs running
        }

    def add_points(self, points: int):
        """Add points to player."""
        self.points += points

    def buy_passive(self, passive: Passive) -> bool:
        """Attempt to buy a passive ability. Returns True if successful."""
        if self.points >= passive.cost:
            if self.passive_manager.add_passive(passive):
                self.points -= passive.cost
                return True
        return False

    def has_passive(self, passive_type: PassiveType) -> bool:
        """Check if player has a specific passive."""
        return self.passive_manager.has_passive(passive_type)

    def get_passives(self) -> list:
        """Get all owned passives."""
        return self.passive_manager.get_all()

    def record_choice(self, location: Location, round_num: int,
                     caught: bool, points_earned: int, location_value: int = None):
        """Record a choice for AI learning."""
        self.choice_history.append(location.name)

        # If location_value not provided, use points_earned (base value before Lucky Charm)
        if location_value is None:
            location_value = points_earned

        self.round_history.append({
            'round': round_num,
            'location': location.name,
            'location_value': location_value,
            'points_before': self.points - points_earned,
            'points_earned': points_earned,
            'caught': caught,
            'passives_held': [p.name for p in self.get_passives()],
        })

    def record_escape_attempt(self, escape_result: Dict[str, Any], round_num: int):
        """
        Record an escape attempt for AI learning (prediction-based system).

        Args:
            escape_result: Dict containing escaped, player_choice_id, choice_type, etc.
            round_num: Current round number
        """
        choice_type = escape_result.get('choice_type', 'hide')
        escaped = escape_result['escaped']
        option_id = escape_result.get('player_choice_id')

        # Record in escape option history for within-game learning
        if option_id:
            self.escape_option_history.append(option_id)

        # Record in full history
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
        else:  # run
            self.hiding_stats['total_run_attempts'] += 1
            if escaped:
                self.hiding_stats['successful_runs'] += 1

        # Track favorite escape options
        if option_id:
            if option_id not in self.hiding_stats['favorite_escape_options']:
                self.hiding_stats['favorite_escape_options'][option_id] = 0
            self.hiding_stats['favorite_escape_options'][option_id] += 1

        # Update hide vs run ratio
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

        # Calculate statistics
        location_counts = {}
        total_value = 0

        for round_data in self.round_history:
            loc = round_data['location']
            location_counts[loc] = location_counts.get(loc, 0) + 1
            total_value += round_data['location_value']

        num_choices = len(self.choice_history)
        unique_locations = len(location_counts)
        avg_value = total_value / num_choices if num_choices > 0 else 0

        # High-value choices (15+ points)
        high_value_count = sum(1 for r in self.round_history
                               if r['location_value'] >= 15)

        return {
            'avg_location_value': avg_value,
            'choice_variety': unique_locations / 8.0,  # 8 total locations
            'high_value_preference': high_value_count / num_choices if num_choices > 0 else 0,
            'location_frequencies': location_counts,
            'total_choices': num_choices,
        }

    def __str__(self) -> str:
        passives = self.get_passives()
        passives_str = f" [{', '.join(p.name for p in passives)}]" if passives else ""
        return f"{self.name} - {self.points} pts{passives_str}"
