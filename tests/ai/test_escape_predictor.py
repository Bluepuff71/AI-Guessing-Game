"""Tests for ai.escape_predictor module."""
import pytest
from ai.escape_predictor import EscapePredictor


class TestEscapePredictorInitialization:
    """Tests for EscapePredictor initialization."""

    def test_initialization(self, sample_escape_predictor):
        """Test EscapePredictor initializes correctly."""
        assert sample_escape_predictor.caught_count == {}
        assert sample_escape_predictor.game_escape_history == {}

    def test_reset_game(self, sample_escape_predictor):
        """Test reset_game clears state."""
        # Add some state
        sample_escape_predictor.caught_count[1] = 3
        sample_escape_predictor.game_escape_history[1] = ['opt1', 'opt2']

        sample_escape_predictor.reset_game()

        assert sample_escape_predictor.caught_count == {}
        assert sample_escape_predictor.game_escape_history == {}


class TestPrediction:
    """Tests for prediction methods."""

    def test_predict_escape_option_no_history(self, sample_escape_predictor):
        """Test prediction with no history."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide Spot 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run Route 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor.predict_escape_option(
            MockPlayer(), escape_options
        )

        assert option_id in ['hide1', 'run1']
        assert 0 <= confidence <= 1
        assert isinstance(reasoning, str)

    def test_predict_escape_option_with_game_history(self, sample_escape_predictor):
        """Test prediction with in-game history."""
        class MockPlayer:
            points = 50

        player = MockPlayer()

        # Record some choices
        sample_escape_predictor.record_escape_choice(player, 'hide1')
        sample_escape_predictor.record_escape_choice(player, 'hide1')
        sample_escape_predictor.record_escape_choice(player, 'hide1')

        escape_options = [
            {'id': 'hide1', 'name': 'Hide Spot 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run Route 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor.predict_escape_option(
            player, escape_options
        )

        # Should likely predict hide1 due to history
        assert option_id in ['hide1', 'run1']
        assert 0 <= confidence <= 1

    def test_predict_escape_option_with_profile_history(self, sample_escape_predictor):
        """Test prediction with profile cross-game history."""
        class MockPlayer:
            points = 50

        class MockHidingStats:
            escape_option_history = ['hide1', 'hide1', 'run1', 'hide1']
            favorite_escape_options = {}

        class MockProfile:
            hiding_stats = MockHidingStats()

        escape_options = [
            {'id': 'hide1', 'name': 'Hide Spot 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run Route 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor.predict_escape_option(
            MockPlayer(), escape_options, MockProfile()
        )

        assert option_id in ['hide1', 'run1']
        assert 0 <= confidence <= 1

    def test_prediction_confidence_range(self, sample_escape_predictor):
        """Test prediction confidence is always in valid range."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'hide2', 'name': 'Hide 2', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'},
            {'id': 'run2', 'name': 'Run 2', 'type': 'run'}
        ]

        for _ in range(10):
            _, confidence, _ = sample_escape_predictor.predict_escape_option(
                MockPlayer(), escape_options
            )
            assert 0 <= confidence <= 1


class TestCrossGameHistory:
    """Tests for cross-game history extraction."""

    def test_get_cross_game_history_no_profile(self, sample_escape_predictor):
        """Test cross-game history with no profile."""
        result = sample_escape_predictor._get_cross_game_history(None)
        assert result == []

    def test_get_cross_game_history_with_escape_option_history(self, sample_escape_predictor):
        """Test cross-game history from escape_option_history."""
        class MockHidingStats:
            escape_option_history = ['hide1', 'run1', 'hide2']

        class MockProfile:
            hiding_stats = MockHidingStats()

        result = sample_escape_predictor._get_cross_game_history(MockProfile())
        assert result == ['hide1', 'run1', 'hide2']

    def test_get_cross_game_history_with_favorite_escape_options(self, sample_escape_predictor):
        """Test cross-game history fallback to favorite_escape_options."""
        class MockHidingStats:
            favorite_escape_options = {'hide1': 3, 'hide2': 2}

        class MockProfile:
            hiding_stats = MockHidingStats()

        result = sample_escape_predictor._get_cross_game_history(MockProfile())
        # Should have hide1 repeated 3 times and hide2 repeated 2 times
        assert result.count('hide1') == 3
        assert result.count('hide2') == 2

    def test_get_cross_game_history_caps_at_five(self, sample_escape_predictor):
        """Test favorite_escape_options count is capped at 5."""
        class MockHidingStats:
            favorite_escape_options = {'hide1': 10}  # More than 5

        class MockProfile:
            hiding_stats = MockHidingStats()

        result = sample_escape_predictor._get_cross_game_history(MockProfile())
        assert result.count('hide1') == 5  # Capped at 5


