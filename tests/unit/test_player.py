"""Unit tests for game/player.py - Player class."""
import pytest
from game.player import Player, PLAYER_COLORS
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
        assert player.choice_history == []
        assert player.round_history == []
        assert player.passive_manager is not None

    def test_player_initialization_with_different_id(self, temp_config_dir):
        """Test player initialization with custom ID."""
        player = Player(42, "Bob")

        assert player.id == 42
        assert player.name == "Bob"

    def test_player_initialization_with_profile_id(self, temp_config_dir):
        """Test player initialization with profile ID."""
        player = Player(1, "Alice", profile_id="profile_123")

        assert player.profile_id == "profile_123"

    def test_player_initialization_guest(self, temp_config_dir):
        """Test player without profile ID (guest)."""
        player = Player(1, "Alice")

        assert player.profile_id is None

    def test_player_string_representation(self, temp_config_dir):
        """Test __str__ method."""
        player = Player(1, "Alice")
        player.points = 50

        assert "Alice" in str(player)
        assert "50" in str(player)

    def test_player_color_assignment(self, temp_config_dir):
        """Test players get assigned colors."""
        player = Player(0, "Alice")

        assert player.color is not None
        assert player.color in PLAYER_COLORS

    def test_player_colors_cycle(self, temp_config_dir):
        """Test player colors cycle based on ID."""
        player1 = Player(0, "Alice")
        player2 = Player(1, "Bob")
        player3 = Player(8, "Charlie")  # Same as player 0 due to modulo

        assert player1.color == PLAYER_COLORS[0]
        assert player2.color == PLAYER_COLORS[1]
        assert player3.color == PLAYER_COLORS[0]  # 8 % 8 = 0


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


