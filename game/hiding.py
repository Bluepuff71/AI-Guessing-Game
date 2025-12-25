"""Hiding and running mechanics with AI integration."""
import random
from typing import Dict, List, Any, Optional
from game.config_loader import config


class HidingManager:
    """Manages hiding spots and escape mechanics."""

    def __init__(self):
        """Initialize HidingManager with config data."""
        self.mechanics_config = config.get_hiding_mechanics()
        if not self.mechanics_config:
            # Defaults if config not loaded
            self.mechanics_config = {
                'run_point_retention': 0.8,
                'base_run_escape_chance': 0.6,
                'ai_threat_impact_multiplier': 0.5
            }
        self.location_spots = config.get_hiding_spots()

    def get_hiding_spots_for_location(self, location_name: str) -> List[Dict[str, Any]]:
        """
        Get all hiding spots for a specific location.

        Args:
            location_name: Name of the location (e.g., "Corner Store")

        Returns:
            List of hiding spot dictionaries with id, name, description, etc.
        """
        return self.location_spots.get(location_name, [])

    def calculate_hide_success_chance(
        self,
        hide_spot: Dict[str, Any],
        player,
        ai_threat: float
    ) -> float:
        """
        Calculate probability of successful hiding.

        Args:
            hide_spot: Dict containing spot details (base_success_rate, ai_learning_weight, etc.)
            player: Player object with hiding stats
            ai_threat: AI threat level (0.0-1.0)

        Returns:
            Success probability (0.0-1.0), clamped between 0.1 and 0.95

        Calculation:
            base_rate - ai_penalty - pattern_penalty
        where:
            - ai_penalty = ai_threat * 0.2 (max 20% reduction)
            - pattern_penalty = based on how often player uses this spot
        """
        base_rate = hide_spot.get('base_success_rate', 0.5)
        ai_learning_weight = hide_spot.get('ai_learning_weight', 1.0)

        # AI threat reduces success (higher threat = more thorough search)
        ai_penalty = ai_threat * 0.2  # Max 20% reduction

        # Pattern recognition penalty - AI learns favorite spots
        pattern_penalty = self._calculate_pattern_penalty(
            player, hide_spot['id'], ai_learning_weight
        )

        # Calculate final success chance
        success_chance = base_rate - ai_penalty - pattern_penalty

        # Clamp between 10% and 95%
        return max(0.1, min(0.95, success_chance))

    def _calculate_pattern_penalty(
        self,
        player,
        spot_id: str,
        learning_weight: float
    ) -> float:
        """
        Calculate penalty based on how often player uses this spot.
        AI learns favorite spots and searches them first.

        Args:
            player: Player object with hiding_stats
            spot_id: ID of the hiding spot
            learning_weight: How quickly AI learns this spot (higher = faster learning)

        Returns:
            Penalty amount (0.0-0.4), where higher means worse success rate

        Formula:
            (frequency * learning_weight * 0.25)

        Examples:
            - 50% frequency + 1.0 weight = 0.5 * 1.0 * 0.25 = 0.125 (12.5% penalty)
            - 80% frequency + 2.0 weight = 0.8 * 2.0 * 0.25 = 0.4 (40% penalty, capped)
        """
        if not hasattr(player, 'hiding_stats'):
            return 0.0

        favorite_spots = player.hiding_stats.get('favorite_hide_spots', {})

        if spot_id not in favorite_spots:
            return 0.0

        uses = favorite_spots[spot_id]
        total_uses = sum(favorite_spots.values())

        if total_uses == 0:
            return 0.0

        # Calculate frequency of using this spot
        frequency = uses / total_uses

        # AI learning weight amplifies penalty
        penalty = frequency * learning_weight * 0.25

        # Cap at 40% penalty
        return min(penalty, 0.4)

    def calculate_run_escape_chance(self, player, ai_threat: float) -> float:
        """
        Calculate probability of successful running escape.

        Args:
            player: Player object (reserved for future use)
            ai_threat: AI threat level (0.0-1.0)

        Returns:
            Escape probability (0.0-1.0), clamped between 0.15 and 0.85

        Formula:
            base_chance - (ai_threat * impact_multiplier)

        Example:
            - Low threat (0.2): 0.6 - (0.2 * 0.5) = 0.5 (50% escape)
            - High threat (0.8): 0.6 - (0.8 * 0.5) = 0.2 (20% escape)
        """
        base_chance = self.mechanics_config.get('base_run_escape_chance', 0.6)
        impact_mult = self.mechanics_config.get('ai_threat_impact_multiplier', 0.5)

        # Higher AI threat = harder to escape
        ai_penalty = ai_threat * impact_mult

        escape_chance = base_chance - ai_penalty

        # Clamp between 15% and 85%
        return max(0.15, min(0.85, escape_chance))

    def get_run_point_retention(self) -> float:
        """
        Get the percentage of points retained when running successfully.

        Returns:
            Point retention ratio (default 0.8 = 80%)
        """
        return self.mechanics_config.get('run_point_retention', 0.8)
