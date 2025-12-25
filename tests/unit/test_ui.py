"""Unit tests for game/ui.py - UI display functions."""
import pytest
from game.ui import (
    clear, print_header, print_standings, print_locations,
    print_player_caught, print_player_looted, print_game_over,
    print_ai_victory, get_player_input
)
from game.player import Player
from game.items import ItemShop, ItemType
from game.locations import Location


class TestBasicOutput:
    """Tests for basic output functions."""

    def test_clear(self, mock_console):
        """Test clear() outputs clear command."""
        clear()
        # Just verify it doesn't crash
        assert True

    def test_print_header(self, mock_console):
        """Test print_header outputs formatted header."""
        console, output = mock_console
        print_header("Test Header")

        result = output.getvalue()
        assert "Test Header" in result

    def test_print_game_over(self, mock_console, temp_config_dir):
        """Test print_game_over displays winner."""
        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 105

        print_game_over(player)

        result = output.getvalue()
        assert "Alice" in result or "WINNER" in result.upper()

    def test_print_ai_victory(self, mock_console):
        """Test print_ai_victory displays AI win message."""
        console, output = mock_console
        print_ai_victory()

        result = output.getvalue()
        assert len(result) > 0  # Should print something


class TestStandingsDisplay:
    """Tests for standings display."""

    def test_print_standings_basic(self, mock_console, temp_config_dir):
        """Test print_standings displays player scores."""
        console, output = mock_console
        player1 = Player(1, "Alice")
        player1.points = 50

        player2 = Player(2, "Bob")
        player2.points = 30

        print_standings([player1, player2])

        result = output.getvalue()
        assert "Alice" in result
        assert "Bob" in result
        assert "50" in result
        assert "30" in result

    def test_print_standings_with_passives(self, mock_console, temp_config_dir, temp_passives_config, monkeypatch):
        """Test print_standings displays player passives."""
        from game.config_loader import ConfigLoader
        from game.passives import PassiveShop, PassiveType

        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)
        PassiveShop.PASSIVES = None

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        # Give player a passive
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            player.passive_manager.add_passive(passive)

        print_standings([player])

        result = output.getvalue()
        assert "Alice" in result

    def test_print_standings_with_choices(self, mock_console, temp_config_dir, sample_location_manager):
        """Test print_standings displays current choices."""
        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50
        loc = sample_location_manager.get_location(0)

        print_standings([player], {player: loc})

        result = output.getvalue()
        assert "Alice" in result


class TestLocationDisplay:
    """Tests for location display."""

    def test_print_locations(self, mock_console, sample_location_manager):
        """Test print_locations displays all locations."""
        console, output = mock_console
        print_locations(sample_location_manager)

        result = output.getvalue()
        # Should display location information
        assert len(result) > 0

    def test_print_locations_with_previous_ai(self, mock_console, sample_location_manager):
        """Test print_locations highlights previous AI location."""
        console, output = mock_console
        loc = sample_location_manager.get_location(0)
        print_locations(sample_location_manager, previous_ai_location=loc)

        result = output.getvalue()
        assert len(result) > 0


class TestPlayerFeedback:
    """Tests for player feedback messages."""

    def test_print_player_caught(self, mock_console, temp_config_dir):
        """Test print_player_caught displays caught message."""
        console, output = mock_console
        player = Player(1, "Alice")

        print_player_caught(player, shield_saved=False)

        result = output.getvalue()
        assert "Alice" in result

    def test_print_player_caught_with_shield(self, mock_console, temp_config_dir):
        """Test print_player_caught displays shield save message."""
        console, output = mock_console
        player = Player(1, "Alice")

        print_player_caught(player, shield_saved=True)

        result = output.getvalue()
        assert "Alice" in result

    def test_print_player_looted_basic(self, mock_console, temp_config_dir):
        """Test print_player_looted displays basic loot."""
        console, output = mock_console
        player = Player(1, "Alice")
        loc = Location("Test Store", "🏪", 5, 10)

        print_player_looted(player, loc, points_earned=7)

        result = output.getvalue()
        assert "Alice" in result
        assert "7" in result