class TestPassiveManagement:
    """Tests for passive ability management."""

    def test_has_passive_false(self, temp_config_dir):
        """Test has_passive returns False when passive is not owned."""
        from game.passives import PassiveType

        player = Player(1, "Alice")
        assert player.has_passive(PassiveType.AI_WHISPERER) is False

    def test_has_passive_true(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test has_passive returns True when passive is owned."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        from game import config_loader
        new_config = ConfigLoader()
        monkeypatch.setattr(config_loader, 'config', new_config)

        player = Player(1, "Alice")
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            player.passive_manager.add_passive(passive)
            assert player.has_passive(PassiveType.AI_WHISPERER) is True

    def test_get_passives_empty(self, temp_config_dir):
        """Test get_passives returns empty list when no passives owned."""
        player = Player(1, "Alice")
        passives = player.get_passives()
        assert isinstance(passives, list)
        assert len(passives) == 0

    def test_get_passives_with_passive(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test get_passives returns list of owned passives."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        from game import config_loader
        new_config = ConfigLoader()
        monkeypatch.setattr(config_loader, 'config', new_config)

        player = Player(1, "Alice")
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            player.passive_manager.add_passive(passive)
            passives = player.get_passives()
            assert len(passives) == 1

    def test_buy_passive_success(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test successful passive purchase."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        from game import config_loader
        new_config = ConfigLoader()
        monkeypatch.setattr(config_loader, 'config', new_config)

        player = Player(1, "Alice")
        player.points = 50

        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            result = player.buy_passive(passive)
            assert result is True
            assert player.has_passive(PassiveType.AI_WHISPERER)
            assert player.points == 50 - passive.cost

    def test_buy_passive_insufficient_points(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test passive purchase fails with insufficient points."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        from game import config_loader
        new_config = ConfigLoader()
        monkeypatch.setattr(config_loader, 'config', new_config)

        player = Player(1, "Alice")
        player.points = 5  # Not enough for any passive

        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            result = player.buy_passive(passive)
            assert result is False
            assert not player.has_passive(PassiveType.AI_WHISPERER)
            assert player.points == 5

    def test_buy_passive_already_owned(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test passive purchase fails if already owned."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        from game import config_loader
        new_config = ConfigLoader()
        monkeypatch.setattr(config_loader, 'config', new_config)

        player = Player(1, "Alice")
        player.points = 100

        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            player.buy_passive(passive)
            initial_points = player.points

            # Try to buy again
            result = player.buy_passive(passive)
            assert result is False
            assert player.points == initial_points  # Points unchanged


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


class TestEscapeTracking:
    """Tests for escape attempt tracking."""

    def test_record_escape_attempt_hide(self, temp_config_dir):
        """Test recording a hide escape attempt."""
        player = Player(1, "Alice")

        escape_result = {
            'escaped': True,
            'choice_type': 'hide',
            'player_choice_id': 'store_stockroom',
            'player_choice_name': 'Behind Boxes',
            'ai_prediction_id': 'store_freezer',
            'ai_was_correct': False,
            'points_awarded': 0
        }

        player.record_escape_attempt(escape_result, round_num=1)

        assert len(player.hide_run_history) == 1
        assert player.hiding_stats['total_escape_attempts'] == 1
        assert player.hiding_stats['successful_escapes'] == 1
        assert player.hiding_stats['total_hide_attempts'] == 1
        assert player.hiding_stats['successful_hides'] == 1

    def test_record_escape_attempt_run(self, temp_config_dir):
        """Test recording a run escape attempt."""
        player = Player(1, "Alice")

        escape_result = {
            'escaped': True,
            'choice_type': 'run',
            'player_choice_id': 'store_backdoor',
            'player_choice_name': 'Back Exit',
            'ai_prediction_id': 'store_window',
            'ai_was_correct': False,
            'points_awarded': 16
        }

        player.record_escape_attempt(escape_result, round_num=1)

        assert player.hiding_stats['total_run_attempts'] == 1
        assert player.hiding_stats['successful_runs'] == 1

    def test_record_escape_attempt_caught(self, temp_config_dir):
        """Test recording a failed escape attempt."""
        player = Player(1, "Alice")

        escape_result = {
            'escaped': False,
            'choice_type': 'hide',
            'player_choice_id': 'store_stockroom',
            'ai_prediction_id': 'store_stockroom',
            'ai_was_correct': True,
            'points_awarded': 0
        }

        player.record_escape_attempt(escape_result, round_num=1)

        assert player.hiding_stats['total_escape_attempts'] == 1
        assert player.hiding_stats['successful_escapes'] == 0
        assert player.hiding_stats['total_hide_attempts'] == 1
        assert player.hiding_stats['successful_hides'] == 0

    def test_escape_option_history_tracking(self, temp_config_dir):
        """Test escape option history is tracked."""
        player = Player(1, "Alice")

        escape_result = {
            'escaped': True,
            'choice_type': 'hide',
            'player_choice_id': 'store_stockroom',
            'points_awarded': 0
        }

        player.record_escape_attempt(escape_result, round_num=1)

        assert 'store_stockroom' in player.escape_option_history

    def test_favorite_escape_options_tracking(self, temp_config_dir):
        """Test favorite escape options are tracked."""
        player = Player(1, "Alice")

        # Record same option multiple times
        for i in range(3):
            escape_result = {
                'escaped': True,
                'choice_type': 'hide',
                'player_choice_id': 'store_stockroom',
                'points_awarded': 0
            }
            player.record_escape_attempt(escape_result, round_num=i+1)

        assert player.hiding_stats['favorite_escape_options']['store_stockroom'] == 3

    def test_hide_vs_run_ratio(self, temp_config_dir):
        """Test hide vs run ratio calculation."""
        player = Player(1, "Alice")

        # Record 2 hide attempts
        for i in range(2):
            player.record_escape_attempt({
                'escaped': True,
                'choice_type': 'hide',
                'player_choice_id': f'hide_{i}',
                'points_awarded': 0
            }, round_num=i+1)

        # Record 2 run attempts
        for i in range(2):
            player.record_escape_attempt({
                'escaped': True,
                'choice_type': 'run',
                'player_choice_id': f'run_{i}',
                'points_awarded': 10
            }, round_num=i+3)

        # 2 hide / 4 total = 0.5
        assert player.hiding_stats['hide_vs_run_ratio'] == 0.5


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
        loc = Location("Test", "T", 15, 25)

        # Add high-value choices
        for i in range(4):
            player.record_choice(loc, round_num=i+1, caught=False,
                               points_earned=20, location_value=20)

        # Add one low-value choice
        low_loc = Location("Low", "L", 5, 10)
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


class TestPlayerElimination:
    """Tests for player elimination state."""

    def test_player_eliminated(self, temp_config_dir):
        """Test player can be eliminated."""
        player = Player(1, "Alice")
        assert player.alive is True

        player.alive = False
        assert player.alive is False

    def test_eliminated_player_still_has_points(self, temp_config_dir):
        """Test eliminated player retains their points."""
        player = Player(1, "Alice")
        player.points = 50
        player.alive = False

        assert player.points == 50
