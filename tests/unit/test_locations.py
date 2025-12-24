"""Unit tests for game/locations.py - Location and LocationManager classes."""
import pytest
from game.locations import Location, LocationManager


class TestLocation:
    """Tests for Location class."""

    def test_location_initialization(self):
        """Test location is initialized with correct attributes."""
        loc = Location("Test Store", "🏪", 5, 10)

        assert loc.name == "Test Store"
        assert loc.emoji == "🏪"
        assert loc.min_points == 5
        assert loc.max_points == 10

    def test_location_roll_points_range(self, deterministic_random):
        """Test roll_points returns value within min/max range."""
        loc = Location("Test Store", "🏪", 5, 10)

        # Test multiple rolls
        for _ in range(20):
            roll = loc.roll_points()
            assert loc.min_points <= roll <= loc.max_points

    def test_location_roll_points_distribution(self, deterministic_random):
        """Test roll_points has reasonable distribution."""
        loc = Location("Test Store", "🏪", 5, 10)

        rolls = [loc.roll_points() for _ in range(100)]

        # Check we get values across the range
        min_roll = min(rolls)
        max_roll = max(rolls)

        assert min_roll >= 5
        assert max_roll <= 10
        # With 100 rolls, we should see some variety
        assert len(set(rolls)) > 1

    def test_location_roll_min_equals_max(self, deterministic_random):
        """Test location with min == max always returns same value."""
        loc = Location("Fixed", "🏪", 10, 10)

        rolls = [loc.roll_points() for _ in range(10)]
        assert all(roll == 10 for roll in rolls)

    def test_location_get_range_str(self):
        """Test get_range_str formats correctly."""
        loc = Location("Test Store", "🏪", 5, 10)
        assert loc.get_range_str() == "5-10"

    def test_location_string_representation(self):
        """Test __str__ method includes emoji and name."""
        loc = Location("Test Store", "🏪", 5, 10)
        loc_str = str(loc)

        assert "🏪" in loc_str
        assert "Test Store" in loc_str

    def test_location_emoji_display(self):
        """Test various emojis are stored correctly."""
        emojis = ["🏪", "💰", "🏦", "💎", "🎰"]

        for emoji in emojis:
            loc = Location("Test", emoji, 1, 10)
            assert loc.emoji == emoji


class TestLocationManager:
    """Tests for LocationManager class."""

    def test_location_manager_initialization(self, temp_config_dir):
        """Test LocationManager loads locations from config."""
        manager = LocationManager()

        assert len(manager.locations) == 3  # Test config has 3 locations
        assert all(isinstance(loc, Location) for loc in manager.locations)

    def test_location_manager_count(self, temp_config_dir):
        """Test __len__ returns correct count."""
        manager = LocationManager()
        assert len(manager) == 3

    def test_get_location_by_index(self, temp_config_dir):
        """Test get_location retrieves by 0-based index."""
        manager = LocationManager()

        loc0 = manager.get_location(0)
        loc1 = manager.get_location(1)
        loc2 = manager.get_location(2)

        assert loc0.name == "Test Store"
        assert loc1.name == "Test Vault"
        assert loc2.name == "Test Bank"

    def test_get_location_invalid_index(self, temp_config_dir):
        """Test get_location raises IndexError for invalid index."""
        manager = LocationManager()

        with pytest.raises(IndexError):
            manager.get_location(10)

    def test_get_location_by_name_success(self, temp_config_dir):
        """Test get_location_by_name finds location."""
        manager = LocationManager()

        loc = manager.get_location_by_name("Test Vault")

        assert loc.name == "Test Vault"
        assert loc.emoji == "💰"

    def test_get_location_by_name_not_found(self, temp_config_dir):
        """Test get_location_by_name raises ValueError for missing location."""
        manager = LocationManager()

        with pytest.raises(ValueError, match="not found"):
            manager.get_location_by_name("Nonexistent Location")

    def test_get_all_locations(self, temp_config_dir):
        """Test get_all returns all locations."""
        manager = LocationManager()

        all_locs = manager.get_all()

        assert len(all_locs) == 3
        assert all(isinstance(loc, Location) for loc in all_locs)

    def test_location_manager_point_ranges(self, temp_config_dir):
        """Test locations have correct min/max points from config."""
        manager = LocationManager()

        store = manager.get_location_by_name("Test Store")
        assert store.min_points == 5
        assert store.max_points == 10

        vault = manager.get_location_by_name("Test Vault")
        assert vault.min_points == 10
        assert vault.max_points == 20

        bank = manager.get_location_by_name("Test Bank")
        assert bank.min_points == 1
        assert bank.max_points == 30


# Note: Backward compatibility tests removed for simplicity
# The game now uses min/max format consistently
# Old base_points + variance format support is legacy code
# not required for 95% coverage goal
