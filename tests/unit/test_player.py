"""Unit tests for game/player.py - Player class."""
import pytest
from game.player import Player
from game.items import ItemShop, ItemType
from game.locations import Location


class TestPlayerInitialization:
    """Tests for Player initialization."""

    def test_player_initialization(self, temp_config_dir):
        """Test player is initialized with correct default values."""
        player = Player(1, "Alice")

        assert player.id == 1
        assert player.name == "Alice"
        assert player.points == 0
        assert player.alive is True
        assert player.items == []
        assert player.choice_history == []
        assert player.round_history == []

    def test_player_initialization_with_different_id(self, temp_config_dir):
        """Test player initialization with custom ID."""
        player = Player(42, "Bob")

        assert player.id == 42
        assert player.name == "Bob"

    def test_player_string_representation(self, temp_config_dir):
        """Test __str__ method."""
        player = Player(1, "Alice")
        player.points = 50

        assert "Alice" in str(player)
        assert "50" in str(player)

    def test_player_string_with_items(self, temp_config_dir, sample_items):
        """Test __str__ includes active items."""
        player = Player(1, "Alice")
        player.items.append(sample_items['scout'])

        player_str = str(player)
        assert "Alice" in player_str
        assert "Scout" in player_str


class TestPointManagement:
    """Tests for point management methods."""

    def test_add_points_basic(self, temp_config_dir):
        """Test basic point addition."""
        player = Player(1, "Alice")

        player.add_points(25)
        assert player.points == 25

        player.add_points(10)
        assert player.points == 35

    def test_add_points_zero(self, temp_config_dir):
        """Test adding zero points."""
        player = Player(1, "Alice")
        player.add_points(0)
        assert player.points == 0

    def test_add_points_large_amount(self, temp_config_dir):
        """Test adding large point values."""
        player = Player(1, "Alice")
        player.add_points(1000)
        assert player.points == 1000

    def test_add_points_accumulation(self, temp_config_dir):
        """Test multiple point additions accumulate correctly."""
        player = Player(1, "Alice")

        for i in range(10):
            player.add_points(10)

        assert player.points == 100

    @pytest.mark.parametrize("points", [0, 1, 5, 10, 50, 100, 999])
    def test_add_points_various_amounts(self, points, temp_config_dir):
        """Test adding various point amounts."""
        player = Player(1, "Alice")
        player.add_points(points)
        assert player.points == points


class TestItemManagement:
    """Tests for item management methods."""

    def test_buy_item_success(self, temp_config_dir, sample_items):
        """Test successful item purchase."""
        player = Player(1, "Alice")
        player.points = 20

        scout = sample_items['scout']
        result = player.buy_item(scout)

        assert result is True
        assert player.points == 14  # 20 - 6
        assert len(player.items) == 1
        assert player.items[0].type == ItemType.SCOUT

    def test_buy_item_insufficient_points(self, temp_config_dir, sample_items):
        """Test item purchase fails with insufficient points."""
        player = Player(1, "Alice")
        player.points = 5

        intel = sample_items['intel_report']
        result = player.buy_item(intel)

        assert result is False
        assert player.points == 5  # Unchanged
        assert len(player.items) == 0

    def test_buy_item_exact_cost(self, temp_config_dir, sample_items):
        """Test purchase with exact point amount."""
        player = Player(1, "Alice")
        player.points = 6

        scout = sample_items['scout']
        result = player.buy_item(scout)

        assert result is True
        assert player.points == 0

    def test_has_item_true(self, temp_config_dir, sample_items):
        """Test has_item returns True when item exists."""
        player = Player(1, "Alice")
        player.items.append(sample_items['scout'])

        assert player.has_item(ItemType.SCOUT) is True

    def test_has_item_false(self, temp_config_dir):
        """Test has_item returns False when item doesn't exist."""
        player = Player(1, "Alice")
        assert player.has_item(ItemType.SCOUT) is False

    def test_has_item_consumed(self, temp_config_dir, sample_items):
        """Test has_item returns False for consumed items."""
        player = Player(1, "Alice")
        scout = sample_items['scout']
        scout.consumed = True
        player.items.append(scout)

        assert player.has_item(ItemType.SCOUT) is False

    def test_use_item_success(self, temp_config_dir, sample_items):
        """Test using an item marks it as consumed."""
        player = Player(1, "Alice")
        player.items.append(sample_items['scout'])

        result = player.use_item(ItemType.SCOUT)

        assert result is not None
        assert result.consumed is True
        assert player.has_item(ItemType.SCOUT) is False

    def test_use_item_not_found(self, temp_config_dir):
        """Test using non-existent item returns None."""
        player = Player(1, "Alice")
        result = player.use_item(ItemType.SCOUT)
        assert result is None

    def test_get_item_exists(self, temp_config_dir, sample_items):
        """Test get_item returns item when it exists."""
        player = Player(1, "Alice")
        player.items.append(sample_items['scout'])

        item = player.get_item(ItemType.SCOUT)

        assert item is not None
        assert item.type == ItemType.SCOUT

    def test_get_item_not_found(self, temp_config_dir):
        """Test get_item returns None when item doesn't exist."""
        player = Player(1, "Alice")
        item = player.get_item(ItemType.SCOUT)
        assert item is None

    def test_get_active_items(self, temp_config_dir, sample_items):
        """Test get_active_items filters consumed items."""
        player = Player(1, "Alice")

        # Add active and consumed items
        scout = sample_items['scout']
        scout.consumed = True
        player.items.append(scout)
        player.items.append(sample_items['intel_report'])

        active = player.get_active_items()

        assert len(active) == 1
        assert active[0].type == ItemType.INTEL_REPORT


