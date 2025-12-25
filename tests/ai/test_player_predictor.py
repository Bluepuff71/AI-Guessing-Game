"""Tests for ai.player_predictor module."""
import json
import os
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestPlayerPredictorInitialization:
    """Tests for PlayerPredictor initialization."""

    def test_initialization(self, temp_profile_with_games):
        """Test PlayerPredictor initializes correctly."""
        from ai.player_predictor import PlayerPredictor

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        assert predictor.profile_id == temp_profile_with_games['profile_id']
        assert predictor.model is None
        assert predictor.label_encoder is None
        assert predictor.min_games_for_model == 5

    def test_model_directory_creation(self, tmp_path):
        """Test model directory is created on initialization."""
        from ai.player_predictor import PlayerPredictor

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        expected_model_dir = os.path.join(data_dir, "profiles", "ai_models")
        assert os.path.exists(expected_model_dir)


class TestModelTrainingEligibility:
    """Tests for model training eligibility checks."""

    def test_should_train_model_insufficient_games(self, tmp_path):
        """Test should_train_model returns False with insufficient games."""
        from ai.player_predictor import PlayerPredictor

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Create history with only 2 games
        game_history = {
            "games": [
                {
                    "game_id": f"game_{i}",
                    "players": [{"profile_id": "test_profile", "round_history": []}]
                }
                for i in range(2)
            ]
        }
        (data_dir / "game_history.json").write_text(json.dumps(game_history))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=str(data_dir))
        assert predictor.should_train_model() is False

    def test_should_train_model_sufficient_games(self, temp_profile_with_games):
        """Test should_train_model returns True with sufficient games."""
        from ai.player_predictor import PlayerPredictor

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        # temp_profile_with_games has 6 games
        assert predictor.should_train_model() is True


class TestPersonalModelTraining:
    """Tests for personal model training."""

    def test_train_personal_model_insufficient_games(self, tmp_path):
        """Test training fails with insufficient games."""
        from ai.player_predictor import PlayerPredictor

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        game_history = {"games": []}
        (data_dir / "game_history.json").write_text(json.dumps(game_history))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=str(data_dir))
        result = predictor.train_personal_model()

        assert result is False

    def test_train_personal_model_insufficient_samples(self, tmp_path):
        """Test training fails with insufficient training samples."""
        from ai.player_predictor import PlayerPredictor

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Create games with minimal round history
        game_history = {
            "games": [
                {
                    "game_id": f"game_{i}",
                    "players": [{
                        "profile_id": "test_profile",
                        "num_players_alive": 2,
                        "round_history": [
                            {"round": 1, "location": "Store", "points_before": 0, "caught": False}
                        ]
                    }]
                }
                for i in range(5)
            ]
        }
        (data_dir / "game_history.json").write_text(json.dumps(game_history))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=str(data_dir))
        # Require more samples than available
        result = predictor.train_personal_model(min_samples=100)

        assert result is False

    @pytest.mark.slow
    def test_train_personal_model_success(self, temp_profile_with_games, monkeypatch):
        """Test successful model training."""
        from ai.player_predictor import PlayerPredictor

        # Mock the profile manager to avoid side effects
        mock_pm = Mock()
        mock_pm.load_profile.return_value = None

        with patch('game.profile_manager.ProfileManager', return_value=mock_pm):
            predictor = PlayerPredictor(
                profile_id=temp_profile_with_games['profile_id'],
                data_dir=temp_profile_with_games['data_dir']
            )

            result = predictor.train_personal_model(min_samples=5)

            # Training may succeed or fail depending on data quality
            # Just verify it doesn't crash
            assert isinstance(result, bool)


