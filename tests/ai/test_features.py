"""Unit tests for ai/features.py - Feature extraction and analysis."""
import pytest
from ai.features import extract_features, calculate_predictability, generate_insights
from game.player import Player
from game.locations import Location, LocationManager


class TestExtractFeatures:
    """Tests for extract_features function."""

    def test_extract_features_complete(self, temp_config_dir, sample_location_manager):
        """Test feature extraction with full player history."""
        player = Player(1, "Alice")
        player.points = 50
        loc_manager = sample_location_manager

        # Add some history
        for i in range(5):
            loc = loc_manager.get_location(i % 3)
            player.record_choice(loc, i+1, caught=False, points_earned=10, location_value=10)

        features = extract_features(player, round_num=6, num_players_alive=2, location_manager=loc_manager)

        # Verify all expected features are present
        assert 'current_score' in features
        assert 'round_number' in features
        assert 'players_alive' in features
        assert 'points_to_win' in features
        assert 'win_threat' in features
        assert 'avg_location_value' in features
        assert 'choice_variety' in features
        assert 'high_value_preference' in features
        assert 'total_choices' in features
        assert 'num_passives' in features
        assert 'recent_avg_value' in features
        assert 'risk_trend' in features

        # Verify values
        assert features['current_score'] == 50
        assert features['round_number'] == 6
        assert features['players_alive'] == 2
        assert features['total_choices'] == 5

    def test_extract_features_no_history(self, temp_config_dir, sample_location_manager):
        """Test feature extraction with no player history."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        features = extract_features(player, round_num=1, num_players_alive=2, location_manager=loc_manager)

        assert features['current_score'] == 0
        assert features['total_choices'] == 0
        assert features['avg_location_value'] == 0
        assert features['recent_avg_value'] == 0
        assert features['risk_trend'] == 0

    def test_extract_features_win_threat_calculation(self, temp_config_dir, sample_location_manager):
        """Test win threat calculation at different score levels."""
        loc_manager = sample_location_manager

        # Low score - no threat
        player1 = Player(1, "Alice")
        player1.points = 10
        features1 = extract_features(player1, 1, 2, loc_manager)
        assert features1['win_threat'] < 0.2

        # 80% of win threshold (80 points) - high threat
        player2 = Player(2, "Bob")
        player2.points = 85
        features2 = extract_features(player2, 1, 2, loc_manager)
        assert features2['win_threat'] >= 0.8

        # At win threshold
        player3 = Player(3, "Charlie")
        player3.points = 100
        features3 = extract_features(player3, 1, 2, loc_manager)
        assert features3['win_threat'] == 1.0

    def test_extract_features_risk_trend_increasing(self, temp_config_dir, sample_location_manager):
        """Test risk trend detection when player is escalating."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Add history with increasing values
        low_loc = Location("Low", "🏪", 5, 10)
        high_loc = Location("High", "💎", 15, 25)

        player.record_choice(low_loc, 1, False, 7, 7)
        player.record_choice(low_loc, 2, False, 8, 8)
        player.record_choice(high_loc, 3, False, 20, 20)

        features = extract_features(player, 4, 2, loc_manager)
        assert features['risk_trend'] == 1  # Increasing

    def test_extract_features_risk_trend_decreasing(self, temp_config_dir, sample_location_manager):
        """Test risk trend detection when player is de-escalating."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Add history with decreasing values
        high_loc = Location("High", "💎", 15, 25)
        low_loc = Location("Low", "🏪", 5, 10)

        player.record_choice(high_loc, 1, False, 20, 20)
        player.record_choice(high_loc, 2, False, 18, 18)
        player.record_choice(low_loc, 3, False, 7, 7)

        features = extract_features(player, 4, 2, loc_manager)
        assert features['risk_trend'] == -1  # Decreasing

    def test_extract_features_risk_trend_stable(self, temp_config_dir, sample_location_manager):
        """Test risk trend detection when player is consistent."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Add history with stable values
        mid_loc = Location("Mid", "🏪", 10, 15)

        player.record_choice(mid_loc, 1, False, 12, 12)
        player.record_choice(mid_loc, 2, False, 13, 13)
        player.record_choice(mid_loc, 3, False, 12, 12)

        features = extract_features(player, 4, 2, loc_manager)
        assert features['risk_trend'] == 0  # Stable

    def test_extract_features_high_value_frequency(self, temp_config_dir, sample_location_manager):
        """Test high-value location frequency tracking."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Create high-value locations with specific names
        bank = Location("Bank Vault", "🏦", 20, 30)
        jewelry = Location("Jewelry Store", "💎", 15, 25)

        # All choices are high-value
        for i in range(4):
            player.record_choice(bank, i+1, False, 25, 25)

        features = extract_features(player, 5, 2, loc_manager)
        # Should have high frequency
        assert features['high_value_location_frequency'] > 0


class TestCalculatePredictability:
    """Tests for calculate_predictability function."""

    def test_predictability_insufficient_history(self, temp_config_dir):
        """Test predictability with <3 choices returns default."""
        player = Player(1, "Alice")

        # 0 choices
        pred1 = calculate_predictability(player)
        assert pred1 == 0.3

        # 2 choices
        loc = Location("Test", "🏪", 5, 10)
        player.record_choice(loc, 1, False, 7)
        player.record_choice(loc, 2, False, 8)

        pred2 = calculate_predictability(player)
        assert pred2 == 0.3

    def test_predictability_low_variety_high_score(self, temp_config_dir, sample_location_manager):
        """Test high predictability from low variety."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Visit same location 10 times
        loc = loc_manager.get_location(0)
        for i in range(10):
            player.record_choice(loc, i+1, False, 7)

        pred = calculate_predictability(player)
        # Low variety should give high predictability
        assert pred > 0.5

    def test_predictability_high_variety_low_score(self, temp_config_dir, sample_location_manager):
        """Test low predictability from high variety."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Visit all locations
        for i in range(9):
            loc = loc_manager.get_location(i % 3)
            player.record_choice(loc, i+1, False, 10)

        pred = calculate_predictability(player)
        # High variety should give lower predictability
        assert pred < 0.7

    def test_predictability_range_bounds(self, temp_config_dir, sample_location_manager):
        """Test predictability is always in 0-1 range."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Add various patterns
        for i in range(10):
            loc = loc_manager.get_location(i % 3)
            player.record_choice(loc, i+1, False, 10)

        pred = calculate_predictability(player)
        assert 0.0 <= pred <= 1.0


