"""ML model training for LOOT RUN AI."""
import json
import os
import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import lightgbm as lgb
from sklearn.preprocessing import LabelEncoder


class ModelTrainer:
    """Trains LightGBM model from game history."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.history_file = os.path.join(data_dir, "game_history.json")
        self.model_file = os.path.join(data_dir, "model.pkl")
        self.label_encoder_file = os.path.join(data_dir, "label_encoder.pkl")

        self.model: Optional[lgb.Booster] = None
        self.label_encoder: Optional[LabelEncoder] = None
        self.feature_names: List[str] = []

    def load_game_history(self) -> List[Dict[str, Any]]:
        """Load all game history."""
        if not os.path.exists(self.history_file):
            return []

        try:
            with open(self.history_file, 'r') as f:
                data = json.load(f)
                return data.get('games', [])
        except Exception as e:
            print(f"Error loading game history: {e}")
            return []

    def extract_training_data(self, games: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract features and labels from game history.

        Returns: (X, y) where X is features array and y is labels (location names)
        """
        X_list = []
        y_list = []

        for game in games:
            for player_data in game['players']:
                self._extract_player_data(player_data, X_list, y_list)

        if not X_list:
            return np.array([]), np.array([])

        X = np.array(X_list)
        y = np.array(y_list)

        return X, y

    def _extract_player_data(self, player_data: Dict[str, Any],
                            X_list: List[List[float]],
                            y_list: List[str]):
        """Extract training samples from a single player's game."""
        round_history = player_data.get('round_history', [])

        if len(round_history) < 2:
            # Need at least 2 rounds to have some history
            return

        for i, round_data in enumerate(round_history):
            # Extract features for this choice
            features = self._extract_features_for_round(
                round_data,
                i,
                round_history[:i],  # History before this round
                player_data
            )

            # Label is the location they chose
            label = round_data['location']

            X_list.append(features)
            y_list.append(label)

    def _extract_features_for_round(self, round_data: Dict[str, Any],
                                   round_idx: int,
                                   history: List[Dict[str, Any]],
                                   player_data: Dict[str, Any]) -> List[float]:
        """Extract feature vector for a single choice."""
        features = []

        # Current state features
        features.append(round_data['points_before'])  # Current score
        features.append(max(0, 100 - round_data['points_before']))  # Points to win
        features.append(round_data['round'])  # Round number

        # Historical behavior features
        if history:
            # Average location value chosen
            avg_value = np.mean([r['location_value'] for r in history])
            features.append(avg_value)

            # Recent average (last 3 rounds)
            recent_history = history[-3:] if len(history) >= 3 else history
            recent_avg = np.mean([r['location_value'] for r in recent_history])
            features.append(recent_avg)

            # Variance in choices
            variance = np.var([r['location_value'] for r in history])
            features.append(variance)

            # High-value preference (15+ points)
            high_value_count = sum(1 for r in history if r['location_value'] >= 15)
            high_value_pref = high_value_count / len(history)
            features.append(high_value_pref)

            # Number of unique locations visited
            unique_locs = len(set(r['location'] for r in history))
            features.append(unique_locs)

            # Total rounds played
            features.append(len(history))

            # Risk trend (comparing recent to overall)
            if recent_avg > avg_value + 3:
                features.append(1)  # Increasing risk
            elif recent_avg < avg_value - 3:
                features.append(-1)  # Decreasing risk
            else:
                features.append(0)  # Stable

            # Close calls in history (got caught)
            close_calls = sum(1 for r in history if r.get('caught', False))
            features.append(close_calls)

        else:
            # First round - no history
            features.extend([0] * 8)  # Pad with zeros (8 history features)

        # Item features (simplified - just count)
        num_items = len(round_data.get('items_held', []))
        features.append(num_items)

        # Store feature names for later
        if not self.feature_names:
            self.feature_names = [
                'current_score',
                'points_to_win',
                'round_number',
                'avg_location_value',
                'recent_avg_value',
                'choice_variance',
                'high_value_preference',
                'unique_locations_visited',
                'total_rounds_played',
                'risk_trend',
                'times_caught',
                'num_items',
            ]

        return features

    def train_model(self, min_samples: int = 50) -> bool:
        """
        Train LightGBM model from game history.

        Args:
            min_samples: Minimum number of training samples needed

        Returns:
            True if model was trained successfully
        """
        # Load game history
        games = self.load_game_history()

        if not games:
            print("No game history found. Play some games first!")
            return False

        # Extract training data
        X, y = self.extract_training_data(games)

        if len(X) < min_samples:
            print(f"Not enough training data: {len(X)} samples (need {min_samples})")
            return False

        print(f"Training with {len(X)} samples from {len(games)} games...")

        # Encode labels (location names -> integers)
        self.label_encoder = LabelEncoder()
        y_encoded = self.label_encoder.fit_transform(y)

        # Create LightGBM dataset
        train_data = lgb.Dataset(
            X,
            label=y_encoded,
            feature_name=self.feature_names,
            free_raw_data=False
        )

        # LightGBM parameters
        params = {
            'objective': 'multiclass',
            'num_class': len(self.label_encoder.classes_),
            'metric': 'multi_logloss',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1,
            'min_data_in_leaf': 5,
        }

        # Train model
        print("Training LightGBM model...")
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=100,
            valid_sets=[train_data],
            valid_names=['train'],
            callbacks=[lgb.log_evaluation(period=0)]  # Silent
        )

        # Save model and encoder
        self.save_model()

        print(f"✓ Model trained successfully!")
        print(f"  - Training samples: {len(X)}")
        print(f"  - Unique locations: {len(self.label_encoder.classes_)}")
        print(f"  - Feature importance (top 5):")

        importance = self.model.feature_importance(importance_type='gain')
        feature_importance = list(zip(self.feature_names, importance))
        feature_importance.sort(key=lambda x: x[1], reverse=True)

        for name, imp in feature_importance[:5]:
            print(f"    {name}: {imp:.1f}")

        return True

    def save_model(self):
        """Save trained model and label encoder to disk."""
        os.makedirs(self.data_dir, exist_ok=True)

        # Save model
        with open(self.model_file, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'feature_names': self.feature_names
            }, f)

        # Save label encoder
        with open(self.label_encoder_file, 'wb') as f:
            pickle.dump(self.label_encoder, f)

        print(f"Model saved to {self.model_file}")

    def load_model(self) -> bool:
        """Load trained model from disk."""
        if not os.path.exists(self.model_file):
            return False

        try:
            # Load model
            with open(self.model_file, 'rb') as f:
                data = pickle.load(f)
                self.model = data['model']
                self.feature_names = data['feature_names']

            # Load label encoder
            with open(self.label_encoder_file, 'rb') as f:
                self.label_encoder = pickle.load(f)

            return True
        except Exception as e:
            print(f"Error loading model: {e}")
            return False

    def predict(self, features: List[float]) -> Dict[str, float]:
        """
        Predict location probabilities.

        Args:
            features: Feature vector

        Returns:
            Dictionary mapping location names to probabilities
        """
        if self.model is None or self.label_encoder is None:
            raise ValueError("Model not loaded or trained")

        # Reshape features
        X = np.array([features])

        # Get predictions (probabilities for each class)
        probs = self.model.predict(X)[0]

        # Map back to location names
        location_probs = {}
        for i, location_name in enumerate(self.label_encoder.classes_):
            location_probs[location_name] = float(probs[i])

        return location_probs

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the trained model."""
        games = self.load_game_history()

        info = {
            'model_exists': os.path.exists(self.model_file),
            'num_games': len(games),
            'model_loaded': self.model is not None
        }

        if self.model is not None and self.label_encoder is not None:
            X, y = self.extract_training_data(games)
            info['training_samples'] = len(X)
            info['locations'] = list(self.label_encoder.classes_)
            info['num_features'] = len(self.feature_names)

        return info


def auto_retrain_if_needed(min_new_games: int = 5) -> bool:
    """
    Automatically retrain model if enough new games have been played.

    Args:
        min_new_games: Retrain every N games

    Returns:
        True if model was retrained
    """
    trainer = ModelTrainer()
    games = trainer.load_game_history()

    if not games:
        return False

    # Check if we should retrain
    num_games = len(games)

    # Try to load existing model to see when it was last trained
    model_exists = os.path.exists(trainer.model_file)

    if not model_exists:
        # No model exists, train if we have enough data
        if num_games >= 2:  # Need at least 2 games
            print(f"\n🤖 No AI model found. Training initial model from {num_games} games...")
            return trainer.train_model(min_samples=20)
    else:
        # Model exists, retrain periodically
        if num_games % min_new_games == 0:
            print(f"\n🤖 Retraining AI model with {num_games} total games...")
            return trainer.train_model(min_samples=20)

    return False