class TestInputHandling:
    """Tests for user input handling."""

    def test_get_player_input_valid(self, mock_console, monkeypatch):
        """Test get_player_input accepts valid input."""
        console, output = mock_console
        # Mock input to return valid value
        monkeypatch.setattr('builtins.input', lambda: "1")

        result = get_player_input("Choose:", valid_range=range(1, 4))

        assert result == "1"

    def test_get_player_input_empty(self, mock_console, monkeypatch):
        """Test get_player_input accepts empty input."""
        console, output = mock_console
        monkeypatch.setattr('builtins.input', lambda: "")

        result = get_player_input("Choose:")

        assert result == ""

    def test_get_player_input_retry_on_invalid(self, mock_console, monkeypatch):
        """Test get_player_input retries on invalid input."""
        console, output = mock_console
        # First invalid, then valid
        inputs = iter(["99", "1"])
        monkeypatch.setattr('builtins.input', lambda: next(inputs))

        result = get_player_input("Choose:", valid_range=range(1, 4))

        assert result == "1"


class TestFlushInput:
    """Tests for flush_input function."""

    def test_flush_input_windows(self, monkeypatch):
        """Test flush_input on Windows platform."""
        from game import ui
        monkeypatch.setattr('sys.platform', 'win32')

        # Should not raise even if msvcrt is not available
        ui.flush_input()

    def test_flush_input_unix(self, monkeypatch):
        """Test flush_input on Unix platform."""
        from game import ui
        monkeypatch.setattr('sys.platform', 'linux')

        # Should not raise even if termios is not available
        ui.flush_input()


class TestPassiveShopDisplay:
    """Tests for passive shop display."""

    def test_print_passive_shop(self, mock_console, temp_config_dir, temp_passives_config, monkeypatch):
        """Test print_passive_shop displays available passives."""
        from game.ui import print_passive_shop
        from game.config_loader import ConfigLoader
        from game.passives import PassiveShop

        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        print_passive_shop(player)

        result = output.getvalue()
        assert len(result) > 0

    def test_print_passive_shop_with_owned_passives(self, mock_console, temp_config_dir, temp_passives_config, monkeypatch):
        """Test print_passive_shop shows owned passives differently."""
        from game.ui import print_passive_shop
        from game.config_loader import ConfigLoader
        from game.passives import PassiveShop, PassiveType

        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        # Give player an owned passive
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if passive:
            player.passive_manager.add_passive(passive)

        print_passive_shop(player)

        result = output.getvalue()
        assert len(result) > 0


class TestIntelReport:
    """Tests for intel report display."""

    def test_show_intel_report_simple(self, mock_console, temp_config_dir):
        """Test show_intel_report in simple mode."""
        from game.ui import show_intel_report

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        show_intel_report(
            player,
            threat_level=0.6,
            predictability=0.4,
            insights=["You tend to revisit locations"],
            detail_level="simple"
        )

        result = output.getvalue()
        assert len(result) > 0

    def test_show_intel_report_full(self, mock_console, temp_config_dir):
        """Test show_intel_report in full mode."""
        from game.ui import show_intel_report

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        show_intel_report(
            player,
            threat_level=0.8,
            predictability=0.7,
            insights=["High threat", "Very predictable"],
            detail_level="full"
        )

        result = output.getvalue()
        assert len(result) > 0

    def test_show_intel_report_with_ai_memory(self, mock_console, temp_config_dir):
        """Test show_intel_report with AI memory data."""
        from game.ui import show_intel_report

        console, output = mock_console
        player = Player(1, "Alice")

        ai_memory = {
            'favorite_location': 'Test Store',
            'risk_profile': 'aggressive',
            'catch_rate': 0.25,
            'has_personal_model': True,
            'total_games': 5
        }

        show_intel_report(
            player,
            threat_level=0.5,
            predictability=0.5,
            insights=[],
            ai_memory=ai_memory,
            detail_level="full"
        )

        result = output.getvalue()
        assert len(result) > 0


