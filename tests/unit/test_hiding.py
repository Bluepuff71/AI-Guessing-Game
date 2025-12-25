"""Tests for game.hiding module."""
import pytest
from game.hiding import HidingManager


class TestHidingManagerInit:
    """Tests for HidingManager initialization."""

    def test_initialization_with_config(self, sample_hiding_manager):
        """Test HidingManager initializes correctly with config."""
        assert sample_hiding_manager is not None
        assert sample_hiding_manager.mechanics_config is not None
        assert sample_hiding_manager.escape_options is not None

    def test_initialization_defaults_without_config(self, monkeypatch):
        """Test HidingManager uses defaults when config not available."""
        from game.config_loader import ConfigLoader, config

        # Mock config to return None for hiding mechanics
        def mock_get_hiding_mechanics():
            return None

        def mock_get_escape_options():
            return {}

        monkeypatch.setattr(config, 'get_hiding_mechanics', mock_get_hiding_mechanics)
        monkeypatch.setattr(config, 'get_escape_options', mock_get_escape_options)

        manager = HidingManager()
        assert manager.mechanics_config == {'run_point_retention': 0.8}


class TestEscapeOptions:
    """Tests for escape options retrieval."""

    def test_get_escape_options_for_valid_location(self, sample_hiding_manager):
        """Test getting escape options for valid location."""
        options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        assert len(options) == 4
        assert any(opt['id'] == 'store_stockroom' for opt in options)
        assert any(opt['id'] == 'store_backdoor' for opt in options)

    def test_get_escape_options_for_invalid_location(self, sample_hiding_manager):
        """Test getting escape options for invalid location returns empty list."""
        options = sample_hiding_manager.get_escape_options_for_location("Nonexistent Location")
        assert options == []

    def test_get_hiding_spots_only(self, sample_hiding_manager):
        """Test getting only hiding spots (type='hide')."""
        spots = sample_hiding_manager.get_hiding_spots_for_location("Test Store")
        assert len(spots) == 2
        assert all(opt.get('type', 'hide') == 'hide' for opt in spots)
        assert any(opt['id'] == 'store_stockroom' for opt in spots)
        assert any(opt['id'] == 'store_freezer' for opt in spots)

    def test_get_escape_routes_only(self, sample_hiding_manager):
        """Test getting only escape routes (type='run')."""
        routes = sample_hiding_manager.get_escape_routes_for_location("Test Store")
        assert len(routes) == 2
        assert all(opt.get('type') == 'run' for opt in routes)
        assert any(opt['id'] == 'store_backdoor' for opt in routes)
        assert any(opt['id'] == 'store_window' for opt in routes)

    def test_get_escape_options_different_locations(self, sample_hiding_manager):
        """Test escape options differ by location."""
        store_options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        vault_options = sample_hiding_manager.get_escape_options_for_location("Test Vault")

        assert len(store_options) == 4
        assert len(vault_options) == 2
        assert store_options != vault_options


class TestEscapeResolution:
    """Tests for escape attempt resolution."""

    def test_resolve_escape_player_outsmarts_ai_hide(self, sample_hiding_manager):
        """Test escape resolution when player outsmarts AI with hide."""
        player_choice = {
            'id': 'store_stockroom',
            'name': 'Behind Boxes',
            'type': 'hide'
        }
        ai_prediction = 'store_freezer'  # AI predicted wrong
        location_points = 20

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 16  # 80% of 20 points
        assert result['player_choice_id'] == 'store_stockroom'
        assert result['ai_prediction_id'] == 'store_freezer'
        assert result['choice_type'] == 'hide'
        assert result['ai_was_correct'] is False

    def test_resolve_escape_player_outsmarts_ai_run(self, sample_hiding_manager):
        """Test escape resolution when player outsmarts AI with run."""
        player_choice = {
            'id': 'store_backdoor',
            'name': 'Back Exit',
            'type': 'run'
        }
        ai_prediction = 'store_window'  # AI predicted wrong
        location_points = 20

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 16  # 80% of 20
        assert result['choice_type'] == 'run'
        assert result['ai_was_correct'] is False

    def test_resolve_escape_ai_predicts_correctly(self, sample_hiding_manager):
        """Test escape resolution when AI predicts correctly."""
        player_choice = {
            'id': 'store_stockroom',
            'name': 'Behind Boxes',
            'type': 'hide'
        }
        ai_prediction = 'store_stockroom'  # AI predicted correctly
        location_points = 20

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is False
        assert result['points_awarded'] == 0  # Caught, no points
        assert result['ai_was_correct'] is True

    def test_resolve_escape_run_points_calculation(self, sample_hiding_manager):
        """Test run points calculation with different point values."""
        player_choice = {
            'id': 'store_backdoor',
            'name': 'Back Exit',
            'type': 'run'
        }
        ai_prediction = 'store_window'

        # Test with 100 points
        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, 100
        )
        assert result['points_awarded'] == 80  # 80% of 100

        # Test with 25 points
        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, 25
        )
        assert result['points_awarded'] == 20  # 80% of 25 = 20

    def test_resolve_escape_hide_points(self, sample_hiding_manager):
        """Test hiding gives 80% points when escaped (same as running)."""
        player_choice = {
            'id': 'store_stockroom',
            'name': 'Behind Boxes',
            'type': 'hide'
        }
        ai_prediction = 'store_backdoor'  # AI predicted wrong
        location_points = 100

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 80  # 80% of 100 points

    def test_resolve_escape_includes_location_points(self, sample_hiding_manager):
        """Test result includes original location points."""
        player_choice = {
            'id': 'store_stockroom',
            'name': 'Behind Boxes',
            'type': 'hide'
        }
        ai_prediction = 'store_freezer'
        location_points = 50

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['location_points'] == 50