class TestGenerateInsights:
    """Tests for generate_insights function."""

    def test_insights_insufficient_history(self, temp_config_dir):
        """Test insights with insufficient history."""
        player = Player(1, "Alice")

        insights = generate_insights(player, num_locations=5)

        assert insights['predictability'] == 0.3
        assert "Not enough data" in insights['patterns'][0]

    def test_insights_high_value_bias_pattern(self, temp_config_dir):
        """Test detection of high-value bias pattern."""
        player = Player(1, "Alice")

        # Add high-value choices (15+ points)
        high_loc = Location("High", "💎", 15, 25)
        for i in range(10):
            player.record_choice(high_loc, i+1, False, 20, 20)

        insights = generate_insights(player, num_locations=5)

        # Should detect high-value bias
        assert any("High-value bias" in p for p in insights['patterns'])
        assert any("low-value locations" in t for t in insights['tips'])

    def test_insights_limited_variety_pattern(self, temp_config_dir, sample_location_manager):
        """Test detection of limited variety pattern."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Visit only 1 location repeatedly
        loc = loc_manager.get_location(0)
        for i in range(10):
            player.record_choice(loc, i+1, False, 7)

        insights = generate_insights(player, num_locations=5)

        # Should detect limited variety
        assert any("Limited variety" in p for p in insights['patterns'])
        assert any("Visit all locations" in t for t in insights['tips'])

    def test_insights_favorite_location_pattern(self, temp_config_dir, sample_location_manager):
        """Test detection of favorite location pattern."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Visit one location many times
        favorite = loc_manager.get_location(0)
        other = loc_manager.get_location(1)

        for i in range(8):
            player.record_choice(favorite, i+1, False, 10)
        for i in range(2):
            player.record_choice(other, i+9, False, 10)

        insights = generate_insights(player, num_locations=5)

        # Should detect favorite location
        assert any("Favorite location" in p for p in insights['patterns'])

    def test_insights_win_rush_pattern(self, temp_config_dir):
        """Test detection of win-rush behavior."""
        player = Player(1, "Alice")
        player.points = 85  # 85% of 100 (win threshold)

        # Add aggressive late-game choices
        high_loc = Location("High", "💎", 20, 30)
        for i in range(3):
            player.record_choice(high_loc, i+1, False, 25, 25)

        insights = generate_insights(player, num_locations=5)

        # Should detect win-rush
        assert any("Win-rush" in p for p in insights['patterns'])
        assert any("safer choices" in t for t in insights['tips'])

    def test_insights_structure(self, temp_config_dir, sample_location_manager):
        """Test insights dictionary structure."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Add some history
        for i in range(5):
            loc = loc_manager.get_location(i % 3)
            player.record_choice(loc, i+1, False, 10)

        insights = generate_insights(player, num_locations=5)

        assert 'predictability' in insights
        assert 'patterns' in insights
        assert 'tips' in insights
        assert isinstance(insights['patterns'], list)
        assert isinstance(insights['tips'], list)
        assert isinstance(insights['predictability'], float)


class TestExtractHidingFeatures:
    """Tests for extract_hiding_features function."""

    def test_extract_hiding_features_no_stats(self, temp_config_dir):
        """Test feature extraction when player has no hiding stats."""
        from ai.features import extract_hiding_features

        player = Player(1, "Alice")
        # Remove hiding_stats if it exists (for players without escape attempts)
        if hasattr(player, 'hiding_stats'):
            delattr(player, 'hiding_stats')

        features = extract_hiding_features(player)

        assert features['hide_vs_run_ratio'] == 0.5
        assert features['hide_success_rate'] == 0.0
        assert features['run_success_rate'] == 0.0
        assert features['total_escape_attempts'] == 0
        assert features['predictability_when_caught'] == 0.5

    def test_extract_hiding_features_with_stats(self, temp_config_dir):
        """Test feature extraction with hiding statistics."""
        from ai.features import extract_hiding_features

        player = Player(1, "Alice")
        # Set up hiding stats
        player.hiding_stats = {
            'total_hide_attempts': 5,
            'successful_hides': 3,
            'total_run_attempts': 3,
            'successful_runs': 2,
            'favorite_escape_options': {'spot_a': 3, 'spot_b': 2},
            'hide_vs_run_ratio': 0.625
        }

        features = extract_hiding_features(player)

        assert features['hide_vs_run_ratio'] == 5 / 8  # 5 hides, 3 runs
        assert features['hide_success_rate'] == 3 / 5  # 3/5 successful hides
        assert features['run_success_rate'] == 2 / 3  # 2/3 successful runs
        assert features['total_escape_attempts'] == 8
        assert 0.0 <= features['predictability_when_caught'] <= 1.0

    def test_extract_hiding_features_hide_preference(self, temp_config_dir):
        """Test feature extraction with strong hide preference."""
        from ai.features import extract_hiding_features

        player = Player(1, "Alice")
        # Set up hiding stats with strong hide preference
        player.hiding_stats = {
            'total_hide_attempts': 8,
            'successful_hides': 6,
            'total_run_attempts': 2,
            'successful_runs': 1,
            'favorite_escape_options': {'spot_a': 6, 'spot_b': 2},
            'hide_vs_run_ratio': 0.8
        }

        features = extract_hiding_features(player)

        assert features['hide_vs_run_ratio'] == 0.8  # 8/10


class TestCalculateHidePredictability:
    """Tests for calculate_hide_predictability function."""

    def test_hide_predictability_no_stats(self, temp_config_dir):
        """Test predictability when player has no hiding stats."""
        from ai.features import calculate_hide_predictability

        player = Player(1, "Alice")
        if hasattr(player, 'hiding_stats'):
            delattr(player, 'hiding_stats')

        pred = calculate_hide_predictability(player)
        assert pred == 0.5  # Default moderate predictability

    def test_hide_predictability_consistent_spots(self, temp_config_dir):
        """Test high predictability when player uses same spots."""
        from ai.features import calculate_hide_predictability

        player = Player(1, "Alice")
        # Set up hiding stats with consistent spot usage
        player.hiding_stats = {
            'total_hide_attempts': 10,
            'successful_hides': 5,
            'total_run_attempts': 2,
            'successful_runs': 1,
            'favorite_escape_options': {'spot_a': 10},  # Always same spot
            'hide_vs_run_ratio': 0.83
        }

        pred = calculate_hide_predictability(player)
        # Should be highly predictable
        assert pred > 0.6

    def test_hide_predictability_varied_spots(self, temp_config_dir):
        """Test lower predictability with varied hiding spots."""
        from ai.features import calculate_hide_predictability

        player = Player(1, "Alice")
        # Set up hiding stats with varied spot usage
        player.hiding_stats = {
            'total_hide_attempts': 10,
            'successful_hides': 5,
            'total_run_attempts': 10,  # Equal hide/run
            'successful_runs': 5,
            'favorite_escape_options': {'spot_a': 3, 'spot_b': 3, 'spot_c': 2, 'spot_d': 2},
            'hide_vs_run_ratio': 0.5
        }

        pred = calculate_hide_predictability(player)
        # Should be less predictable
        assert pred < 0.6

    def test_hide_predictability_few_attempts(self, temp_config_dir):
        """Test predictability with very few attempts."""
        from ai.features import calculate_hide_predictability

        player = Player(1, "Alice")
        # Set up hiding stats with few attempts
        player.hiding_stats = {
            'total_hide_attempts': 1,
            'successful_hides': 1,
            'total_run_attempts': 1,
            'successful_runs': 1,
            'favorite_escape_options': {'spot_a': 1},
            'hide_vs_run_ratio': 0.5
        }

        pred = calculate_hide_predictability(player)
        # Should be in valid range
        assert 0.0 <= pred <= 1.0

    def test_hide_predictability_no_favorite_spots(self, temp_config_dir):
        """Test predictability with empty favorite spots."""
        from ai.features import calculate_hide_predictability

        player = Player(1, "Alice")
        player.hiding_stats = {
            'total_hide_attempts': 5,
            'successful_hides': 3,
            'total_run_attempts': 5,
            'successful_runs': 3,
            'favorite_escape_options': {},  # Empty spots dict
            'hide_vs_run_ratio': 0.5
        }

        pred = calculate_hide_predictability(player)
        # Should handle empty spots gracefully
        assert 0.0 <= pred <= 1.0


class TestGenerateInsightsWithHiding:
    """Tests for generate_insights with hiding stats."""

    def test_insights_escape_master(self, temp_config_dir):
        """Test detection of escape master pattern."""
        player = Player(1, "Alice")

        # Add some regular history
        loc = Location("Test", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        # Set up great escape stats
        player.hide_run_history = [
            {'escaped': True}, {'escaped': True}, {'escaped': True},
            {'escaped': True}, {'escaped': True}
        ]
        player.hiding_stats = {
            'total_hide_attempts': 3,
            'successful_hides': 3,
            'total_run_attempts': 2,
            'successful_runs': 2,
            'favorite_escape_options': {'spot_a': 2, 'spot_b': 1},
            'hide_vs_run_ratio': 0.6
        }

        insights = generate_insights(player, num_locations=5)

        # Should detect escape master
        assert any("Escape master" in p for p in insights['patterns'])

    def test_insights_caught_often(self, temp_config_dir):
        """Test detection of frequently caught pattern."""
        player = Player(1, "Alice")

        # Add some regular history
        loc = Location("Test", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        # Set up poor escape stats
        player.hide_run_history = [
            {'escaped': False}, {'escaped': False}, {'escaped': False},
            {'escaped': True}, {'escaped': False}
        ]
        player.hiding_stats = {
            'total_hide_attempts': 3,
            'successful_hides': 0,
            'total_run_attempts': 2,
            'successful_runs': 1,
            'favorite_escape_options': {'spot_a': 2, 'spot_b': 1},
            'hide_vs_run_ratio': 0.6
        }

        insights = generate_insights(player, num_locations=5)

        # Should detect caught often
        assert any("Caught often" in p for p in insights['patterns'])

    def test_insights_hide_preference(self, temp_config_dir):
        """Test detection of hide preference pattern."""
        player = Player(1, "Alice")

        # Add some regular history
        loc = Location("Test", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        # Set up strong hide preference
        player.hide_run_history = [
            {'escaped': True}, {'escaped': True}, {'escaped': True},
            {'escaped': True}, {'escaped': True}
        ]
        player.hiding_stats = {
            'total_hide_attempts': 8,
            'successful_hides': 6,
            'total_run_attempts': 2,
            'successful_runs': 1,
            'favorite_escape_options': {'spot_a': 5, 'spot_b': 3},
            'hide_vs_run_ratio': 0.8
        }

        insights = generate_insights(player, num_locations=5)

        # Should detect hide preference
        assert any("Hide preference" in p for p in insights['patterns'])

    def test_insights_runner(self, temp_config_dir):
        """Test detection of runner pattern."""
        player = Player(1, "Alice")

        # Add some regular history
        loc = Location("Test", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        # Set up strong run preference
        player.hide_run_history = [
            {'escaped': True}, {'escaped': True}, {'escaped': True},
            {'escaped': True}, {'escaped': True}
        ]
        player.hiding_stats = {
            'total_hide_attempts': 2,
            'successful_hides': 1,
            'total_run_attempts': 8,
            'successful_runs': 6,
            'favorite_escape_options': {'spot_a': 1, 'spot_b': 1},
            'hide_vs_run_ratio': 0.2
        }

        insights = generate_insights(player, num_locations=5)

        # Should detect runner pattern
        assert any("Runner" in p for p in insights['patterns'])

    def test_insights_favorite_hiding_spot(self, temp_config_dir):
        """Test detection of favorite hiding spot pattern."""
        player = Player(1, "Alice")

        # Add some regular history
        loc = Location("Test", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        # Set up stats with clear favorite spot
        player.hide_run_history = [
            {'escaped': True}, {'escaped': True}, {'escaped': True}
        ]
        player.hiding_stats = {
            'total_hide_attempts': 5,
            'successful_hides': 3,
            'total_run_attempts': 2,
            'successful_runs': 1,
            'favorite_escape_options': {'behind_boxes': 4, 'freezer': 1},
            'hide_vs_run_ratio': 0.7
        }

        insights = generate_insights(player, num_locations=5)

        # Should detect favorite hiding spot
        assert any("Favorite hiding spot" in p for p in insights['patterns'])
