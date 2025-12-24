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

    def predict_player_location(self, player: Player, num_players_alive: int, event_manager=None) -> Tuple[str, float, str]:
        """
        Predict where a player will go.

        Args:
            player: The player to predict
            num_players_alive: Number of alive players
            event_manager: Optional EventManager to consider events

        Returns: (location_name, confidence, reasoning)
        """
        self.round_num += 1

        # Early game (rounds 1-3): Always use random (learning phase)
        if self.round_num <= 3:
            prediction = self._random_prediction(player)
        # Not enough history yet
        elif len(player.choice_history) < 2:
            prediction = self._simple_pattern_prediction(player)
        else:
            # Try per-player ML prediction if player has a profile
            prediction = None
            if hasattr(player, 'profile_id') and player.profile_id:
                try:
                    player_prediction = self._player_ml_prediction(player, num_players_alive)
                    if player_prediction:
                        prediction = player_prediction
                except Exception:
                    # Fall through to global model or baseline
                    pass

            # Try global ML prediction if available
            if not prediction and self.use_ml and self.ml_trainer:
                try:
                    prediction = self._ml_prediction(player, num_players_alive)
                except Exception as e:
                    # Fall back to baseline if ML fails
                    pass

            # Fallback: use baseline AI
            if not prediction:
                # Mid game (rounds 4-6): Simple pattern matching
                if self.round_num <= 6:
                    prediction = self._simple_pattern_prediction(player)
                else:
                    # Late game (rounds 7+): Advanced prediction
                    prediction = self._advanced_prediction(player, num_players_alive)

        # Adjust prediction based on events
        if event_manager:
            prediction = self._adjust_for_events(prediction, event_manager, player)

        return prediction

    def _adjust_for_events(self, prediction: Tuple[str, float, str], event_manager, player: Player) -> Tuple[str, float, str]:
        """
        Adjust AI prediction confidence and reasoning based on active events.

        Args:
            prediction: Original (location_name, confidence, reasoning) tuple
            event_manager: EventManager with active events
            player: The player being predicted

        Returns: Adjusted (location_name, confidence, reasoning) tuple
        """
        location_name, confidence, reasoning = prediction

        # Find the location object
        predicted_location = self.location_manager.get_location_by_name(location_name)
        if not predicted_location:
            return prediction

        # Check for active event at predicted location
        event = event_manager.get_location_event(predicted_location)
        if not event:
            return prediction

        # Adjust based on event type
        if event.point_modifier:
            # Positive point modifiers make location more attractive
            # Test if it increases points
            test_points = event.point_modifier(10)
            if test_points > 10:
                # Good event - player more likely to go
                confidence = min(confidence * 1.3, 0.95)
                reasoning += f" The {event.name} makes it tempting."
            elif test_points < 10:
                # Bad event - player less likely to go
                confidence = confidence * 0.7
                reasoning += f" The {event.name} might deter them."

        if event.special_effect == "immunity":
            # Immunity makes location very attractive (safe from capture)
            confidence = min(confidence * 1.5, 0.95)
            reasoning += f" The {event.name} offers protection."

        elif event.special_effect == "guaranteed_catch":
            # Guaranteed catch should scare players away
            confidence = confidence * 0.3
            reasoning += f" The {event.name} should scare them off."

        return (location_name, confidence, reasoning)

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
            # No history - fill with zeros (8 history features)
            features.extend([0.0] * 8)

        # Items
        num_items = len(player.get_active_items())
        features.append(float(num_items))

        return features

    def _player_ml_prediction(self, player: Player, num_players_alive: int) -> Optional[Tuple[str, float, str]]:
        """Per-player ML prediction using trained personal model."""
        from ai.player_predictor import PlayerPredictor
        from game.profile_manager import ProfileManager

        predictor = PlayerPredictor(player.profile_id)

        # Try to load model
        if not predictor.load_model():
            return None  # Model doesn't exist yet

        # Extract features (same as global model)
        features = self._extract_ml_features(player, num_players_alive)

        # Get predictions from personal model
        location_probs = predictor.predict(features)

        # Find most likely location
        best_location = max(location_probs.items(), key=lambda x: x[1])
        location_name, confidence = best_location

        # Generate PERSONALIZED reasoning
        pm = ProfileManager()
        profile = pm.load_profile(player.profile_id)
        if profile and profile.behavioral_stats.favorite_location != "Unknown":
            reasoning = f"I know YOUR style, {player.name}. You favor {profile.behavioral_stats.favorite_location}."
        else:
            reasoning = f"Based on your personal history, predicting {location_name}."

        return (location_name, confidence, reasoning)

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

    def decide_search_location(self, players: List[Player], event_manager=None) -> Tuple[Location, Dict[Player, Tuple], str]:
        """
        Decide which location to search based on all player predictions.

        Args:
            players: List of all players
            event_manager: Optional EventManager to consider events in decision

        Returns: (location_to_search, {player: (predicted_loc, confidence, reasoning)}, search_reasoning)
        """
        alive_players = [p for p in players if p.alive]
        num_alive = len(alive_players)

        if num_alive == 0:
            # No players alive, return random
            return self.location_manager.get_location(0), {}, "No players remaining"

        # Get predictions for all players
        predictions = {}
        for player in alive_players:
            pred = self.predict_player_location(player, num_alive, event_manager=event_manager)
            predictions[player] = pred

        # Calculate expected impact for each location
        location_impacts = {}
        impact_details = {}  # Track why each location scored high

        for location in self.location_manager.get_all():
            impact = 0.0
            contributors = []

            for player in alive_players:
                predicted_loc, confidence, reasoning = predictions[player]

                # If this player is predicted to be at this location
                if predicted_loc == location.name:
                    # Calculate win threat (0-1 scale)
                    win_threat = self._calculate_win_threat(player)

                    # Expected impact = confidence * threat
                    contribution = confidence * win_threat
                    impact += contribution
                    contributors.append((player.name, confidence, win_threat, contribution))

            location_impacts[location.name] = impact
            impact_details[location.name] = contributors

        # Adjust impacts based on events
        if event_manager:
            for location in self.location_manager.get_all():
                event = event_manager.get_location_event(location)
                if event:
                    base_impact = location_impacts[location.name]

                    # Boost guaranteed catch locations (easy target)
                    if event.special_effect == "guaranteed_catch":
                        location_impacts[location.name] = base_impact * 2.0

                    # Reduce immunity locations (can't catch players there)
                    elif event.special_effect == "immunity":
                        location_impacts[location.name] = base_impact * 0.2

        # Search location with highest expected impact
        best_location_name = max(location_impacts.items(), key=lambda x: x[1])[0]
        best_location = self.location_manager.get_location_by_name(best_location_name)

        # Generate reasoning
        best_impact = location_impacts[best_location_name]
        contributors = impact_details[best_location_name]

        if contributors:
            # Sort by contribution
            top_contributors = sorted(contributors, key=lambda x: x[3], reverse=True)[:2]

            reasoning_parts = []
            for name, conf, threat, _ in top_contributors:
                reasoning_parts.append(f"{name} ({conf:.0%} likely, {threat:.0%} threat)")

            search_reasoning = f"Targeting {best_location_name}: " + " + ".join(reasoning_parts)
        else:
            search_reasoning = f"Random search: No strong predictions"

        return best_location, predictions, search_reasoning

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

    def reset_round(self):
        """Reset for a new round."""
        # Round number is tracked per prediction, no reset needed
        pass