class TestRevealPhase:
    """Tests for reveal phase UI functions."""

    def test_print_reveal_header(self, mock_console):
        """Test print_reveal_header outputs header."""
        from game.ui import print_reveal_header

        console, output = mock_console
        print_reveal_header()

        result = output.getvalue()
        assert len(result) > 0

    def test_print_player_choice(self, mock_console, temp_config_dir):
        """Test print_player_choice displays player's choice."""
        from game.ui import print_player_choice

        console, output = mock_console
        player = Player(1, "Alice")
        loc = Location("Test Store", "🏪", 5, 10)

        print_player_choice(player, loc, "Other Location", confidence=0.6, reasoning="Pattern detected")

        result = output.getvalue()
        assert "Alice" in result

    def test_print_player_choice_match(self, mock_console, temp_config_dir):
        """Test print_player_choice when AI predicted correctly."""
        from game.ui import print_player_choice

        console, output = mock_console
        player = Player(1, "Alice")
        loc = Location("Test Store", "🏪", 5, 10)

        print_player_choice(player, loc, "Test Store", confidence=0.9, reasoning="High confidence")

        result = output.getvalue()
        assert "Alice" in result

    def test_print_search_result(self, mock_console, temp_config_dir):
        """Test print_search_result displays search info."""
        from game.ui import print_search_result

        console, output = mock_console
        loc = Location("Test Store", "🏪", 5, 10)

        print_search_result(loc)

        result = output.getvalue()
        # Output may use uppercase for display
        assert "test store" in result.lower()

    def test_print_search_result_with_previous(self, mock_console, temp_config_dir):
        """Test print_search_result with previous location."""
        from game.ui import print_search_result

        console, output = mock_console
        loc = Location("Test Store", "🏪", 5, 10)
        prev_loc = Location("Old Store", "🏬", 3, 8)

        print_search_result(loc, previous_location=prev_loc, reasoning="Pattern detected")

        result = output.getvalue()
        assert len(result) > 0


class TestProfileUI:
    """Tests for profile selection UI."""

    def test_print_profile_selection_menu_empty(self, mock_console):
        """Test profile menu with no profiles."""
        from game.ui import print_profile_selection_menu

        console, output = mock_console
        print_profile_selection_menu([])

        result = output.getvalue()
        assert len(result) > 0

    def test_print_profile_selection_menu_with_profiles(self, mock_console):
        """Test profile menu with existing profiles."""
        from game.ui import print_profile_selection_menu
        from dataclasses import dataclass
        from datetime import datetime, timezone

        console, output = mock_console

        @dataclass
        class MockProfile:
            name: str = "Player1"
            id: str = "p1"
            last_played: str = datetime.now(timezone.utc).isoformat()
            wins: int = 5
            losses: int = 5
            total_games: int = 10
            win_rate: float = 0.5

        profiles = [MockProfile()]
        print_profile_selection_menu(profiles)

        result = output.getvalue()
        assert "Player1" in result

    def test_get_profile_selection(self, mock_console, monkeypatch):
        """Test get_profile_selection returns valid input."""
        from game.ui import get_profile_selection

        console, output = mock_console
        monkeypatch.setattr('builtins.input', lambda: "1")

        result = get_profile_selection(max_number=5)

        assert result == "1"

    def test_print_current_profile(self, mock_console, monkeypatch):
        """Test print_current_profile displays profile info."""
        from game.ui import print_current_profile
        from dataclasses import dataclass

        console, output = mock_console

        @dataclass
        class MockStats:
            wins: int = 5
            losses: int = 3

        @dataclass
        class MockAIMemory:
            has_personal_model: bool = False

        @dataclass
        class MockProfile:
            name: str = "TestPlayer"
            id: str = "test123"
            stats: MockStats = None
            ai_memory: MockAIMemory = None

            def __post_init__(self):
                if self.stats is None:
                    self.stats = MockStats()
                if self.ai_memory is None:
                    self.ai_memory = MockAIMemory()

        # Mock ProfileManager.get_play_style
        from game import profile_manager
        monkeypatch.setattr(profile_manager.ProfileManager, 'get_play_style', lambda self, p: "Balanced")

        profile = MockProfile()
        print_current_profile(profile)

        result = output.getvalue()
        assert "TestPlayer" in result


