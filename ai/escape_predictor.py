"""AI prediction for escape options when players are caught."""
import random
from typing import Dict, List, Tuple, Any, Optional


class EscapePredictor:
    """AI that predicts which escape option a player will choose when caught."""

    def __init__(self):
        """Initialize EscapePredictor."""
        # Track caught count per player per game (for prediction phase selection)
        self.caught_count: Dict[int, int] = {}
        # Track within-game escape choices per player
        self.game_escape_history: Dict[int, List[str]] = {}

    def reset_game(self):
        """Reset state for a new game."""
        self.caught_count = {}
        self.game_escape_history = {}

    def predict_escape_option(
        self,
        player,
        escape_options: List[Dict[str, Any]],
        profile=None
    ) -> Tuple[str, float, str]:
        """
        Predict which escape option the player will choose.

        Args:
            player: Player object being predicted
            escape_options: List of escape option dicts with id, name, type, etc.
            profile: Optional PlayerProfile for cross-game learning

        Returns:
            Tuple of (option_id, confidence, reasoning)
        """
        player_id = id(player)
        caught_count = self.caught_count.get(player_id, 0)

        # Get cross-game history from profile if available
        cross_game_history = self._get_cross_game_history(profile)

        # Get within-game history
        game_history = self.game_escape_history.get(player_id, [])

        # Combine histories (cross-game first, then current game)
        combined_history = cross_game_history + game_history

        # Early catches (1-2): Random prediction (learning phase)
        if caught_count <= 1:
            return self._random_prediction(escape_options)

        # Mid catches (2-4): Recency-weighted pattern matching
        if caught_count <= 4:
            return self._recency_weighted_prediction(
                escape_options, combined_history, player
            )

        # Late catches (5+): Advanced behavioral prediction
        return self._behavioral_prediction(
            escape_options, combined_history, player, profile
        )

    def _get_cross_game_history(self, profile) -> List[str]:
        """Extract escape option history from player profile."""
        if not profile:
            return []

        # Check for hiding_stats with escape_option_history
        if hasattr(profile, 'hiding_stats'):
            stats = profile.hiding_stats
            if hasattr(stats, 'escape_option_history'):
                return list(stats.escape_option_history)
            # Fallback: use old favorite_hide_spots if available
            if hasattr(stats, 'favorite_hide_spots') and stats.favorite_hide_spots:
                # Convert frequency dict to list (repeat based on count)
                history = []
                for spot_id, count in stats.favorite_hide_spots.items():
                    history.extend([spot_id] * min(count, 5))  # Cap at 5 per spot
                return history

        return []

    def _random_prediction(
        self,
        escape_options: List[Dict[str, Any]]
    ) -> Tuple[str, float, str]:
        """Random prediction for early catches (AI is still learning)."""
        option = random.choice(escape_options)
        confidence = 1.0 / len(escape_options)
        return (
            option['id'],
            confidence,
            "AI is learning your escape patterns..."
        )

    def _recency_weighted_prediction(
        self,
        escape_options: List[Dict[str, Any]],
        combined_history: List[str],
        player
    ) -> Tuple[str, float, str]:
        """
        Pattern matching with recency weighting.

        Recent choices matter more than older ones.
        Uses same exponential decay as location predictor.
        """
        if not combined_history:
            return self._random_prediction(escape_options)

        # Get valid option IDs for this location
        valid_option_ids = {opt['id'] for opt in escape_options}

        # Use recency-weighted counting
        # Weight = 2^(-decay_rate * age), where age = 0 (most recent)
        option_scores: Dict[str, float] = {}
        decay_rate = 0.3

        # Process history from oldest to newest
        for age, option_id in enumerate(reversed(combined_history)):
            # Skip options not available at this location
            if option_id not in valid_option_ids:
                continue

            weight = 2 ** (-decay_rate * age)

            if option_id not in option_scores:
                option_scores[option_id] = 0.0
            option_scores[option_id] += weight

        # If no matching history, fall back to random
        if not option_scores:
            return self._random_prediction(escape_options)

        # Find option with highest weighted score
        predicted_id, weighted_score = max(option_scores.items(), key=lambda x: x[1])

        # Calculate confidence
        total_weight = sum(option_scores.values())
        confidence = weighted_score / total_weight if total_weight > 0 else 0.2

        # Add Laplace smoothing
        num_options = len(escape_options)
        confidence = (confidence + 0.1) / (1.0 + 0.1 * num_options)

        # Count occurrences for reasoning
        total_uses = combined_history.count(predicted_id)
        recent_uses = sum(1 for opt in combined_history[-3:] if opt == predicted_id)

        if recent_uses >= 2:
            reasoning = f"You used this escape {recent_uses}/3 times recently"
        else:
            reasoning = f"You've chosen this escape {total_uses} times before"

        return (predicted_id, confidence, reasoning)

    def _behavioral_prediction(
        self,
        escape_options: List[Dict[str, Any]],
        combined_history: List[str],
        player,
        profile
    ) -> Tuple[str, float, str]:
        """
        Advanced behavioral prediction considering multiple factors.
        """
        option_scores: Dict[str, float] = {}

        # Get valid option IDs
        valid_option_ids = {opt['id'] for opt in escape_options}

        # Calculate hide vs run preference
        hide_count = 0
        run_count = 0
        for opt_id in combined_history:
            # Try to determine type from ID pattern
            if 'run' in opt_id or any(r in opt_id for r in ['backdoor', 'window', 'exit', 'alley', 'garage', 'lobby', 'parking', 'mall', 'floor', 'kitchen']):
                run_count += 1
            else:
                hide_count += 1

        total_choices = hide_count + run_count
        hide_preference = hide_count / total_choices if total_choices > 0 else 0.5

        for opt in escape_options:
            score = 1.0  # Base score

            # Factor 1: Historical frequency (recency-weighted)
            for age, opt_id in enumerate(reversed(combined_history)):
                if opt_id == opt['id']:
                    weight = 2 ** (-0.3 * age)
                    score += weight * 5

            # Factor 2: Hide vs Run preference
            opt_type = opt.get('type', 'hide')
            if opt_type == 'hide' and hide_preference > 0.6:
                score += 3  # Player tends to hide
            elif opt_type == 'run' and hide_preference < 0.4:
                score += 3  # Player tends to run

            # Factor 3: Point pressure (close to winning = more likely to run)
            if hasattr(player, 'points') and player.points >= 80:
                if opt_type == 'run':
                    score += 2  # Desperate players want to keep points

            # Factor 4: Penalize options never used before (players have habits)
            if opt['id'] not in combined_history:
                score *= 0.7  # Less likely to try new escapes under pressure

            option_scores[opt['id']] = score

        # Get highest scored option
        predicted_id, pred_score = max(option_scores.items(), key=lambda x: x[1])

        # Normalize to confidence
        total_score = sum(option_scores.values())
        confidence = pred_score / total_score if total_score > 0 else 0.2

        # Generate reasoning
        reasoning = self._generate_reasoning(
            predicted_id, escape_options, combined_history, hide_preference, player
        )

        return (predicted_id, confidence, reasoning)

    def _generate_reasoning(
        self,
        predicted_id: str,
        escape_options: List[Dict[str, Any]],
        history: List[str],
        hide_preference: float,
        player
    ) -> str:
        """Generate human-readable reasoning for the prediction."""
        reasons = []

        # Find the predicted option
        predicted_opt = next((o for o in escape_options if o['id'] == predicted_id), None)
        if not predicted_opt:
            return "Pattern analysis"

        # Check usage frequency
        usage_count = history.count(predicted_id)
        if usage_count >= 3:
            reasons.append(f"you favor {predicted_opt['name']}")

        # Check hide vs run tendency
        if hide_preference > 0.7:
            reasons.append("you prefer hiding")
        elif hide_preference < 0.3:
            reasons.append("you prefer running")

        # Check point pressure
        if hasattr(player, 'points') and player.points >= 80:
            if predicted_opt.get('type') == 'run':
                reasons.append("you're close to winning")

        if not reasons:
            return "Behavioral pattern analysis"

        return "I predict this because " + ", ".join(reasons[:2])

    def record_escape_choice(self, player, option_id: str):
        """
        Record a player's escape choice for within-game learning.

        Args:
            player: Player who made the choice
            option_id: The escape option ID they chose
        """
        player_id = id(player)

        # Update caught count
        self.caught_count[player_id] = self.caught_count.get(player_id, 0) + 1

        # Add to game history
        if player_id not in self.game_escape_history:
            self.game_escape_history[player_id] = []
        self.game_escape_history[player_id].append(option_id)

    def get_caught_count(self, player) -> int:
        """Get how many times a player has been caught this game."""
        return self.caught_count.get(id(player), 0)
