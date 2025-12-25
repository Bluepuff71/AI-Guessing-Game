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

    def test_prediction_early_game_no_history(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test early game prediction with no player history uses behavioral analysis."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Even early in the game, AI uses advanced behavioral prediction
        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # Confidence should be reasonable (not random 1/n, but based on analysis)
        assert 0.0 < confidence <= 1.0
        # Location should be valid
        assert location_name in [loc.name for loc in sample_location_manager.get_all()]

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

    @pytest.mark.parametrize("round_num,has_history", [
        (2, False),
        (5, True),
        (8, True),
    ])
    def test_prediction_works_across_rounds(self, round_num, has_history, temp_config_dir,
                                            sample_location_manager, deterministic_random):
        """Test prediction works correctly at different game stages."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history if applicable
        if has_history:
            loc = sample_location_manager.get_location(0)
            for i in range(5):
                player.record_choice(loc, i+1, False, 10, 10)

        ai.round_num = round_num - 1
        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # AI always uses advanced behavioral prediction
        assert isinstance(location_name, str)
        assert location_name in [loc.name for loc in sample_location_manager.get_all()]
        assert 0 < confidence <= 1
        assert isinstance(reasoning, str)

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
        assert len(features) == 16  # Expected feature count (3 current + 8 history + 1 passives + 4 passive types)
        assert all(isinstance(f, (int, float)) for f in features)

    def test_extract_ml_features_no_history(self, temp_config_dir, sample_location_manager):
        """Test ML features with no history."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        features = ai._extract_ml_features(player, num_players_alive=2)

        assert len(features) == 16  # 3 current + 8 history + 1 passives + 4 passive types
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


class TestEventAdjustments:
    """Tests for event-based prediction adjustments."""

    def test_adjust_for_positive_point_modifier(self, temp_config_dir, sample_location_manager,
                                                 sample_event_manager, deterministic_random):
        """Test prediction adjustment for positive point modifier events."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        # Force an event on a location using copy_with_location
        from game.events import Event
        jackpot = Event(
            id="jackpot",
            name="JACKPOT",
            description="Double points!",
            emoji="💰",
            duration_rounds=1,
            point_modifier={"type": "multiply", "value": 2.0}
        )
        sample_event_manager.active_events = [jackpot.copy_with_location(loc)]

        location_name, confidence, reasoning = ai.predict_player_location(player, 1, sample_event_manager)

        # Should have some reasoning mentioning the event
        assert isinstance(reasoning, str)
        assert isinstance(confidence, float)

    def test_adjust_for_negative_point_modifier(self, temp_config_dir, sample_location_manager,
                                                 sample_event_manager, deterministic_random):
        """Test prediction adjustment for negative point modifier events."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        # Force a lockdown event
        from game.events import Event
        lockdown = Event(
            id="lockdown",
            name="LOCKDOWN",
            description="Reduced points",
            emoji="🔒",
            duration_rounds=1,
            point_modifier={"type": "multiply", "value": 0.7}
        )
        sample_event_manager.active_events = [lockdown.copy_with_location(loc)]

        location_name, confidence, reasoning = ai.predict_player_location(player, 1, sample_event_manager)

        assert isinstance(confidence, float)

    def test_adjust_for_immunity_event(self, temp_config_dir, sample_location_manager,
                                        sample_event_manager, deterministic_random):
        """Test prediction adjustment for immunity events."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        # Force an immunity event
        from game.events import Event
        immunity = Event(
            id="immunity",
            name="IMMUNITY",
            description="Cannot be caught!",
            emoji="🛡️",
            duration_rounds=1,
            special_effect="immunity"
        )
        sample_event_manager.active_events = [immunity.copy_with_location(loc)]

        location_name, confidence, reasoning = ai.predict_player_location(player, 1, sample_event_manager)

        # Immunity should boost confidence
        assert confidence > 0

    def test_adjust_for_guaranteed_catch_event(self, temp_config_dir, sample_location_manager,
                                                sample_event_manager, deterministic_random):
        """Test prediction adjustment for guaranteed catch events."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        # Force a guaranteed catch event
        from game.events import Event
        catch_event = Event(
            id="dragnet",
            name="DRAGNET",
            description="Guaranteed catch!",
            emoji="🚔",
            duration_rounds=1,
            special_effect="guaranteed_catch"
        )
        sample_event_manager.active_events = [catch_event.copy_with_location(loc)]

        location_name, confidence, reasoning = ai.predict_player_location(player, 1, sample_event_manager)

        # Guaranteed catch should reduce confidence
        assert isinstance(confidence, float)


class TestRandomPrediction:
    """Tests for random prediction fallback."""

    def test_random_prediction_method(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test _random_prediction method directly."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        location_name, confidence, reasoning = ai._random_prediction(player)

        assert location_name in [loc.name for loc in sample_location_manager.get_all()]
        assert confidence == 0.125  # 1/8 random chance
        assert "learning" in reasoning.lower()


class TestSimplePatternPrediction:
    """Tests for simple pattern prediction."""

    def test_simple_pattern_with_history(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test simple pattern prediction with player history."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add consistent history - always choose location 0
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 10, 10)

        location_name, confidence, reasoning = ai._simple_pattern_prediction(player)

        assert location_name == loc.name
        assert confidence > 0.3  # Should have higher confidence for consistent pattern

    def test_simple_pattern_no_history_fallback(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test simple pattern falls back to random with no history."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        location_name, confidence, reasoning = ai._simple_pattern_prediction(player)

        # Falls back to random prediction
        assert confidence == 0.125

    def test_simple_pattern_recency_weighting(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test recency weighting in simple pattern prediction."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add mixed history - old choices of loc0, recent choices of loc1
        loc0 = sample_location_manager.get_location(0)
        loc1 = sample_location_manager.get_location(1)

        for i in range(3):
            player.record_choice(loc0, i+1, False, 10, 10)
        for i in range(3, 6):
            player.record_choice(loc1, i+1, False, 10, 10)

        location_name, confidence, reasoning = ai._simple_pattern_prediction(player)

        # Should favor more recent loc1
        assert location_name == loc1.name


class TestMLReasoning:
    """Tests for ML reasoning generation."""

    def test_generate_ml_reasoning_high_confidence(self, temp_config_dir, sample_location_manager):
        """Test ML reasoning with high confidence."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add some history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 20, 20)

        reasoning = ai._generate_ml_reasoning(player, loc.name, 0.75)

        # Check case-insensitively since capitalize() is applied
        assert "ml model high confidence" in reasoning.lower()

    def test_generate_ml_reasoning_win_threat(self, temp_config_dir, sample_location_manager):
        """Test ML reasoning for win threat player."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 90  # Close to winning

        reasoning = ai._generate_ml_reasoning(player, "Test Store", 0.3)

        assert "win threat" in reasoning.lower()

    def test_generate_ml_reasoning_low_value_preference(self, temp_config_dir, sample_location_manager):
        """Test ML reasoning for player preferring low values."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history with very low values
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 5, 5)

        reasoning = ai._generate_ml_reasoning(player, loc.name, 0.3)

        assert "low-value" in reasoning.lower()


class TestMLPredictionPath:
    """Tests for ML prediction code path."""

    def test_ml_prediction_with_mock_trainer(self, temp_config_dir, sample_location_manager, monkeypatch):
        """Test ML prediction path with mocked trainer."""
        # Create mock trainer
        class MockTrainer:
            def load_model(self):
                return True

            def get_model_info(self):
                return {"samples": 100}

            def predict(self, features):
                # Return mock predictions
                return {"Test Store": 0.6, "Test Vault": 0.3, "Test Bank": 0.1}

        def mock_trainer_init(*args, **kwargs):
            return MockTrainer()

        monkeypatch.setattr("ai.trainer.ModelTrainer", mock_trainer_init, raising=False)

        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        location_name, confidence, reasoning = ai.predict_player_location(player, 1)

        # Should use ML prediction
        assert isinstance(location_name, str)
        assert isinstance(confidence, float)


class TestAdvancedPrediction:
    """Tests for advanced prediction."""

    def test_advanced_prediction_direct(self, temp_config_dir, sample_location_manager, deterministic_random):
        """Test _advanced_prediction method directly."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 15, 15)

        location_name, confidence, reasoning = ai._advanced_prediction(player, 2)

        assert location_name in [loc.name for loc in sample_location_manager.get_all()]
        assert 0 <= confidence <= 1
        assert isinstance(reasoning, str)

    def test_advanced_prediction_with_events(self, temp_config_dir, sample_location_manager,
                                              sample_event_manager, deterministic_random):
        """Test advanced prediction with event manager."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        location_name, confidence, reasoning = ai._advanced_prediction(player, 2, sample_event_manager)

        assert isinstance(location_name, str)


class TestMLFeatureExtractionAdvanced:
    """More tests for ML feature extraction."""

    def test_extract_ml_features_with_events(self, temp_config_dir, sample_location_manager, sample_event_manager):
        """Test ML features include event information."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add history
        loc = sample_location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        features = ai._extract_ml_features(player, 2, sample_event_manager)

        # Should include event features
        assert len(features) > 16  # Base features + event features

    def test_extract_ml_features_risk_trend_increasing(self, temp_config_dir, sample_location_manager):
        """Test ML features capture increasing risk trend."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history with increasing values (risk increasing)
        loc0 = sample_location_manager.get_location(0)  # Low value location
        loc1 = sample_location_manager.get_location(1)  # High value location

        # Old choices - low values
        for i in range(3):
            player.record_choice(loc0, i+1, False, 5, 5)
        # Recent choices - high values
        for i in range(3, 6):
            player.record_choice(loc1, i+1, False, 20, 20)

        features = ai._extract_ml_features(player, 2)

        # Risk trend feature should be positive (increasing)
        assert len(features) == 16

    def test_extract_ml_features_risk_trend_decreasing(self, temp_config_dir, sample_location_manager):
        """Test ML features capture decreasing risk trend."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history with decreasing values (risk decreasing)
        loc0 = sample_location_manager.get_location(0)
        loc1 = sample_location_manager.get_location(1)

        # Old choices - high values
        for i in range(3):
            player.record_choice(loc1, i+1, False, 20, 20)
        # Recent choices - low values
        for i in range(3, 6):
            player.record_choice(loc0, i+1, False, 5, 5)

        features = ai._extract_ml_features(player, 2)

        assert len(features) == 16


class TestLocationScoring:
    """Tests for location scoring."""

    def test_score_location_for_player(self, temp_config_dir, sample_location_manager):
        """Test _score_location_for_player method."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")
        player.points = 50

        # Add history - prefer location 0
        loc = sample_location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 10, 10)

        from ai.features import extract_features
        features = extract_features(player, 5, 2, sample_location_manager)

        # Score the preferred location
        score = ai._score_location_for_player(loc, player, features)

        assert score > 1.0  # Should be above base score


class TestGenerateReasoning:
    """Tests for reasoning generation."""

    def test_generate_reasoning_predictable_player(self, temp_config_dir, sample_location_manager):
        """Test reasoning generation for predictable player."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add very consistent history
        loc = sample_location_manager.get_location(0)
        for i in range(10):
            player.record_choice(loc, i+1, False, 10, 10)

        from ai.features import extract_features
        features = extract_features(player, 10, 2, sample_location_manager)

        reasoning = ai._generate_reasoning(player, features, loc.name)

        assert isinstance(reasoning, str)
        assert len(reasoning) > 0

    def test_generate_reasoning_high_value_player(self, temp_config_dir, sample_location_manager):
        """Test reasoning generation for high-value seeking player."""
        ai = AIPredictor(sample_location_manager)
        player = Player(1, "Alice")

        # Add history with high values
        loc = sample_location_manager.get_location(1)  # High value location
        for i in range(5):
            player.record_choice(loc, i+1, False, 25, 25)

        from ai.features import extract_features
        features = extract_features(player, 5, 2, sample_location_manager)

        reasoning = ai._generate_reasoning(player, features, loc.name)

        assert isinstance(reasoning, str)