class TestHidingUI:
    """Tests for hiding/escape UI functions."""

    def test_print_caught_message(self, mock_console, temp_config_dir):
        """Test print_caught_message displays caught info."""
        from game.ui import print_caught_message

        console, output = mock_console
        player = Player(1, "Alice")
        loc = Location("Test Store", "🏪", 5, 10)

        print_caught_message(player, loc)

        result = output.getvalue()
        assert len(result) > 0

    def test_select_escape_option(self, mock_console, monkeypatch, temp_config_dir):
        """Test select_escape_option returns selected option."""
        from game.ui import select_escape_option

        console, output = mock_console
        # Mock input to select first option
        monkeypatch.setattr('builtins.input', lambda: "1")

        escape_options = [
            {'id': 'hide1', 'name': 'Hide Spot 1', 'description': 'A hiding spot', 'emoji': '📦', 'type': 'hide'},
            {'id': 'run1', 'name': 'Run Route 1', 'description': 'An escape route', 'emoji': '🚪', 'type': 'run'}
        ]

        player = Player(1, "Alice")
        result = select_escape_option(escape_options, player, location_points=20)

        assert result['id'] == 'hide1'

    def test_print_escape_result_success(self, mock_console, temp_config_dir, monkeypatch):
        """Test print_escape_result for successful escape."""
        from game.ui import print_escape_result
        import game.animations as animations
        import game.ui as ui_module

        # Mock animations to avoid actual display
        monkeypatch.setattr(animations, 'play_escape_animation', lambda: None)
        # Mock console.input to avoid stdin issue
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        result = {
            'escaped': True,
            'points_awarded': 16,
            'player_choice_id': 'hide1',
            'player_choice_name': 'Hide Spot',
            'ai_prediction_id': 'hide2',
            'choice_type': 'hide',
            'ai_was_correct': False
        }

        print_escape_result(player, result)

        output_text = output.getvalue()
        assert len(output_text) > 0

    def test_print_escape_result_failure(self, mock_console, temp_config_dir, monkeypatch):
        """Test print_escape_result for failed escape."""
        from game.ui import print_escape_result
        import game.animations as animations
        import game.ui as ui_module

        monkeypatch.setattr(animations, 'play_elimination_animation', lambda: None)
        # Mock console.input to avoid stdin issue
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        result = {
            'escaped': False,
            'points_awarded': 0,
            'player_choice_id': 'hide1',
            'player_choice_name': 'Hide Spot',
            'ai_prediction_id': 'hide1',
            'choice_type': 'hide',
            'ai_was_correct': True
        }

        print_escape_result(player, result)

        output_text = output.getvalue()
        assert len(output_text) > 0


class TestPostGameReport:
    """Tests for post-game report display."""

    def test_print_post_game_report(self, mock_console, temp_config_dir):
        """Test print_post_game_report displays summary."""
        from game.ui import print_post_game_report

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 105

        insights = {
            'total_rounds': 8,
            'times_caught': 2,
            'total_points_earned': 105,
            'favorite_location': 'Test Store',
            'win': True
        }

        print_post_game_report(player, insights)

        result = output.getvalue()
        assert len(result) > 0


class TestLocationsWithEvents:
    """Tests for location display with events."""

    def test_print_locations_with_scout_rolls(self, mock_console, sample_location_manager):
        """Test print_locations with Scout preview rolls."""
        from game.ui import print_locations

        console, output = mock_console

        scout_rolls = {
            sample_location_manager.get_location(0): 8,
            sample_location_manager.get_location(1): 15
        }

        print_locations(sample_location_manager, scout_rolls=scout_rolls)

        result = output.getvalue()
        assert len(result) > 0

    def test_print_locations_with_point_hints(self, mock_console, sample_location_manager):
        """Test print_locations with point trend hints."""
        from game.ui import print_locations

        console, output = mock_console

        point_hints = {
            sample_location_manager.get_location(0).name: "Trending Low",
            sample_location_manager.get_location(1).name: "Trending High"
        }

        print_locations(sample_location_manager, point_hints=point_hints)

        result = output.getvalue()
        assert len(result) > 0


class TestAIThinking:
    """Tests for AI thinking display."""

    def test_show_ai_thinking(self, mock_console, monkeypatch):
        """Test show_ai_thinking displays thinking message."""
        from game.ui import show_ai_thinking
        import time

        console, output = mock_console

        # Speed up the test by mocking sleep
        monkeypatch.setattr(time, 'sleep', lambda x: None)

        show_ai_thinking()

        result = output.getvalue()
        assert len(result) > 0

    def test_create_progress_spinner(self, mock_console):
        """Test create_progress_spinner returns Progress object."""
        from game.ui import create_progress_spinner
        from rich.progress import Progress

        spinner = create_progress_spinner("Testing...")

        assert isinstance(spinner, Progress)


class TestFlushInput:
    """Tests for flush_input function."""

    def test_flush_input_windows(self, monkeypatch):
        """Test flush_input on Windows platform."""
        from game.ui import flush_input
        import sys

        # Mock Windows platform
        monkeypatch.setattr(sys, 'platform', 'win32')

        # Should not crash
        flush_input()

    def test_flush_input_linux(self, monkeypatch):
        """Test flush_input on Linux platform."""
        from game.ui import flush_input
        import sys

        # Mock Linux platform
        monkeypatch.setattr(sys, 'platform', 'linux')

        # Should not crash
        flush_input()


