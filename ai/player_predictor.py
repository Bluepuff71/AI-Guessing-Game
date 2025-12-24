"""Per-player ML model training for personalized AI predictions."""
import json
import os
import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder


class PlayerPredictor:
    """Trains and manages per-player ML models for personalized predictions."""

    def __init__(self, profile_id: str, data_dir: str = "data"):
        self.profile_id = profile_id
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "game_history.json")
        self.model_dir = os.path.join(data_dir, "profiles", "ai_models")
        self.model_file = os.path.join(self.model_dir, f"{profile_id}_model.pkl")
        self.label_encoder_file = os.path.join(self.model_dir, f"{profile_id}_encoder.pkl")

        self.model: Optional[lgb.Booster] = None
        self.label_encoder: Optional[LabelEncoder] = None
        self.feature_names: List[str] = []
        self.min_games_for_model = 5

        # Ensure model directory exists
        os.makedirs(self.model_dir, exist_ok=True)

    def should_train_model(self) -> bool:
        """Check if player has enough games to train a model."""
        games = self._load_player_games()
        return len(games) >= self.min_games_for_model

    def train_personal_model(self, min_samples: int = 10) -> bool:
        """
        Train a LightGBM model on this player's game history.

        Args:
            min_samples: Minimum number of training samples required

        Returns:
            True if training succeeded, False otherwise
        """
        # Load only this player's games
        games = self._load_player_games()

        if len(games) < self.min_games_for_model:
            print(f"Not enough games for player {self.profile_id}: {len(games)} < {self.min_games_for_model}")
            return False

        # Extract training data
        X, y = self._extract_training_data(games)

        if len(X) < min_samples:
            print(f"Not enough training samples for player {self.profile_id}: {len(X)} < {min_samples}")
            return False

        # Encode labels
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        # Train LightGBM model
        try:
            # Convert to LightGBM Dataset
            train_data = lgb.Dataset(X, label=y_encoded)

            # Set parameters (same as global model but smaller tree depth for less overfitting)
            params = {
                'objective': 'multiclass',
                'num_class': len(self.label_encoder.classes_),
                'metric': 'multi_logloss',
                'boosting_type': 'gbdt',
                'num_leaves': 15,  # Smaller than global model (31)
                'learning_rate': 0.05,
                'feature_fraction': 0.8,
                'verbose': -1
            }

            # Train
            self.model = lgb.train(
                params,
                train_data,
                num_boost_round=50,  # Fewer rounds for smaller dataset
                valid_sets=[train_data],
                callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)]
            )

            # Save model and encoder
            self.save_model()

            # Update profile AI memory
            self._update_profile_ai_memory()

            print(f"Trained personal model for {self.profile_id} with {len(X)} samples from {len(games)} games")
            return True

        except Exception as e:
            print(f"Error training model for player {self.profile_id}: {e}")
            return False

    def load_model(self) -> bool:
        """Load the trained model from disk."""
        if not os.path.exists(self.model_file) or not os.path.exists(self.label_encoder_file):
            return False

        try:
            with open(self.model_file, 'rb') as f:
                self.model = pickle.load(f)

            with open(self.label_encoder_file, 'rb') as f:
                self.label_encoder = pickle.load(f)

            return True
        except Exception as e:
            print(f"Error loading model for player {self.profile_id}: {e}")
            return False

    def save_model(self) -> None:
        """Save the trained model to disk."""
        try:
            with open(self.model_file, 'wb') as f:
                pickle.dump(self.model, f)

            with open(self.label_encoder_file, 'wb') as f:
                pickle.dump(self.label_encoder, f)

        except Exception as e:
            print(f"Error saving model for player {self.profile_id}: {e}")

    def predict(self, features: List[float]) -> Dict[str, float]:
        """
        Predict location probabilities for this player.

        Args:
            features: 12-element feature vector (same as global model)

        Returns:
            Dict mapping location names to probabilities
        """
        if self.model is None or self.label_encoder is None:
            raise ValueError("Model not loaded. Call load_model() first.")

        # Get probabilities
        features_array = np.array([features])
        probabilities = self.model.predict(features_array)[0]

        # Map to location names
        predictions = {}
        for i, location in enumerate(self.label_encoder.classes_):
            predictions[location] = float(probabilities[i])

        return predictions

    def _load_player_games(self) -> List[Dict[str, Any]]:
        """Load all games where this player participated."""
        if not os.path.exists(self.history_file):
            return []

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_games = data.get('games', [])

            # Filter to only games where this player participated
            player_games = []
            for game in all_games:
                # Check if this profile_id is in the game
                for player_data in game.get('players', []):
                    if player_data.get('profile_id') == self.profile_id:
                        player_games.append(game)
                        break

            return player_games

        except Exception as e:
            print(f"Error loading games for player {self.profile_id}: {e}")
            return []

    def _extract_training_data(self, games: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """Extract features and labels from player's games."""
        X_list = []
        y_list = []

        for game in games:
            # Find this player's data in the game
            for player_data in game.get('players', []):
                if player_data.get('profile_id') == self.profile_id:
                    self._extract_player_data(player_data, X_list, y_list)
                    break

        if not X_list:
            return np.array([]), np.array([])

        return np.array(X_list), np.array(y_list)

    def _extract_player_data(self, player_data: Dict[str, Any],
                            X_list: List[List[float]],
                            y_list: List[str]):
        """Extract training samples from player's game (same as global model)."""
        round_history = player_data.get('round_history', [])

        if len(round_history) < 2:
            return

        for i, round_data in enumerate(round_history):
            features = self._extract_features_for_round(
                round_data,
                i,
                round_history[:i],
                player_data
            )

            label = round_data['location']

            X_list.append(features)
            y_list.append(label)

    def _extract_features_for_round(self, round_data: Dict[str, Any],
                                   round_index: int,
                                   history: List[Dict[str, Any]],
                                   player_data: Dict[str, Any]) -> List[float]:
        """
        Extract 12 features for a round (same as global model).

        Features:
        1. Current points
        2. Round number
        3. Num players alive
        4. Avg location value (history)
        5. Recent avg value (last 3)
        6. Times caught
        7. Catch rate
        8. Unique locations visited
        9. Most common location frequency
        10. Avg points per round
        11. Current points / round
        12. Number of items held
        """
        features = []

        # Current state (3 features)
        features.append(round_data.get('points_before', 0))
        features.append(round_data.get('round', round_index + 1))
        # Note: num_players_alive isn't in round_data, use default
        features.append(player_data.get('num_players_alive', 2))

        # History-based features (8 features)
        if history:
            location_values = [r.get('location_value', 0) for r in history]
            features.append(np.mean(location_values))

            recent = location_values[-3:] if len(location_values) >= 3 else location_values
            features.append(np.mean(recent) if recent else 0)

            caught_count = sum(1 for r in history if r.get('caught', False))
            features.append(caught_count)
            features.append(caught_count / len(history) if len(history) > 0 else 0)

            locations_visited = set(r.get('location', '') for r in history)
            features.append(len(locations_visited))

            from collections import Counter
            location_counter = Counter(r.get('location', '') for r in history)
            if location_counter:
                features.append(location_counter.most_common(1)[0][1])
            else:
                features.append(0)

            total_points = sum(r.get('points_earned', 0) for r in history)
            features.append(total_points / len(history) if len(history) > 0 else 0)

            current_round = round_index + 1
            features.append(round_data.get('points_before', 0) / current_round if current_round > 0 else 0)
        else:
            # No history - use zeros
            features.extend([0] * 8)

        # Items feature (1 feature)
        items_held = len(round_data.get('items_held', []))
        features.append(items_held)

        return features

    def _update_profile_ai_memory(self):
        """Update the profile's AI memory stats after training model."""
        try:
            from game.profile_manager import ProfileManager
            from datetime import datetime, timezone

            pm = ProfileManager()
            profile = pm.load_profile(self.profile_id)

            if profile:
                profile.ai_memory.has_personal_model = True
                profile.ai_memory.model_trained_date = datetime.now(timezone.utc).isoformat()
                pm.save_profile(profile)

        except Exception as e:
            print(f"Error updating profile AI memory: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the trained model."""
        games = self._load_player_games()
        X, y = self._extract_training_data(games)

        return {
            'profile_id': self.profile_id,
            'num_games': len(games),
            'training_samples': len(X),
            'model_exists': os.path.exists(self.model_file),
            'model_loaded': self.model is not None,
            'locations': list(self.label_encoder.classes_) if self.label_encoder else []
        }
