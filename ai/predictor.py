"""AI prediction and search logic."""
import random
from typing import List, Dict, Tuple, Any, Optional
from game.player import Player
from game.locations import Location, LocationManager
from game.config_loader import config
from ai.features import extract_features, calculate_predictability


class AIPredictor:
    """AI that predicts player locations and decides where to search."""

    def __init__(self, location_manager: LocationManager):
        self.location_manager = location_manager
        self.round_num = 0

        # Try to load ML model
        self.ml_trainer = None
        self.use_ml = False
        self._try_load_ml_model()

    def _try_load_ml_model(self):
        """Try to load ML model if available."""
        try:
            from ai.trainer import ModelTrainer
            self.ml_trainer = ModelTrainer()
            if self.ml_trainer.load_model():
                self.use_ml = True
                info = self.ml_trainer.get_model_info()
                # Model loaded successfully (silent)
            else:
                self.use_ml = False
        except Exception as e:
            # ML not available, use baseline
            self.use_ml = False
            self.ml_trainer = None

    def predict_player_location(self, player: Player, num_players_alive: int) -> Tuple[str, float, str]:
        """
        Predict where a player will go.

        Returns: (location_name, confidence, reasoning)
        """
        self.round_num += 1

        # Early game (rounds 1-3): Always use random (learning phase)
        if self.round_num <= 3:
            return self._random_prediction(player)

        # Not enough history yet
        if len(player.choice_history) < 2:
            return self._simple_pattern_prediction(player)

        # Try ML prediction if available
        if self.use_ml and self.ml_trainer:
            try:
                return self._ml_prediction(player, num_players_alive)
            except Exception as e:
                # Fall back to baseline if ML fails
                pass

        # Fallback: use baseline AI
        # Mid game (rounds 4-6): Simple pattern matching
        if self.round_num <= 6:
            return self._simple_pattern_prediction(player)

        # Late game (rounds 7+): Advanced prediction
        return self._advanced_prediction(player, num_players_alive)

    def _random_prediction(self, player: Player) -> Tuple[str, float, str]:
        """Random prediction for early game (AI is still learning)."""
        location = random.choice(self.location_manager.get_all())
        return (
            location.name,
            0.125,  # 1/8 chance (random)
            "AI is still learning your patterns..."
        )

    def _ml_prediction(self, player: Player, num_players_alive: int) -> Tuple[str, float, str]:
        """ML-based prediction using trained LightGBM model."""
        # Extract features for this player
        features = self._extract_ml_features(player, num_players_alive)

        # Get predictions from model
        location_probs = self.ml_trainer.predict(features)

        # Find most likely location
        best_location = max(location_probs.items(), key=lambda x: x[1])
        location_name, confidence = best_location

        # Generate reasoning based on player behavior
        reasoning = self._generate_ml_reasoning(player, location_name, confidence)

        return (location_name, confidence, reasoning)

    def _extract_ml_features(self, player: Player, num_players_alive: int) -> List[float]:
        """Extract features for ML model (matches trainer feature extraction)."""
        features = []

        # Current state
        win_threshold = config.get('game', 'win_threshold', default=100)
        features.append(player.points)  # current_score
        features.append(max(0, win_threshold - player.points))  # points_to_win
        features.append(self.round_num)  # round_number

        # Historical behavior
        if player.round_history:
            history = player.round_history

            # Average location value
            avg_value = sum(r['location_value'] for r in history) / len(history)
            features.append(avg_value)

            # Recent average (last 3)
            recent = history[-3:] if len(history) >= 3 else history
            recent_avg = sum(r['location_value'] for r in recent) / len(recent)
            features.append(recent_avg)

            # Variance
            values = [r['location_value'] for r in history]
            import numpy as np
            variance = float(np.var(values))
            features.append(variance)

            # High-value preference
            high_value_count = sum(1 for r in history if r['location_value'] >= 15)
            high_value_pref = high_value_count / len(history)
            features.append(high_value_pref)

            # Unique locations
            unique_locs = len(set(r['location'] for r in history))
            features.append(float(unique_locs))

            # Total rounds
            features.append(float(len(history)))

            # Risk trend
            if recent_avg > avg_value + 3:
                features.append(1.0)
            elif recent_avg < avg_value - 3:
                features.append(-1.0)
            else:
                features.append(0.0)

            # Times caught
            caught_count = sum(1 for r in history if r.get('caught', False))
            features.append(float(caught_count))

        else:
            # No history - fill with zeros
            features.extend([0.0] * 9)

        # Items
        num_items = len(player.get_active_items())
        features.append(float(num_items))

        return features

    def _generate_ml_reasoning(self, player: Player, predicted_location: str, confidence: float) -> str:
        """Generate reasoning for ML prediction."""
        reasons = []

        # High confidence
        if confidence > 0.5:
            reasons.append("ML model high confidence")

        # Add behavioral insights
        win_threshold = config.get('game', 'win_threshold', default=100)
        win_proximity_threshold = int(win_threshold * 0.8)
        if player.points >= win_proximity_threshold:
            reasons.append(f"{player.points} points - win threat")

        behavior = player.get_behavior_summary()
        if behavior['avg_location_value'] > 18:
            reasons.append("favors high-value locations")
        elif behavior['avg_location_value'] < 10:
            reasons.append("prefers low-value targets")

        if behavior['choice_variety'] < 0.5:
            reasons.append("limited variety detected")

        if not reasons:
            return "ML pattern recognition"

        return ", ".join(reasons[:3]).capitalize()

    def _simple_pattern_prediction(self, player: Player) -> Tuple[str, float, str]:
        """Simple pattern matching based on frequency."""
        if not player.choice_history:
            return self._random_prediction(player)

        # Find most common location
        from collections import Counter
        location_counts = Counter(player.choice_history)
        most_common = location_counts.most_common(1)[0]
        most_common_name, count = most_common

        # Calculate confidence with Laplace smoothing to prevent overconfidence on small samples
        # Prevents 1/1 = 100%, instead makes it (1+1)/(1+num_locations) = more reasonable
        num_locations = len(self.location_manager.get_all())
        total_choices = len(player.choice_history)
        confidence = (count + 1) / (total_choices + num_locations)

        reasoning = f"You've picked {most_common_name} {count}/{len(player.choice_history)} times"

        return (most_common_name, confidence, reasoning)

    def _advanced_prediction(self, player: Player, num_players_alive: int) -> Tuple[str, float, str]:
        """Advanced prediction using behavioral analysis."""
        features = extract_features(player, self.round_num, num_players_alive, self.location_manager)

        # Build prediction based on multiple factors
        location_scores = {}

        for location in self.location_manager.get_all():
            score = self._score_location_for_player(location, player, features)
            location_scores[location.name] = score

        # Get highest scored location
        predicted_location = max(location_scores.items(), key=lambda x: x[1])
        location_name, score = predicted_location

        # Normalize score to confidence (0-1)
        total_score = sum(location_scores.values())
        confidence = score / total_score if total_score > 0 else 0.125

        # Generate reasoning
        reasoning = self._generate_reasoning(player, features, location_name)

        return (location_name, confidence, reasoning)

    def _score_location_for_player(self, location: Location, player: Player,
                                   features: Dict[str, Any]) -> float:
        """Score how likely a player is to choose this location."""
        score = 1.0  # Base score

        # Factor 1: Historical frequency
        if location.name in player.choice_history:
            frequency = player.choice_history.count(location.name) / len(player.choice_history)
            score += frequency * 10

        # Factor 2: Value preference
        # Use average of range since locations no longer have fixed values
        location_value = (location.min_points + location.max_points) / 2
        avg_value = features['avg_location_value']

        if avg_value > 0:
            # If player likes high-value and this is high-value, boost score
            if features['high_value_preference'] > 0.6 and location_value >= 15:
                score += 5
            # If player likes low-value and this is low-value, boost score
            elif features['high_value_preference'] < 0.4 and location_value < 15:
                score += 5

        # Factor 3: Win threat (players near win threshold likely to go high-value)
        win_threshold = config.get('game', 'win_threshold', default=100)
        close_to_win_margin = int(win_threshold * 0.2)
        if features['points_to_win'] <= close_to_win_margin and location_value >= 20:
            score += 8  # High priority on high-value when close to winning

        # Factor 4: Recent trend
        if features['risk_trend'] > 0 and location_value >= 15:
            score += 3  # Escalating risk
        elif features['risk_trend'] < 0 and location_value < 15:
            score += 3  # Decreasing risk

        # Factor 5: Lucky Charm usage (doubled points means higher value targets)
        if features['has_lucky_charm'] and location_value >= 15:
            score += 7

        # Factor 6: Avoid recently searched locations (slight penalty)
        # TODO: Track AI's recent searches and penalize

        return max(0, score)

    def _generate_reasoning(self, player: Player, features: Dict[str, Any],
                           predicted_location: str) -> str:
        """Generate human-readable reasoning for the prediction."""
        reasons = []

        # Win threat
        if features['points_to_win'] <= 20:
            reasons.append(f"Critical win threat - {player.points} points")

        # Patterns
        if features['high_value_preference'] > 0.6:
            reasons.append("consistently chooses high-value locations")
        elif features['high_value_preference'] < 0.4:
            reasons.append("prefers low-value locations")

        # Recent behavior
        if features['risk_trend'] > 0:
            reasons.append("escalating risk pattern")
        elif features['risk_trend'] < 0:
            reasons.append("becoming more conservative")

        # Items
        if features['has_lucky_charm']:
            reasons.append("has Lucky Charm (likely targeting high-value)")
        if features['has_scanner']:
            reasons.append("used Scanner (may avoid predicted areas)")

        # Predictability
        predictability = calculate_predictability(player)
        if predictability > 0.7:
            reasons.append("highly predictable behavior")
        elif predictability < 0.3:
            reasons.append("unpredictable pattern")

        # Combine into reasoning string
        if not reasons:
            return "Based on behavioral analysis"

        # Prioritize most important reasons (max 2-3)
        return ", ".join(reasons[:3]).capitalize()

    def decide_search_location(self, players: List[Player]) -> Tuple[Location, Dict[Player, Tuple]]:
        """
        Decide which location to search based on all player predictions.

        Returns: (location_to_search, {player: (predicted_loc, confidence, reasoning)})
        """
        alive_players = [p for p in players if p.alive]
        num_alive = len(alive_players)

        if num_alive == 0:
            # No players alive, return random
            return self.location_manager.get_location(0), {}

        # Get predictions for all players
        predictions = {}
        for player in alive_players:
            pred = self.predict_player_location(player, num_alive)
            predictions[player] = pred

        # Calculate expected impact for each location
        location_impacts = {}

        for location in self.location_manager.get_all():
            impact = 0.0

            for player in alive_players:
                predicted_loc, confidence, reasoning = predictions[player]

                # If this player is predicted to be at this location
                if predicted_loc == location.name:
                    # Calculate win threat (0-1 scale)
                    win_threat = self._calculate_win_threat(player)

                    # Expected impact = confidence * threat
                    impact += confidence * win_threat

            location_impacts[location.name] = impact

        # Search location with highest expected impact
        best_location_name = max(location_impacts.items(), key=lambda x: x[1])[0]
        best_location = self.location_manager.get_location_by_name(best_location_name)

        return best_location, predictions

    def _calculate_win_threat(self, player: Player) -> float:
        """
        Calculate how much of a threat this player is to winning.

        Returns: 0-1 scale, where 1 is highest threat
        """
        win_threshold = config.get('game', 'win_threshold', default=100)
        win_proximity_threshold = int(win_threshold * 0.8)

        # Primary factor: proximity to win threshold
        points_threat = player.points / win_threshold

        # Exponential scaling for players close to winning
        if player.points >= win_proximity_threshold:
            points_threat = 0.8 + (player.points - win_proximity_threshold) / win_threshold  # 0.8-1.0 range

        # Secondary factor: has Lucky Charm (could double points)
        has_lucky_charm = any(item.name == "Lucky Charm" and not item.consumed
                             for item in player.items)

        if has_lucky_charm:
            # If they have lucky charm and could potentially win this round
            # (assuming they go for Bank Vault = 35 pts * 2 = 70 pts)
            lucky_charm_win_threshold = int(win_threshold * 0.3)
            if player.points >= lucky_charm_win_threshold:
                points_threat = min(1.0, points_threat + 0.3)

        # Tertiary factor: predictability (easier to catch)
        predictability = calculate_predictability(player)
        catch_likelihood = predictability * 0.2

        total_threat = min(1.0, points_threat + catch_likelihood)

        return total_threat

    def get_scanner_predictions(self, players: List[Player]) -> List[Tuple[str, float, str]]:
        """
        Get top 2 location predictions for Scanner item.

        Returns: [(location_name, confidence, reason), ...]
        """
        alive_players = [p for p in players if p.alive]
        location_impacts = {}

        for location in self.location_manager.get_all():
            impact = 0.0

            for player in alive_players:
                pred_loc, confidence, reasoning = self.predict_player_location(player, len(alive_players))

                if pred_loc == location.name:
                    win_threat = self._calculate_win_threat(player)
                    impact += confidence * win_threat

            location_impacts[location.name] = impact

        # Sort by impact and get top 2
        sorted_locations = sorted(location_impacts.items(), key=lambda x: x[1], reverse=True)

        results = []
        for loc_name, impact in sorted_locations[:2]:
            # Generate reason based on impact
            if impact > 0.7:
                reason = "High win threat detected"
            elif impact > 0.4:
                reason = "Multiple aggressive players predicted"
            else:
                reason = "Moderate threat level"

            # Impact as confidence (normalize)
            max_impact = sorted_locations[0][1] if sorted_locations else 1.0
            confidence = impact / max_impact if max_impact > 0 else 0.5

            results.append((loc_name, confidence, reason))

        return results

    def reset_round(self):
        """Reset for a new round."""
        # Round number is tracked per prediction, no reset needed
        pass