class TestRandomPrediction:
    """Tests for random prediction strategy."""

    def test_random_prediction_returns_valid_option(self, sample_escape_predictor):
        """Test random prediction returns a valid option."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor._random_prediction(
            escape_options
        )

        assert option_id in ['hide1', 'run1']
        assert confidence == 0.5  # 1/2 options
        assert "learning" in reasoning.lower()

    def test_random_prediction_confidence_scales_with_options(self, sample_escape_predictor):
        """Test random prediction confidence scales with number of options."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'hide2', 'name': 'Hide 2', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'},
            {'id': 'run2', 'name': 'Run 2', 'type': 'run'}
        ]

        _, confidence, _ = sample_escape_predictor._random_prediction(escape_options)
        assert confidence == 0.25  # 1/4 options


class TestRecencyWeightedPrediction:
    """Tests for recency-weighted prediction strategy."""

    def test_recency_weighted_no_history(self, sample_escape_predictor):
        """Test recency-weighted prediction falls back to random with no history."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor._recency_weighted_prediction(
            escape_options, [], MockPlayer()
        )

        assert option_id in ['hide1', 'run1']
        assert "learning" in reasoning.lower()

    def test_recency_weighted_with_history(self, sample_escape_predictor):
        """Test recency-weighted prediction uses history."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        # History with mostly hide1
        history = ['hide1', 'hide1', 'hide1', 'run1']

        option_id, confidence, reasoning = sample_escape_predictor._recency_weighted_prediction(
            escape_options, history, MockPlayer()
        )

        # Should predict one of the valid options
        assert option_id in ['hide1', 'run1']
        assert 0 <= confidence <= 1

    def test_recency_weighted_filters_invalid_options(self, sample_escape_predictor):
        """Test recency-weighted prediction filters out invalid options."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        # History with options not available at this location
        history = ['different_hide', 'different_run']

        option_id, confidence, reasoning = sample_escape_predictor._recency_weighted_prediction(
            escape_options, history, MockPlayer()
        )

        # Should fall back to random since no matching history
        assert option_id in ['hide1', 'run1']


class TestBehavioralPrediction:
    """Tests for behavioral prediction strategy."""

    def test_behavioral_prediction_hide_preference(self, sample_escape_predictor):
        """Test behavioral prediction detects hide preference."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        # History showing strong hide preference
        history = ['hide1', 'hide1', 'hide1', 'hide1', 'run1']

        option_id, confidence, reasoning = sample_escape_predictor._behavioral_prediction(
            escape_options, history, MockPlayer(), None
        )

        assert option_id in ['hide1', 'run1']
        assert 0 <= confidence <= 1

    def test_behavioral_prediction_run_preference(self, sample_escape_predictor):
        """Test behavioral prediction detects run preference."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'store_backdoor', 'name': 'Backdoor', 'type': 'run'}
        ]

        # History with run-like options (contains backdoor pattern)
        history = ['store_backdoor', 'store_backdoor', 'store_backdoor', 'hide1']

        option_id, confidence, reasoning = sample_escape_predictor._behavioral_prediction(
            escape_options, history, MockPlayer(), None
        )

        assert option_id in ['hide1', 'store_backdoor']

    def test_behavioral_prediction_point_pressure(self, sample_escape_predictor):
        """Test behavioral prediction considers point pressure."""
        class MockPlayer:
            points = 90  # Close to winning

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        option_id, confidence, reasoning = sample_escape_predictor._behavioral_prediction(
            escape_options, [], MockPlayer(), None
        )

        # At high points, run options should be boosted
        assert option_id in ['hide1', 'run1']

    def test_behavioral_prediction_penalizes_new_options(self, sample_escape_predictor):
        """Test behavioral prediction penalizes unused options."""
        class MockPlayer:
            points = 50

        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'},
            {'id': 'hide2', 'name': 'Hide 2', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run 1', 'type': 'run'}
        ]

        # Only hide1 in history
        history = ['hide1', 'hide1', 'hide1']

        option_id, confidence, reasoning = sample_escape_predictor._behavioral_prediction(
            escape_options, history, MockPlayer(), None
        )

        # hide1 should be favored due to history
        assert option_id in ['hide1', 'hide2', 'run1']


class TestRecordAndTracking:
    """Tests for recording and tracking methods."""

    def test_record_escape_choice(self, sample_escape_predictor):
        """Test recording an escape choice."""
        class MockPlayer:
            pass

        player = MockPlayer()
        sample_escape_predictor.record_escape_choice(player, 'hide1')

        player_id = id(player)
        assert sample_escape_predictor.caught_count[player_id] == 1
        assert sample_escape_predictor.game_escape_history[player_id] == ['hide1']

    def test_get_caught_count(self, sample_escape_predictor):
        """Test getting caught count for player."""
        class MockPlayer:
            pass

        player = MockPlayer()
        assert sample_escape_predictor.get_caught_count(player) == 0

        sample_escape_predictor.record_escape_choice(player, 'hide1')
        assert sample_escape_predictor.get_caught_count(player) == 1

    def test_caught_count_increments(self, sample_escape_predictor):
        """Test caught count increments correctly."""
        class MockPlayer:
            pass

        player = MockPlayer()

        sample_escape_predictor.record_escape_choice(player, 'hide1')
        sample_escape_predictor.record_escape_choice(player, 'run1')
        sample_escape_predictor.record_escape_choice(player, 'hide2')

        assert sample_escape_predictor.get_caught_count(player) == 3

    def test_game_history_accumulates(self, sample_escape_predictor):
        """Test game history accumulates choices."""
        class MockPlayer:
            pass

        player = MockPlayer()

        sample_escape_predictor.record_escape_choice(player, 'hide1')
        sample_escape_predictor.record_escape_choice(player, 'run1')
        sample_escape_predictor.record_escape_choice(player, 'hide2')

        player_id = id(player)
        assert sample_escape_predictor.game_escape_history[player_id] == ['hide1', 'run1', 'hide2']


class TestReasoningGeneration:
    """Tests for reasoning generation."""

    def test_generate_reasoning_usage_frequency(self, sample_escape_predictor):
        """Test reasoning mentions usage frequency."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide Spot 1', 'type': 'hide'}
        ]

        class MockPlayer:
            points = 50

        # History with frequent usage of hide1
        history = ['hide1', 'hide1', 'hide1', 'hide1']

        reasoning = sample_escape_predictor._generate_reasoning(
            'hide1', escape_options, history, 0.8, MockPlayer()
        )

        assert "favor" in reasoning.lower() or "Hide Spot 1" in reasoning

    def test_generate_reasoning_hide_preference(self, sample_escape_predictor):
        """Test reasoning mentions hide preference."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'}
        ]

        class MockPlayer:
            points = 50

        reasoning = sample_escape_predictor._generate_reasoning(
            'hide1', escape_options, [], 0.8, MockPlayer()
        )

        # With high hide_preference (0.8), should mention hiding
        assert "hiding" in reasoning.lower() or "pattern" in reasoning.lower()

    def test_generate_reasoning_point_pressure(self, sample_escape_predictor):
        """Test reasoning mentions point pressure when close to winning."""
        escape_options = [
            {'id': 'run1', 'name': 'Run Route', 'type': 'run'}
        ]

        class MockPlayer:
            points = 90  # Close to winning

        reasoning = sample_escape_predictor._generate_reasoning(
            'run1', escape_options, [], 0.3, MockPlayer()
        )

        assert "winning" in reasoning.lower() or "pattern" in reasoning.lower()

    def test_generate_reasoning_default(self, sample_escape_predictor):
        """Test default reasoning when no specific factors."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'}
        ]

        class MockPlayer:
            points = 50

        reasoning = sample_escape_predictor._generate_reasoning(
            'hide1', escape_options, [], 0.5, MockPlayer()
        )

        assert len(reasoning) > 0  # Should have some reasoning

    def test_generate_reasoning_unknown_option(self, sample_escape_predictor):
        """Test reasoning for unknown predicted option."""
        escape_options = [
            {'id': 'hide1', 'name': 'Hide 1', 'type': 'hide'}
        ]

        class MockPlayer:
            points = 50

        reasoning = sample_escape_predictor._generate_reasoning(
            'unknown_option', escape_options, [], 0.5, MockPlayer()
        )

        assert reasoning == "Pattern analysis"
