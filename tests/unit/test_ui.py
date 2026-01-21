"""Tests for client/ui.py module - UI functionality."""
from unittest.mock import MagicMock, patch

import pytest

from client.lan import DiscoveredGame
from client.ui import select_lan_game
from version import VERSION


class TestSelectLanGame:
    """Tests for select_lan_game function."""

    def test_returns_none_for_empty_games_list(self):
        """Test that select_lan_game returns None for empty list."""
        result = select_lan_game([])
        assert result is None

    def test_shows_version_in_choice_text(self, mock_questionary):
        """Test that version is included in game choice text."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Test Game",
                host_name="Host",
                player_count=2,
                max_players=6,
                version="v2026.01.20"
            )
        ]

        # Mock selecting the first game (version different from client so has [!])
        mock_questionary("Test Game - Host (2/6) [v2026.01.20] [!]")

        result = select_lan_game(games)
        assert result == 0

    def test_compatible_version_no_warning_indicator(self, mock_questionary):
        """Test that compatible version games don't have warning indicator."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Compatible Game",
                host_name="Host",
                player_count=1,
                max_players=6,
                version=VERSION  # Same as client
            )
        ]

        # Expected choice text without [!] indicator
        expected_choice = f"Compatible Game - Host (1/6) [{VERSION}]"
        mock_questionary(expected_choice)

        result = select_lan_game(games)
        assert result == 0

    def test_incompatible_version_has_warning_indicator(self, mock_questionary):
        """Test that incompatible version games have [!] indicator."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Incompatible Game",
                host_name="Host",
                player_count=1,
                max_players=6,
                version="v9999.99.99"  # Different from client
            )
        ]

        # Expected choice text with [!] indicator
        expected_choice = "Incompatible Game - Host (1/6) [v9999.99.99] [!]"
        mock_questionary(expected_choice)

        result = select_lan_game(games)
        assert result == 0

    def test_cancel_returns_none(self, mock_questionary):
        """Test that selecting cancel returns None."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Test Game",
                host_name="Host",
                player_count=1,
                max_players=6,
                version=VERSION
            )
        ]

        mock_questionary("Cancel - Return to menu")

        result = select_lan_game(games)
        assert result is None

    def test_multiple_games_with_mixed_versions(self, mock_questionary):
        """Test display of multiple games with mixed version compatibility."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Compatible",
                host_name="Host A",
                player_count=2,
                max_players=6,
                version=VERSION
            ),
            DiscoveredGame(
                host="192.168.1.101",
                port=8765,
                game_name="Incompatible",
                host_name="Host B",
                player_count=1,
                max_players=4,
                version="v1.0.0"
            ),
            DiscoveredGame(
                host="192.168.1.102",
                port=8765,
                game_name="Unknown Ver",
                host_name="Host C",
                player_count=3,
                max_players=6,
                version="unknown"
            )
        ]

        # Select the second game (incompatible)
        expected_choice = "Incompatible - Host B (1/4) [v1.0.0] [!]"
        mock_questionary(expected_choice)

        result = select_lan_game(games)
        assert result == 1

    def test_selects_correct_index_from_multiple_games(self, mock_questionary):
        """Test that correct index is returned when selecting from multiple games."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Game 1",
                host_name="Host 1",
                player_count=1,
                max_players=6,
                version=VERSION
            ),
            DiscoveredGame(
                host="192.168.1.101",
                port=8765,
                game_name="Game 2",
                host_name="Host 2",
                player_count=2,
                max_players=6,
                version=VERSION
            ),
            DiscoveredGame(
                host="192.168.1.102",
                port=8765,
                game_name="Game 3",
                host_name="Host 3",
                player_count=3,
                max_players=6,
                version=VERSION
            )
        ]

        # Select the third game
        expected_choice = f"Game 3 - Host 3 (3/6) [{VERSION}]"
        mock_questionary(expected_choice)

        result = select_lan_game(games)
        assert result == 2

    def test_unknown_version_shows_warning(self, mock_questionary):
        """Test that unknown version shows warning indicator."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Old Server",
                host_name="Host",
                player_count=1,
                max_players=6,
                version="unknown"  # Legacy server without version
            )
        ]

        # Unknown version should have [!] indicator (unless client version is also unknown)
        if VERSION != "unknown":
            expected_choice = "Old Server - Host (1/6) [unknown] [!]"
        else:
            expected_choice = "Old Server - Host (1/6) [unknown]"

        mock_questionary(expected_choice)

        result = select_lan_game(games)
        assert result == 0