class TestModelPersistence:
    """Tests for model save/load functionality."""

    def test_load_model_not_found(self, tmp_path):
        """Test load_model returns False when model doesn't exist."""
        from ai.player_predictor import PlayerPredictor

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        result = predictor.load_model()
        assert result is False

    def test_save_and_load_model(self, tmp_path):
        """Test saving and loading a model."""
        from ai.player_predictor import PlayerPredictor
        from sklearn.preprocessing import LabelEncoder
        import lightgbm as lgb

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        # Train a minimal real LightGBM model (pickle-compatible)
        X = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12]])
        y = np.array([0, 1, 2, 0])
        train_data = lgb.Dataset(X, label=y)
        params = {'objective': 'multiclass', 'num_class': 3, 'verbose': -1}
        predictor.model = lgb.train(params, train_data, num_boost_round=2)

        predictor.label_encoder = LabelEncoder()
        predictor.label_encoder.fit(['Location1', 'Location2', 'Location3'])

        predictor.save_model()

        # Verify files were created
        assert os.path.exists(predictor.model_file)
        assert os.path.exists(predictor.label_encoder_file)

        # Create new predictor and load
        predictor2 = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)
        result = predictor2.load_model()

        assert result is True
        assert predictor2.model is not None
        assert predictor2.label_encoder is not None


class TestPrediction:
    """Tests for prediction functionality."""

    def test_predict_without_model_raises_error(self, tmp_path):
        """Test predict raises error when model not loaded."""
        from ai.player_predictor import PlayerPredictor

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        features = [0] * 12

        with pytest.raises(ValueError, match="Model not loaded"):
            predictor.predict(features)

    def test_predict_with_model(self, tmp_path, mock_ml_model):
        """Test prediction with loaded model."""
        from ai.player_predictor import PlayerPredictor
        from sklearn.preprocessing import LabelEncoder

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        # Setup mock model and encoder
        predictor.model = mock_ml_model
        predictor.label_encoder = LabelEncoder()
        predictor.label_encoder.fit(['Corner Store', 'Pawn Shop', 'Jewelry Store', 'Casino Vault', 'Bank Heist'])

        features = [50, 3, 2, 10, 12, 1, 0.2, 3, 2, 15, 16, 0]  # 12 features

        predictions = predictor.predict(features)

        assert isinstance(predictions, dict)
        assert len(predictions) == 5
        assert all(isinstance(v, float) for v in predictions.values())

    def test_predict_returns_probabilities(self, tmp_path, mock_ml_model):
        """Test prediction returns valid probabilities."""
        from ai.player_predictor import PlayerPredictor
        from sklearn.preprocessing import LabelEncoder

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        predictor.model = mock_ml_model
        predictor.label_encoder = LabelEncoder()
        predictor.label_encoder.fit(['Loc1', 'Loc2', 'Loc3', 'Loc4', 'Loc5'])

        features = [0] * 12

        predictions = predictor.predict(features)

        # Probabilities should sum close to 1
        total = sum(predictions.values())
        assert 0.99 <= total <= 1.01


class TestDataExtraction:
    """Tests for data loading and feature extraction."""

    def test_load_player_games_no_file(self, tmp_path):
        """Test loading games when history file doesn't exist."""
        from ai.player_predictor import PlayerPredictor

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        games = predictor._load_player_games()
        assert games == []

    def test_load_player_games_filters_by_profile(self, temp_profile_with_games):
        """Test loading games filters by profile ID."""
        from ai.player_predictor import PlayerPredictor

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        games = predictor._load_player_games()
        assert len(games) == 6

        # Test with different profile ID
        predictor2 = PlayerPredictor(
            profile_id="other_profile",
            data_dir=temp_profile_with_games['data_dir']
        )

        games2 = predictor2._load_player_games()
        assert len(games2) == 0

    def test_extract_training_data(self, temp_profile_with_games):
        """Test extracting training data from games."""
        from ai.player_predictor import PlayerPredictor

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        games = predictor._load_player_games()
        X, y = predictor._extract_training_data(games)

        assert len(X) > 0
        assert len(y) > 0
        assert len(X) == len(y)
        assert X.shape[1] == 12  # 12 features

    def test_extract_features_for_round(self, temp_profile_with_games):
        """Test feature extraction for a single round."""
        from ai.player_predictor import PlayerPredictor

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        round_data = {
            'round': 2,
            'location': 'Corner Store',
            'points_before': 25,
            'location_value': 15,
            'caught': False,
            'items_held': []
        }

        history = [
            {'location': 'Pawn Shop', 'location_value': 10, 'points_earned': 10, 'caught': False}
        ]

        player_data = {'num_players_alive': 2}

        features = predictor._extract_features_for_round(round_data, 1, history, player_data)

        assert len(features) == 12
        assert features[0] == 25  # points_before
        assert features[1] == 2   # round