class TestUtilities:
    """Tests for utility methods."""

    def test_get_run_point_retention(self, sample_hiding_manager):
        """Test getting run point retention from config."""
        retention = sample_hiding_manager.get_run_point_retention()
        assert retention == 0.8

    def test_get_option_by_id_exists(self, sample_hiding_manager):
        """Test getting escape option by ID when it exists."""
        option = sample_hiding_manager.get_option_by_id("Test Store", "store_stockroom")
        assert option is not None
        assert option['id'] == 'store_stockroom'
        assert option['name'] == 'Behind Boxes'
        assert option['type'] == 'hide'

    def test_get_option_by_id_not_found(self, sample_hiding_manager):
        """Test getting escape option by ID when not found."""
        option = sample_hiding_manager.get_option_by_id("Test Store", "nonexistent_id")
        assert option == {}

    def test_get_option_by_id_wrong_location(self, sample_hiding_manager):
        """Test getting escape option from wrong location."""
        option = sample_hiding_manager.get_option_by_id("Test Vault", "store_stockroom")
        assert option == {}


class TestDefaultType:
    """Tests for default type handling."""

    def test_option_default_type_is_hide(self, sample_hiding_manager):
        """Test that options without explicit type default to 'hide'."""
        spots = sample_hiding_manager.get_hiding_spots_for_location("Test Store")
        # Our test config explicitly sets types, but the code handles defaults
        for spot in spots:
            opt_type = spot.get('type', 'hide')
            assert opt_type == 'hide'


class TestOptionKeepAmount:
    """Tests for per-option keep_amount functionality."""

    def test_get_option_keep_amount_explicit(self, sample_hiding_manager):
        """Test getting keep_amount when explicitly set on option."""
        option = {
            'id': 'test_option',
            'name': 'Test',
            'type': 'hide',
            'keep_amount': 0.9
        }
        assert sample_hiding_manager.get_option_keep_amount(option) == 0.9

    def test_get_option_keep_amount_fallback(self, sample_hiding_manager):
        """Test fallback to global retention when keep_amount not set."""
        option = {
            'id': 'test_option',
            'name': 'Test',
            'type': 'hide'
        }
        assert sample_hiding_manager.get_option_keep_amount(option) == 0.8

    def test_get_option_keep_amount_zero(self, sample_hiding_manager):
        """Test keep_amount of zero is respected."""
        option = {
            'id': 'test_option',
            'name': 'Test',
            'type': 'hide',
            'keep_amount': 0.0
        }
        assert sample_hiding_manager.get_option_keep_amount(option) == 0.0

    def test_get_option_keep_amount_full(self, sample_hiding_manager):
        """Test keep_amount of 1.0 (100%) is respected."""
        option = {
            'id': 'test_option',
            'name': 'Test',
            'type': 'run',
            'keep_amount': 1.0
        }
        assert sample_hiding_manager.get_option_keep_amount(option) == 1.0

    def test_resolve_escape_with_custom_keep_amount(self, sample_hiding_manager):
        """Test escape resolution uses option-specific keep_amount."""
        player_choice = {
            'id': 'custom_spot',
            'name': 'Custom Spot',
            'type': 'hide',
            'keep_amount': 0.9
        }
        ai_prediction = 'other_spot'
        location_points = 100

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 90  # 90% of 100

    def test_resolve_escape_with_low_keep_amount(self, sample_hiding_manager):
        """Test escape with lower keep_amount gives fewer points."""
        player_choice = {
            'id': 'risky_spot',
            'name': 'Risky Spot',
            'type': 'run',
            'keep_amount': 0.6
        }
        ai_prediction = 'other_spot'
        location_points = 100

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 60  # 60% of 100

    def test_resolve_escape_default_keep_amount(self, sample_hiding_manager):
        """Test escape resolution falls back to default when no keep_amount."""
        player_choice = {
            'id': 'default_spot',
            'name': 'Default Spot',
            'type': 'hide'
        }
        ai_prediction = 'other_spot'
        location_points = 100

        result = sample_hiding_manager.resolve_escape_attempt(
            player_choice, ai_prediction, location_points
        )

        assert result['escaped'] is True
        assert result['points_awarded'] == 80  # 80% default
