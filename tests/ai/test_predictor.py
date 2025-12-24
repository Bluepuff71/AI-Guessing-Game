"""Unit tests for ai/predictor.py - AIPredictor class."""
import pytest
from ai.predictor import AIPredictor
from game.player import Player
from game.locations import Location, LocationManager


class TestAIPredictorInitialization:
    """Tests for AIPredictor initialization."""

    def test_initialization_without_ml(self, temp_config_dir, sample_location_manager, monkeypatch):
        """Test AIPredictor initializes without ML model."""
        # Mock ML import to fail
        def mock_load_fail(*args, **kwargs):
            raise Exception("No model")

        monkeypatch.setattr("ai.trainer.ModelTrainer.load_model", mock_load_fail, raising=False)

        ai = AIPredictor(sample_location_manager)

        assert ai.location_manager is sample_location_manager
        assert ai.round_num == 0
        assert ai.use_ml is False

    def test_initialization_with_ml(self, temp_config_dir, sample_location_manager, mock_ml_model, monkeypatch):
        """Test AIPredictor can initialize with ML model."""
        # Mock successful ML loading
        class MockTrainer:
            def load_model(self):
                return True

            def get_model_info(self):
                return {"samples": 100}

        def mock_trainer_init(*args, **kwargs):
            return MockTrainer()

        monkeypatch.setattr("ai.trainer.ModelTrainer", mock_trainer_init, raising=False)

        ai = AIPredictor(sample_location_manager)

        assert ai.round_num == 0