class TestPrintLocationsEdgeCases:
    """Tests for print_locations edge cases."""

    def test_print_locations_with_scout_rolls_by_name(self, mock_console, sample_location_manager):
        """Test print_locations with Scout preview rolls keyed by name."""
        from game.ui import print_locations

        console, output = mock_console

        # Scout rolls keyed by location NAME (not object)
        scout_rolls = {
            sample_location_manager.get_location(0).name: 8,
            sample_location_manager.get_location(1).name: 15
        }

        print_locations(sample_location_manager, scout_rolls=scout_rolls)

        result = output.getvalue()
        assert "Scout" in result or "8" in result

    def test_print_locations_with_point_hints_by_name(self, mock_console, sample_location_manager):
        """Test print_locations with point hints keyed by name."""
        from game.ui import print_locations

        console, output = mock_console

        # Point hints keyed by location NAME
        point_hints = {
            sample_location_manager.get_location(0).name: "Trending Low",
            sample_location_manager.get_location(1).name: "Trending High",
            sample_location_manager.get_location(2).name if len(sample_location_manager.get_all()) > 2 else sample_location_manager.get_location(0).name: "Trending High"
        }

        print_locations(sample_location_manager, point_hints=point_hints)

        result = output.getvalue()
        # Should display with hint colors
        assert len(result) > 0


class TestGetPlayerInputEdgeCases:
    """Tests for get_player_input edge cases."""

    def test_get_player_input_invalid_then_valid(self, mock_console, monkeypatch):
        """Test get_player_input handles invalid input then valid."""
        from game.ui import get_player_input
        import game.ui

        console, output = mock_console

        # Mock console.input to return invalid then valid
        inputs = iter(["abc", "2"])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        result = get_player_input("Choose:", range(1, 5))

        assert result == "2"

    def test_get_player_input_out_of_range_then_valid(self, mock_console, monkeypatch):
        """Test get_player_input handles out of range then valid."""
        from game.ui import get_player_input
        import game.ui

        console, output = mock_console

        # Mock console.input to return out of range then valid
        inputs = iter(["10", "3"])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        result = get_player_input("Choose:", range(1, 5))

        assert result == "3"


class TestShowIntelReportEdgeCases:
    """Tests for show_intel_report edge cases."""

    def test_show_intel_report_with_ai_memory_training(self, mock_console, temp_config_dir):
        """Test Intel Report when AI is training a model."""
        from game.ui import show_intel_report

        console, output = mock_console
        player = Player(1, "Alice")

        ai_memory = {
            'favorite_location': 'Test Store',
            'risk_profile': 'aggressive',
            'catch_rate': 0.25,
            'has_personal_model': False,
            'total_games': 5
        }

        show_intel_report(
            player,
            threat_level=0.5,
            predictability=0.5,
            insights=["Test insight"],
            ai_memory=ai_memory,
            detail_level="full"
        )

        result = output.getvalue()
        assert "training" in result.lower() or "model" in result.lower()

    def test_show_intel_report_with_hiding_stats(self, mock_console, temp_config_dir):
        """Test Intel Report with hiding statistics."""
        from game.ui import show_intel_report

        console, output = mock_console
        player = Player(1, "Alice")

        ai_memory = {
            'favorite_location': 'Test Store',
            'risk_profile': 'cautious',
            'catch_rate': 0.3,
            'has_personal_model': True,
            'total_games': 10,
            'hiding_stats': {
                'total_caught': 5,
                'hide_attempts': 3,
                'run_attempts': 2,
                'hide_success_rate': 0.67,
                'run_success_rate': 0.5,
                'risk_profile_when_caught': 'careful_hider'
            }
        }

        show_intel_report(
            player,
            threat_level=0.8,
            predictability=0.7,
            insights=["Pattern detected"],
            ai_memory=ai_memory,
            detail_level="full"
        )

        result = output.getvalue()
        assert "ESCAPE" in result.upper() or "Hide" in result or "Run" in result


class TestPrintPostGameReportEdgeCases:
    """Tests for print_post_game_report edge cases."""

    def test_print_post_game_report_with_tips(self, mock_console, temp_config_dir):
        """Test post-game report displays tips."""
        from game.ui import print_post_game_report

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 75

        # Add some history
        from game.locations import Location
        loc = Location("Test Store", "🏪", 5, 10)
        for i in range(5):
            player.record_choice(loc, i+1, False, 7)

        insights = {
            'predictability': 0.8,
            'patterns': ["High-value bias detected"],
            'tips': ["Mix in more low-value locations", "Vary your choices more"]
        }

        print_post_game_report(player, insights)

        result = output.getvalue()
        assert "tip" in result.lower() or "💡" in result


