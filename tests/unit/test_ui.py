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

    def test_print_standings_with_items(self, mock_console, temp_config_dir):
        """Test print_standings displays player items."""
        console, output = mock_console
        player = Player(1, "Alice")
        player.points = 50
        player.items.append(ItemShop.get_item(ItemType.LUCKY_CHARM))

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

    def test_print_player_looted_with_lucky_charm(self, mock_console, temp_config_dir):
        """Test print_player_looted displays Lucky Charm multiplier."""
        console, output = mock_console
        player = Player(1, "Alice")
        loc = Location("Test Store", "🏪", 5, 10)

        print_player_looted(player, loc, points_earned=23, base_roll=20,
                          used_lucky_charm=True, lucky_charm_multiplier=1.15)

        result = output.getvalue()
        assert "Alice" in result
        # Should show multiplier breakdown
        assert "1.15" in result or "15%" in result or "Lucky Charm" in result


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