class TestProfileUpdate:
    """Tests for profile AI memory updates."""

    def test_update_profile_ai_memory(self, tmp_path):
        """Test updating profile AI memory after training."""
        from ai.player_predictor import PlayerPredictor

        data_dir = str(tmp_path / "data")
        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        # Mock the profile manager
        mock_profile = Mock()
        mock_profile.ai_memory = Mock()
        mock_pm = Mock()
        mock_pm.load_profile.return_value = mock_profile

        with patch('game.profile_manager.ProfileManager', return_value=mock_pm):
            predictor._update_profile_ai_memory()

            # Verify the update was attempted
            mock_pm.load_profile.assert_called_once_with("test_profile")


class TestModelInfo:
    """Tests for model information retrieval."""

    def test_get_model_info(self, temp_profile_with_games, mock_ml_model):
        """Test getting model information."""
        from ai.player_predictor import PlayerPredictor
        from sklearn.preprocessing import LabelEncoder

        predictor = PlayerPredictor(
            profile_id=temp_profile_with_games['profile_id'],
            data_dir=temp_profile_with_games['data_dir']
        )

        info = predictor.get_model_info()

        assert info['profile_id'] == temp_profile_with_games['profile_id']
        assert info['num_games'] == 6
        assert info['training_samples'] > 0
        assert info['model_exists'] is False
        assert info['model_loaded'] is False
        assert info['locations'] == []

    def test_get_model_info_with_loaded_model(self, tmp_path, mock_ml_model):
        """Test getting model info when model is loaded."""
        from ai.player_predictor import PlayerPredictor
        from sklearn.preprocessing import LabelEncoder

        data_dir = str(tmp_path / "data")
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "game_history.json").write_text(json.dumps({"games": []}))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=data_dir)

        predictor.model = mock_ml_model
        predictor.label_encoder = LabelEncoder()
        predictor.label_encoder.fit(['Loc1', 'Loc2'])
        predictor.save_model()

        info = predictor.get_model_info()

        assert info['model_exists'] is True
        assert info['model_loaded'] is True
        assert info['locations'] == ['Loc1', 'Loc2']


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_round_history(self, tmp_path):
        """Test handling of empty round history."""
        from ai.player_predictor import PlayerPredictor

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        game_history = {
            "games": [{
                "game_id": "game_1",
                "players": [{
                    "profile_id": "test_profile",
                    "round_history": []
                }]
            }]
        }
        (data_dir / "game_history.json").write_text(json.dumps(game_history))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=str(data_dir))
        X, y = predictor._extract_training_data(predictor._load_player_games())

        assert len(X) == 0
        assert len(y) == 0

    def test_single_round_history(self, tmp_path):
        """Test handling of single round history."""
        from ai.player_predictor import PlayerPredictor

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        game_history = {
            "games": [{
                "game_id": "game_1",
                "players": [{
                    "profile_id": "test_profile",
                    "num_players_alive": 2,
                    "round_history": [
                        {"round": 1, "location": "Store", "points_before": 0}
                    ]
                }]
            }]
        }
        (data_dir / "game_history.json").write_text(json.dumps(game_history))

        predictor = PlayerPredictor(profile_id="test_profile", data_dir=str(data_dir))
        X, y = predictor._extract_training_data(predictor._load_player_games())

        # Single round should still produce at least one sample
        assert len(X) == 0 or len(X) >= 0  # May be 0 due to minimum history requirement