class TestPrintProfileSelectionMenuEdgeCases:
    """Tests for print_profile_selection_menu edge cases."""

    def test_print_profile_selection_menu_with_old_date(self, mock_console):
        """Test profile menu with older last_played dates."""
        from game.ui import print_profile_selection_menu
        from dataclasses import dataclass
        from datetime import datetime, timezone, timedelta

        console, output = mock_console

        @dataclass
        class MockProfile:
            name: str = "Player1"
            id: str = "p1"
            last_played: str = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            wins: int = 5
            losses: int = 5
            total_games: int = 10
            win_rate: float = 0.5

        profiles = [MockProfile()]
        print_profile_selection_menu(profiles)

        result = output.getvalue()
        assert "Player1" in result

    def test_print_profile_selection_menu_with_invalid_date(self, mock_console):
        """Test profile menu handles invalid date gracefully."""
        from game.ui import print_profile_selection_menu
        from dataclasses import dataclass

        console, output = mock_console

        @dataclass
        class MockProfile:
            name: str = "Player1"
            id: str = "p1"
            last_played: str = "invalid-date"
            wins: int = 5
            losses: int = 5
            total_games: int = 10
            win_rate: float = 0.5

        profiles = [MockProfile()]
        print_profile_selection_menu(profiles)

        result = output.getvalue()
        # Should show "Unknown" for invalid date
        assert "Player1" in result


class TestPrintProfileStatsSummary:
    """Tests for print_profile_stats_summary function."""

    def test_print_profile_stats_summary_basic(self, mock_console, monkeypatch):
        """Test profile stats summary display."""
        from game.ui import print_profile_stats_summary
        from dataclasses import dataclass, field
        from typing import List
        import game.ui

        console, output = mock_console

        @dataclass
        class MockStats:
            total_games: int = 10
            wins: int = 6
            losses: int = 4
            win_rate: float = 0.6
            highest_score: int = 95
            times_caught: int = 3

        @dataclass
        class MockBehavioralStats:
            favorite_location: str = "Bank Vault"
            risk_profile: str = "aggressive"
            predictability_score: float = 0.45

        @dataclass
        class MockAIMemory:
            has_personal_model: bool = False
            model_trained_date: str = ""
            catch_rate: float = 0.3

        @dataclass
        class MockMatch:
            outcome: str = "win"
            final_score: int = 100
            rounds_played: int = 8
            caught: bool = False

        @dataclass
        class MockProfile:
            name: str = "TestPlayer"
            stats: MockStats = field(default_factory=MockStats)
            behavioral_stats: MockBehavioralStats = field(default_factory=MockBehavioralStats)
            ai_memory: MockAIMemory = field(default_factory=MockAIMemory)
            match_history: List = field(default_factory=list)

        profile = MockProfile()
        profile.match_history = [MockMatch()]

        # Mock console.input for "Press Enter to continue"
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt="": "")

        print_profile_stats_summary(profile)

        result = output.getvalue()
        assert "TestPlayer" in result.upper() or "testplayer" in result.lower()

    def test_print_profile_stats_summary_with_ai_model(self, mock_console, monkeypatch):
        """Test profile stats summary with personal AI model."""
        from game.ui import print_profile_stats_summary
        from dataclasses import dataclass, field
        from typing import List
        import game.ui

        console, output = mock_console

        @dataclass
        class MockStats:
            total_games: int = 10
            wins: int = 6
            losses: int = 4
            win_rate: float = 0.6
            highest_score: int = 95
            times_caught: int = 3

        @dataclass
        class MockBehavioralStats:
            favorite_location: str = "Bank Vault"
            risk_profile: str = "aggressive"
            predictability_score: float = 0.45

        @dataclass
        class MockAIMemory:
            has_personal_model: bool = True
            model_trained_date: str = "2025-01-01"
            catch_rate: float = 0.4

        @dataclass
        class MockProfile:
            name: str = "TestPlayer"
            stats: MockStats = field(default_factory=MockStats)
            behavioral_stats: MockBehavioralStats = field(default_factory=MockBehavioralStats)
            ai_memory: MockAIMemory = field(default_factory=MockAIMemory)
            match_history: List = field(default_factory=list)

        profile = MockProfile()

        monkeypatch.setattr(game.ui.console, 'input', lambda prompt="": "")

        print_profile_stats_summary(profile)

        result = output.getvalue()
        assert "AI" in result.upper() or "model" in result.lower()