class TestChoiceRecording:
    """Tests for choice recording and history tracking."""

    def test_record_choice_basic(self, temp_config_dir, sample_location_manager):
        """Test basic choice recording."""
        player = Player(1, "Alice")
        loc = sample_location_manager.get_location(0)

        player.record_choice(loc, round_num=1, caught=False, points_earned=10)

        assert len(player.choice_history) == 1
        assert player.choice_history[0] == loc.name
        assert len(player.round_history) == 1
        assert player.round_history[0]['location'] == loc.name
        assert player.round_history[0]['round'] == 1

    def test_record_choice_caught(self, temp_config_dir, sample_location_manager):
        """Test recording when player is caught."""
        player = Player(1, "Alice")
        loc = sample_location_manager.get_location(0)

        player.record_choice(loc, round_num=1, caught=True, points_earned=0)

        assert player.round_history[0]['caught'] is True
        assert player.round_history[0]['points_earned'] == 0

    def test_record_choice_with_location_value(self, temp_config_dir, sample_location_manager):
        """Test recording with explicit location_value."""
        player = Player(1, "Alice")
        loc = sample_location_manager.get_location(0)

        player.record_choice(loc, round_num=1, caught=False,
                           points_earned=23, location_value=20)

        assert player.round_history[0]['location_value'] == 20
        assert player.round_history[0]['points_earned'] == 23

    def test_record_choice_history_accumulation(self, temp_config_dir, sample_location_manager):
        """Test multiple rounds accumulate in history."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        for i in range(5):
            loc = loc_manager.get_location(i % 3)
            player.record_choice(loc, round_num=i+1, caught=False, points_earned=10)

        assert len(player.choice_history) == 5
        assert len(player.round_history) == 5


class TestBehaviorSummary:
    """Tests for behavior summary calculations."""

    def test_behavior_summary_no_history(self, temp_config_dir):
        """Test behavior summary with no history returns zeros."""
        player = Player(1, "Alice")
        summary = player.get_behavior_summary()

        assert summary['avg_location_value'] == 0
        assert summary['choice_variety'] == 0
        assert summary['high_value_preference'] == 0

    def test_behavior_summary_with_history(self, temp_config_dir, sample_location_manager):
        """Test behavior summary calculates correctly with history."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Record 3 choices
        for i in range(3):
            loc = loc_manager.get_location(0)
            player.record_choice(loc, round_num=i+1, caught=False,
                               points_earned=10, location_value=10)

        summary = player.get_behavior_summary()

        assert summary['avg_location_value'] == 10
        assert summary['total_choices'] == 3
        assert 'location_frequencies' in summary

    def test_behavior_summary_high_value_preference(self, temp_config_dir):
        """Test high_value_preference calculation (15+ points)."""
        player = Player(1, "Alice")
        loc = Location("Test", "🏪", 15, 25)

        # Add high-value choices
        for i in range(4):
            player.record_choice(loc, round_num=i+1, caught=False,
                               points_earned=20, location_value=20)

        # Add one low-value choice
        low_loc = Location("Low", "🏪", 5, 10)
        player.record_choice(low_loc, round_num=5, caught=False,
                           points_earned=7, location_value=7)

        summary = player.get_behavior_summary()

        # 4 out of 5 are high value (15+)
        assert summary['high_value_preference'] == 0.8

    def test_behavior_summary_variety_calculation(self, temp_config_dir, sample_location_manager):
        """Test choice_variety calculation."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        # Use all 3 test locations
        for i in range(3):
            loc = loc_manager.get_location(i)
            player.record_choice(loc, round_num=i+1, caught=False, points_earned=10)

        summary = player.get_behavior_summary()

        # 3 unique locations / 8 total = 0.375
        assert summary['choice_variety'] == pytest.approx(0.375, abs=0.01)

    def test_behavior_summary_location_frequencies(self, temp_config_dir, sample_location_manager):
        """Test location frequency tracking."""
        player = Player(1, "Alice")
        loc_manager = sample_location_manager

        loc1 = loc_manager.get_location(0)
        loc2 = loc_manager.get_location(1)

        # Record multiple choices
        player.record_choice(loc1, 1, False, 10)
        player.record_choice(loc1, 2, False, 10)
        player.record_choice(loc2, 3, False, 10)

        summary = player.get_behavior_summary()

        assert summary['location_frequencies'][loc1.name] == 2
        assert summary['location_frequencies'][loc2.name] == 1