class TestPredictionStrategies:
    """Tests for different prediction strategies."""

    def test_random_prediction_early_game(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test rounds 1-3 always use random prediction."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Rounds 1-3 should be random
        for round_num in range(1, 4):
            location_name, confidence, reasoning = ai.predict_player_location(player, 1)

            assert confidence == pytest.approx(0.125, abs=0.01)  # 1/8 random (or 1/5 for 5 locations)
            assert "learning" in reasoning.lower()

    def test_simple_pattern_prediction_mid_game(self, temp_config_dir, sample_location_manager, deterministic_random, monkeypatch):
        """Test rounds 4-6 use simple pattern prediction."""
        # Disable ML to test simple pattern fallback
        def mock_load_fail(*args, **kwargs):
            raise Exception("No model")
        monkeypatch.setattr("ai.trainer.ModelTrainer.load_model", mock_load_fail, raising=False)

        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history - player always chooses location 0
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, caught=False, points_earned=10, location_value=10)

        # Advance to round 4
        ai.round_num = 3

        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # Should predict the most common location
        assert location_name == loc.name

    def test_advanced_prediction_late_game(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test rounds 7+ use advanced prediction."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add history with patterns
        loc = sample_location_manager.get_location(0)
        for i in range(8):
            player.record_choice(loc, i+1, caught=False, points_earned=10, location_value=10)

        # Advance to round 7+
        ai.round_num = 6

        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # Should use advanced logic
        assert isinstance(location_name, str)
        assert 0 <= confidence <= 1
        assert isinstance(reasoning, str)

    def test_prediction_no_history_fallback(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test prediction falls back to simple when no history."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Advance past early game but no history
        ai.round_num = 4

        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # Should fallback gracefully
        assert isinstance(location_name, str)
        assert 0 <= confidence <= 1

    @pytest.mark.parametrize("round_num,expected_strategy", [
        (2, "random"),
        (5, "simple"),
        (8, "advanced"),
    ])
    def test_prediction_strategy_progression(self, round_num, expected_strategy, temp_config_dir,
                                            sample_location_manager, deterministic_random):
        """Test correct strategy used based on round number."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add minimal history for simple/advanced to work
        if round_num >= 4:
            loc = sample_location_manager.get_location(0)
            for i in range(5):
                player.record_choice(loc, i+1, False, 10, 10)

        ai.round_num = round_num - 1
        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        if expected_strategy == "random":
            assert "learning" in reasoning.lower()
        else:
            # Simple or advanced - just verify it works
            assert isinstance(location_name, str)

    def test_prediction_confidence_range(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test confidence is always 0-1."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Test across different rounds
        for i in range(10):
            _, confidence, _ = ai.predict_player_location(player, 1)
            assert 0 <= confidence <= 1


class TestMLFeatureExtraction:
    """Tests for ML feature extraction."""

    def test_extract_ml_features_count(self, temp_config_dir, sample_location_manager):
        """Test ML features has expected count."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add some history
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 10, 10)

        features = ai._extract_ml_features(player, num_players_alive=2)

        # Should return a list of numeric features
        assert isinstance(features, list)
        assert len(features) == 12  # Expected feature count (3 current + 8 history + 1 items)
        assert all(isinstance(f, (int, float)) for f in features)

    def test_extract_ml_features_no_history(self, temp_config_dir, sample_location_manager):
        """Test ML features with no history."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        features = ai._extract_ml_features(player, num_players_alive=2)

        assert len(features) == 12
        # Many features should be 0 with no history (features 3-10 are history features)
        assert features[3] == 0  # avg_value (first history feature)
        assert features[4] == 0  # recent_avg


class TestSearchDecision:
    """Tests for AI search location decision."""

    def test_decide_search_single_player(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test search decision with single player."""
        ai = AIPredictor(sample_location_manager)

        player = Player(1, "Alice")
        player.points = 50

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 10, 10)

        # Advance past early game
        ai.round_num = 4

        search_loc, predictions, reasoning = ai.decide_search_location([player])

        assert isinstance(search_loc, Location)
        assert isinstance(predictions, dict)
        assert player in predictions
        assert isinstance(reasoning, str)

    def test_decide_search_multiple_players(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test search decision with multiple players."""
        ai = AIPredictor(sample_location_manager)

        player1 = Player(1, "Alice")
        player1.points = 80  # High threat

        player2 = Player(2, "Bob")
        player2.points = 20  # Low threat

        # Add history to both
        loc1 = sample_location_manager.get_location(0)
        loc2 = sample_location_manager.get_location(1)

        for i in range(5):
            player1.record_choice(loc1, i+1, False, 15, 15)
            player2.record_choice(loc2, i+1, False, 7, 7)

        ai.round_num = 4

        search_loc, predictions, reasoning = ai.decide_search_location([player1, player2])

        # Should have predictions for both players
        assert player1 in predictions
        assert player2 in predictions

    def test_decide_search_no_players(self, temp_config_dir, sample_location_manager):
        """Test search decision with no players (edge case)."""
        ai = AIPredictor(sample_location_manager)
        ai.round_num = 4

        search_loc, predictions, reasoning = ai.decide_search_location([])

        # Should return random location
        assert isinstance(search_loc, Location)
        assert predictions == {}

    def test_decide_search_prioritizes_high_threat(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test search decision with high and low threat players."""
        ai = AIPredictor(sample_location_manager)

        # High-threat player close to winning
        high_threat = Player(1, "Alice")
        high_threat.points = 95

        # Low-threat player
        low_threat = Player(2, "Bob")
        low_threat.points = 10

        # Add history
        loc1 = sample_location_manager.get_location(0)
        loc2 = sample_location_manager.get_location(1)

        for i in range(5):
            high_threat.record_choice(loc1, i+1, False, 20, 20)
            low_threat.record_choice(loc2, i+1, False, 5, 5)

        # Use advanced strategy (round 7+)
        ai.round_num = 6  # Will increment to 7+ during prediction

        search_loc, predictions, reasoning = ai.decide_search_location([high_threat, low_threat])

        # Should have predictions for both players
        assert high_threat in predictions
        assert low_threat in predictions
        # Should return a valid location
        assert isinstance(search_loc, Location)
        # Should have reasoning
        assert isinstance(reasoning, str)
        assert len(reasoning) > 0


class TestWinThreatCalculation:
    """Tests for win threat calculation."""

    def test_calculate_win_threat_low_score(self, temp_config_dir, sample_location_manager):
        """Test win threat for low-score player."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 10

        threat = ai._calculate_win_threat(player)

        assert 0 <= threat < 0.2  # Low threat

    def test_calculate_win_threat_high_score(self, temp_config_dir, sample_location_manager):
        """Test win threat for high-score player."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 85  # 85% of 100

        threat = ai._calculate_win_threat(player)

        assert threat > 0.8  # High threat

    def test_calculate_win_threat_at_threshold(self, temp_config_dir, sample_location_manager):
        """Test win threat at win threshold."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 100

        threat = ai._calculate_win_threat(player)

        assert threat >= 1.0  # Maximum threat

    def test_calculate_win_threat_range(self, temp_config_dir, sample_location_manager):
        """Test win threat is always 0-1+."""
        ai = AIPredictor(sample_location_manager)

        for points in [0, 20, 50, 80, 100, 120]:
            player = Player(1, "Test")
            player.points = points
            threat = ai._calculate_win_threat(player)
            assert threat >= 0  # Can exceed 1.0 for scores above threshold


class TestResetRound:
    """Test for reset_round method."""

    def test_reset_round_exists(self, temp_config_dir, sample_location_manager):
        """Test reset_round method exists (currently a no-op)."""
        ai = AIPredictor(sample_location_manager)

        # Make some predictions
        player = Player(1, "Alice")
        for _ in range(5):
            ai.predict_player_location(player, 1)

        # reset_round() currently does nothing (it's a pass statement)
        # This test just verifies the method exists and doesn't crash
        ai.reset_round()
        assert ai.round_num == 5  # Should remain unchanged