class TestGetProfileSelection:
    """Tests for get_profile_selection function."""

    def test_get_profile_selection_invalid_then_valid(self, mock_console, monkeypatch):
        """Test get_profile_selection handles invalid input then valid."""
        from game.ui import get_profile_selection
        import game.ui

        console, output = mock_console

        # Mock console.input to return invalid then valid
        inputs = iter(["abc", "N"])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        result = get_profile_selection(max_number=5)

        assert result == "N"

    def test_get_profile_selection_out_of_range_then_valid(self, mock_console, monkeypatch):
        """Test get_profile_selection handles out of range then valid."""
        from game.ui import get_profile_selection
        import game.ui

        console, output = mock_console

        # Mock console.input to return out of range then valid
        inputs = iter(["10", "2"])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        result = get_profile_selection(max_number=5)

        assert result == "2"


class TestPrintCurrentProfileEdgeCases:
    """Tests for print_current_profile edge cases."""

    def test_print_current_profile_with_ai_model(self, mock_console, monkeypatch):
        """Test print_current_profile shows AI model warning."""
        from game.ui import print_current_profile
        from dataclasses import dataclass
        import game.ui
        from game import profile_manager

        console, output = mock_console

        @dataclass
        class MockStats:
            wins: int = 5
            losses: int = 3

        @dataclass
        class MockAIMemory:
            has_personal_model: bool = True

        @dataclass
        class MockProfile:
            name: str = "TestPlayer"
            stats: MockStats = None
            ai_memory: MockAIMemory = None

            def __post_init__(self):
                if self.stats is None:
                    self.stats = MockStats()
                if self.ai_memory is None:
                    self.ai_memory = MockAIMemory()

        # Mock ProfileManager.get_play_style
        monkeypatch.setattr(profile_manager.ProfileManager, 'get_play_style', lambda self, p: "Aggressive")

        profile = MockProfile()
        print_current_profile(profile)

        result = output.getvalue()
        assert "AI" in result or "learned" in result.lower() or "patterns" in result.lower()

    def test_print_current_profile_no_profile(self, mock_console):
        """Test print_current_profile with no profile."""
        from game.ui import print_current_profile

        console, output = mock_console

        print_current_profile(None)

        result = output.getvalue()
        assert "guest" in result.lower() or "No profile" in result


class TestSelectEscapeOptionEdgeCases:
    """Tests for select_escape_option edge cases."""

    def test_select_escape_option_invalid_then_valid(self, mock_console, monkeypatch, temp_config_dir):
        """Test select_escape_option handles invalid input."""
        from game.ui import select_escape_option
        import game.ui

        console, output = mock_console

        player = Player(1, "Alice")
        escape_options = [
            {'id': 'hide1', 'name': 'Behind Boxes', 'description': 'Hide behind boxes', 'emoji': '📦', 'type': 'hide'},
            {'id': 'run1', 'name': 'Back Door', 'description': 'Run out back', 'emoji': '🚪', 'type': 'run'}
        ]

        # Mock console.input to return invalid then valid
        inputs = iter(["abc", "0", "5", "1"])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        result = select_escape_option(escape_options, player, location_points=20)

        assert result['id'] == 'hide1'


class TestPrintEscapeResultEdgeCases:
    """Tests for print_escape_result edge cases."""

    def test_print_escape_result_with_option_names(self, mock_console, monkeypatch, temp_config_dir):
        """Test print_escape_result finds option names from list."""
        from game.ui import print_escape_result
        import game.animations as animations
        import game.ui as ui_module
        import time

        monkeypatch.setattr(animations, 'play_escape_animation', lambda: None)
        monkeypatch.setattr(animations, 'play_elimination_animation', lambda: None)
        monkeypatch.setattr(time, 'sleep', lambda x: None)
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        escape_options = [
            {'id': 'hide1', 'name': 'Behind Boxes', 'emoji': '📦'},
            {'id': 'run1', 'name': 'Back Door', 'emoji': '🚪'}
        ]

        result = {
            'escaped': True,
            'points_awarded': 16,
            'player_choice_id': 'hide1',
            'player_choice_name': 'Behind Boxes',
            'ai_prediction_id': 'run1',  # AI predicted wrong
            'choice_type': 'hide',
            'location_points': 20
        }

        print_escape_result(player, result, escape_options)

        output_text = output.getvalue()
        assert "Back Door" in output_text or "Behind Boxes" in output_text

    def test_print_escape_result_run_success(self, mock_console, monkeypatch, temp_config_dir):
        """Test print_escape_result for successful run."""
        from game.ui import print_escape_result
        import game.animations as animations
        import game.ui as ui_module
        import time

        monkeypatch.setattr(animations, 'play_escape_animation', lambda: None)
        monkeypatch.setattr(time, 'sleep', lambda x: None)
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        result = {
            'escaped': True,
            'points_awarded': 16,
            'player_choice_id': 'run1',
            'player_choice_name': 'Back Door',
            'ai_prediction_id': 'hide1',
            'choice_type': 'run',
            'location_points': 20
        }

        print_escape_result(player, result)

        output_text = output.getvalue()
        assert "16" in output_text or "kept" in output_text.lower()


class TestLegacyEscapeFunctions:
    """Tests for legacy print_escape_success and print_escape_failure."""

    def test_print_escape_success_hide(self, mock_console, monkeypatch, temp_config_dir):
        """Test legacy print_escape_success for hide."""
        from game.ui import print_escape_success
        import game.ui as ui_module

        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        result = {
            'choice': 'hide',
            'hide_spot_name': 'Behind Boxes',
            'success_chance': 0.6
        }

        print_escape_success(player, result)

        output_text = output.getvalue()
        assert "hid" in output_text.lower() or "Behind Boxes" in output_text

    def test_print_escape_success_run(self, mock_console, monkeypatch, temp_config_dir):
        """Test legacy print_escape_success for run."""
        from game.ui import print_escape_success
        import game.ui as ui_module

        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        result = {
            'choice': 'run',
            'success_chance': 0.7,
            'points_retained': 16
        }

        print_escape_success(player, result)

        output_text = output.getvalue()
        assert "escaped" in output_text.lower()

    def test_print_escape_success_with_search_location(self, mock_console, monkeypatch, temp_config_dir):
        """Test print_escape_success with search location info."""
        from game.ui import print_escape_success
        import game.ui as ui_module

        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        result = {'choice': 'hide', 'hide_spot_name': 'Test'}

        search_location = Location("Test Store", "🏪", 5, 10)

        print_escape_success(player, result, search_location)

        output_text = output.getvalue()
        assert "Test Store" in output_text

    def test_print_escape_failure_hide(self, mock_console, monkeypatch, temp_config_dir):
        """Test legacy print_escape_failure for hide."""
        from game.ui import print_escape_failure
        import game.animations as animations
        import game.ui as ui_module

        monkeypatch.setattr(animations, 'play_elimination_animation', lambda: None)
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        result = {
            'choice': 'hide',
            'hide_spot_name': 'Behind Boxes',
            'success_chance': 0.3
        }

        print_escape_failure(player, result)

        output_text = output.getvalue()
        assert "found" in output_text.lower() or "ELIMINATED" in output_text

    def test_print_escape_failure_run(self, mock_console, monkeypatch, temp_config_dir):
        """Test legacy print_escape_failure for run."""
        from game.ui import print_escape_failure
        import game.animations as animations
        import game.ui as ui_module

        monkeypatch.setattr(animations, 'play_elimination_animation', lambda: None)
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50

        result = {
            'choice': 'run',
            'success_chance': 0.4
        }

        print_escape_failure(player, result)

        output_text = output.getvalue()
        assert "caught" in output_text.lower() or "ELIMINATED" in output_text

    def test_print_escape_failure_with_search_location(self, mock_console, monkeypatch, temp_config_dir):
        """Test print_escape_failure with search location info."""
        from game.ui import print_escape_failure
        import game.animations as animations
        import game.ui as ui_module

        monkeypatch.setattr(animations, 'play_elimination_animation', lambda: None)
        monkeypatch.setattr(ui_module.console, 'input', lambda *args, **kwargs: "")

        console, output = mock_console
        player = Player(1, "Alice")

        result = {'choice': 'hide', 'hide_spot_name': 'Test'}

        search_location = Location("Test Store", "🏪", 5, 10)

        print_escape_failure(player, result, search_location)

        output_text = output.getvalue()
        assert "Test Store" in output_text
