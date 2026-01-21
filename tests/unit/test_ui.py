"""Tests for client/ui.py module - UI functionality."""
from unittest.mock import MagicMock, patch

import pytest

from client.lan import DiscoveredGame
from client.state import ClientPhase, PlayerInfo, LocationInfo
from client.ui import (
    select_lan_game,
    clear_screen,
    print_header,
    print_main_menu,
    print_lobby,
    print_standings,
    print_locations,
    print_location_choice_prompt,
    print_waiting_for_players,
    print_round_results,
    print_escape_prompt,
    print_escape_result,
    print_game_over,
    print_shop,
    print_connecting,
    print_error,
    print_info,
    wait_for_enter,
    get_input,
    get_player_count,
    get_player_name,
    get_host_name,
    get_game_name,
    get_server_address,
    get_location_choice,
    get_escape_choice,
    get_shop_choice,
)
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

    def test_returns_none_on_unmatched_choice(self, mock_questionary):
        """Test that unmatched choice returns None (fallback path)."""
        games = [
            DiscoveredGame(
                host="192.168.1.100",
                port=8765,
                game_name="Game",
                host_name="Host",
                player_count=1,
                max_players=6,
                version=VERSION
            )
        ]

        # Return a value that doesn't match any choice
        mock_questionary("Non-existent choice")

        result = select_lan_game(games)
        assert result is None


class TestClearScreen:
    """Tests for clear_screen function."""

    def test_clears_console(self, mock_console):
        """Test that clear_screen calls console.clear()."""
        mock_console.install()
        clear_screen()
        assert mock_console.clear_calls == 1


class TestPrintHeader:
    """Tests for print_header function."""

    def test_prints_title_only(self, mock_console):
        """Test printing header with title only."""
        mock_console.install()
        print_header("Test Title")
        # Verify print was called (Panel object is passed to print)
        assert mock_console.print_calls

    def test_prints_title_and_subtitle(self, mock_console):
        """Test printing header with title and subtitle."""
        mock_console.install()
        print_header("Main Title", "Subtitle Here")
        # Verify print was called
        assert mock_console.print_calls


class TestPrintMainMenu:
    """Tests for print_main_menu function."""

    def test_returns_single_player_choice(self, mock_console, mock_ui_inputs):
        """Test selecting single player returns '1'."""
        mock_console.install()
        mock_ui_inputs(["Single Player"])
        result = print_main_menu()
        assert result == "1"

    def test_returns_local_multiplayer_choice(self, mock_console, mock_ui_inputs):
        """Test selecting local multiplayer returns '2'."""
        mock_console.install()
        mock_ui_inputs(["Local Multiplayer (Hot-Seat)"])
        result = print_main_menu()
        assert result == "2"

    def test_returns_host_online_choice(self, mock_console, mock_ui_inputs):
        """Test selecting host online returns '3'."""
        mock_console.install()
        mock_ui_inputs(["Host Online Game"])
        result = print_main_menu()
        assert result == "3"

    def test_returns_join_online_choice(self, mock_console, mock_ui_inputs):
        """Test selecting join online returns '4'."""
        mock_console.install()
        mock_ui_inputs(["Join Online Game"])
        result = print_main_menu()
        assert result == "4"

    def test_returns_quit_choice(self, mock_console, mock_ui_inputs):
        """Test selecting quit returns '5'."""
        mock_console.install()
        mock_ui_inputs(["Quit"])
        result = print_main_menu()
        assert result == "5"

    def test_returns_quit_on_none(self, mock_console, mock_ui_inputs):
        """Test that None selection defaults to quit."""
        mock_console.install()
        mock_ui_inputs([None])
        result = print_main_menu()
        assert result == "5"


class TestPrintLobby:
    """Tests for print_lobby function."""

    def test_prints_lobby_as_host(self, mock_console, mock_game_state):
        """Test lobby display for host."""
        mock_console.install()
        state = mock_game_state(
            game_id="test_lobby",
            players=[
                {"username": "Host", "ready": True, "connected": True, "is_local": True},
                {"username": "Player2", "ready": False, "connected": True},
            ]
        )
        print_lobby(state, is_host=True)
        # Verify console interactions happened
        assert mock_console.clear_calls > 0
        assert len(mock_console.print_calls) > 0

    def test_prints_lobby_as_player(self, mock_console, mock_game_state):
        """Test lobby display for non-host player."""
        mock_console.install()
        state = mock_game_state(
            game_id="test_lobby",
            players=[
                {"username": "Host", "ready": True, "connected": True},
                {"username": "Me", "ready": False, "connected": True, "is_local": True},
            ]
        )
        print_lobby(state, is_host=False)
        assert mock_console.clear_calls > 0

    def test_shows_disconnected_player(self, mock_console, mock_game_state):
        """Test that disconnected players show disconnected status."""
        mock_console.install()
        state = mock_game_state(
            game_id="test",
            players=[
                {"username": "Connected", "connected": True},
                {"username": "Disconnected", "connected": False},
            ]
        )
        print_lobby(state)
        # Verify print was called for the lobby display
        assert mock_console.print_calls


class TestPrintStandings:
    """Tests for print_standings function."""

    def test_prints_standings_with_alive_players(self, mock_console, mock_game_state):
        """Test standings with alive players."""
        mock_console.install()
        state = mock_game_state(
            round_num=3,
            players=[
                {"player_id": "p1", "username": "Alice", "points": 50, "alive": True},
                {"player_id": "p2", "username": "Bob", "points": 30, "alive": True},
            ],
            local_player_ids=["p1"]
        )
        print_standings(state)
        # Verify print was called for standings table
        assert mock_console.print_calls

    def test_prints_standings_with_eliminated_player(self, mock_console, mock_game_state):
        """Test standings show eliminated players."""
        mock_console.install()
        state = mock_game_state(
            round_num=5,
            players=[
                {"username": "Alive", "points": 80, "alive": True},
                {"username": "Dead", "points": 20, "alive": False},
            ]
        )
        print_standings(state)
        # Verify print was called
        assert mock_console.print_calls


class TestPrintLocations:
    """Tests for print_locations function."""

    def test_prints_locations_without_events(self, mock_console, mock_game_state):
        """Test location display without events."""
        mock_console.install()
        state = mock_game_state(
            locations=[
                {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
                {"name": "Bank", "emoji": "🏦", "min_points": 10, "max_points": 20},
            ]
        )
        print_locations(state)
        # Verify print was called for locations table
        assert mock_console.print_calls

    def test_prints_locations_with_events(self, mock_console, mock_game_state):
        """Test location display with events."""
        mock_console.install()
        state = mock_game_state(
            locations=[
                {
                    "name": "Store",
                    "emoji": "🏪",
                    "min_points": 5,
                    "max_points": 10,
                    "event": {"name": "Jackpot", "emoji": "💰"}
                },
            ]
        )
        print_locations(state, show_events=True)
        # Verify print was called
        assert mock_console.print_calls

    def test_hides_events_when_flag_false(self, mock_console, mock_game_state):
        """Test that events are hidden when show_events=False."""
        mock_console.install()
        state = mock_game_state(
            locations=[
                {
                    "name": "Store",
                    "emoji": "🏪",
                    "min_points": 5,
                    "max_points": 10,
                    "event": {"name": "Jackpot", "emoji": "💰"}
                },
            ]
        )
        print_locations(state, show_events=False)
        # Verify print was called (event is not shown when flag is False)
        assert mock_console.print_calls


class TestPrintLocationChoicePrompt:
    """Tests for print_location_choice_prompt function."""

    def test_prints_choice_prompt(self, mock_console, mock_game_state):
        """Test location choice prompt display."""
        mock_console.install()
        state = mock_game_state(
            round_num=2,
            players=[
                {"player_id": "p1", "username": "TestPlayer", "points": 25, "alive": True},
            ],
            locations=[
                {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
            ],
            local_player_ids=["p1"]
        )
        player = state.get_player("p1")
        print_location_choice_prompt(state, player)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_shows_previous_ai_location(self, mock_console, mock_game_state):
        """Test that previous AI location is shown when set."""
        mock_console.install()
        state = mock_game_state(
            round_num=3,
            previous_ai_location="Bank",
            players=[{"player_id": "p1", "username": "Test", "points": 0}],
            locations=[{"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10}],
            local_player_ids=["p1"]
        )
        player = state.get_player("p1")
        print_location_choice_prompt(state, player)
        # Verify additional print call for previous AI location
        assert mock_console.print_calls


class TestPrintWaitingForPlayers:
    """Tests for print_waiting_for_players function."""

    def test_shows_submitted_players(self, mock_console, mock_game_state):
        """Test waiting screen shows who has submitted."""
        mock_console.install()
        state = mock_game_state(
            round_num=1,
            players=[
                {"player_id": "p1", "username": "Alice", "alive": True},
                {"player_id": "p2", "username": "Bob", "alive": True},
                {"player_id": "p3", "username": "Charlie", "alive": True},
            ]
        )
        print_waiting_for_players(state, submitted=["p1", "p2"])
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls


class TestPrintRoundResults:
    """Tests for print_round_results function."""

    def test_shows_ai_search_location(self, mock_console, mock_game_state):
        """Test results show where AI searched."""
        mock_console.install()
        state = mock_game_state(round_num=1)
        results = {
            "ai_search_location": "Bank",
            "ai_search_emoji": "🏦",
            "player_results": []
        }
        print_round_results(state, results)
        # Verify console was used
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_shows_caught_player(self, mock_console, mock_game_state):
        """Test results show caught players."""
        mock_console.install()
        state = mock_game_state(round_num=1)
        results = {
            "ai_search_location": "Bank",
            "ai_search_emoji": "🏦",
            "player_results": [
                {
                    "username": "CaughtPlayer",
                    "location": "Bank",
                    "location_emoji": "🏦",
                    "caught": True
                }
            ]
        }
        print_round_results(state, results)
        # Verify print was called for caught player
        assert mock_console.print_calls

    def test_shows_safe_player_with_points(self, mock_console, mock_game_state):
        """Test results show safe players with points earned."""
        mock_console.install()
        state = mock_game_state(round_num=1)
        results = {
            "ai_search_location": "Bank",
            "ai_search_emoji": "🏦",
            "player_results": [
                {
                    "username": "SafePlayer",
                    "location": "Store",
                    "location_emoji": "🏪",
                    "caught": False,
                    "points_earned": 15,
                    "total_points": 45
                }
            ]
        }
        print_round_results(state, results)
        # Verify print was called for safe player
        assert mock_console.print_calls


class TestPrintEscapePrompt:
    """Tests for print_escape_prompt function."""

    def test_shows_caught_info(self, mock_console, mock_game_state):
        """Test escape prompt shows caught location and points."""
        mock_console.install()
        state = mock_game_state(
            caught_location="Vault",
            caught_points=50,
            players=[{"player_id": "p1", "username": "Escapee", "points": 50}]
        )
        player = state.get_player("p1")
        print_escape_prompt(state, player)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls


class TestPrintEscapeResult:
    """Tests for print_escape_result function."""

    def test_shows_successful_escape(self, mock_console):
        """Test escape result for successful escape."""
        mock_console.install()
        result = {
            "escaped": True,
            "username": "Lucky",
            "player_choice_name": "Hide Behind Boxes",
            "ai_prediction_name": "Sprint Away",
            "points_awarded": 40
        }
        print_escape_result(result)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_shows_failed_escape(self, mock_console):
        """Test escape result for failed escape (elimination)."""
        mock_console.install()
        result = {
            "escaped": False,
            "username": "Unlucky",
            "player_choice_name": "Sprint Away",
            "ai_prediction_name": "Sprint Away"
        }
        print_escape_result(result)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls


class TestPrintGameOver:
    """Tests for print_game_over function."""

    def test_shows_ai_wins(self, mock_console, mock_game_state):
        """Test game over when AI wins."""
        mock_console.install()
        state = mock_game_state()
        state.ai_wins = True
        state.final_standings = [
            {"username": "Player1", "points": 30},
            {"username": "Player2", "points": 20},
        ]
        print_game_over(state)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_shows_player_wins(self, mock_console, mock_game_state):
        """Test game over when a player wins."""
        mock_console.install()
        state = mock_game_state()
        state.ai_wins = False
        state.winner = {"username": "Winner", "score": 100}
        state.final_standings = [
            {"username": "Winner", "points": 100},
            {"username": "Second", "points": 50},
        ]
        print_game_over(state)
        # Verify console was used
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_shows_final_standings(self, mock_console, mock_game_state):
        """Test that final standings table is displayed."""
        mock_console.install()
        state = mock_game_state()
        state.ai_wins = False
        state.winner = {"username": "Winner", "score": 100}
        state.final_standings = [
            {"username": "First", "points": 100},
            {"username": "Second", "points": 75},
            {"username": "Third", "points": 50},
        ]
        print_game_over(state)
        # Verify console was used
        assert mock_console.print_calls


class TestPrintShop:
    """Tests for print_shop function."""

    def test_prints_shop_header(self, mock_console, mock_game_state):
        """Test shop header shows player info."""
        mock_console.install()
        state = mock_game_state(
            players=[{"player_id": "p1", "username": "Shopper", "points": 50}]
        )
        player = state.get_player("p1")
        print_shop(state, player)
        # Verify console was cleared and printed to
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls


class TestPrintConnecting:
    """Tests for print_connecting function."""

    def test_prints_connecting_message(self, mock_console):
        """Test connecting message displays host and port."""
        mock_console.install()
        print_connecting("192.168.1.100", 8765)
        # Verify print was called
        assert mock_console.print_calls


class TestPrintError:
    """Tests for print_error function."""

    def test_prints_error_message(self, mock_console):
        """Test error message is displayed."""
        mock_console.install()
        print_error("Something went wrong")
        # Verify print was called
        assert mock_console.print_calls


class TestPrintInfo:
    """Tests for print_info function."""

    def test_prints_info_message(self, mock_console):
        """Test info message is displayed."""
        mock_console.install()
        print_info("Important information")
        # Verify print was called
        assert mock_console.print_calls


class TestWaitForEnter:
    """Tests for wait_for_enter function."""

    def test_waits_for_input(self, mock_console):
        """Test wait_for_enter calls console.input."""
        mock_console.install()
        mock_console.set_input_responses([""])
        wait_for_enter()
        # Function should complete without error


class TestGetInput:
    """Tests for get_input function."""

    def test_returns_stripped_input(self, mock_console):
        """Test get_input returns stripped text."""
        mock_console.install()
        mock_console.set_input_responses(["  test input  "])
        result = get_input("Enter: ")
        assert result == "test input"

    def test_empty_input(self, mock_console):
        """Test get_input with empty input."""
        mock_console.install()
        mock_console.set_input_responses([""])
        result = get_input()
        assert result == ""


class TestGetPlayerCount:
    """Tests for get_player_count function."""

    def test_returns_2_players(self, mock_ui_inputs):
        """Test selecting 2 players returns 2."""
        mock_ui_inputs(["2 Players"])
        result = get_player_count()
        assert result == 2

    def test_returns_4_players(self, mock_ui_inputs):
        """Test selecting 4 players returns 4."""
        mock_ui_inputs(["4 Players"])
        result = get_player_count()
        assert result == 4

    def test_returns_6_players(self, mock_ui_inputs):
        """Test selecting 6 players returns 6."""
        mock_ui_inputs(["6 Players"])
        result = get_player_count()
        assert result == 6

    def test_default_on_none(self, mock_ui_inputs):
        """Test that None selection defaults to 2."""
        mock_ui_inputs([None])
        result = get_player_count()
        assert result == 2


class TestGetPlayerName:
    """Tests for get_player_name function."""

    def test_returns_entered_name(self, mock_ui_inputs):
        """Test returns the entered name."""
        mock_ui_inputs(["Alice"])
        result = get_player_name(1)
        assert result == "Alice"

    def test_returns_default_on_empty(self, mock_ui_inputs):
        """Test returns default name on empty/None input."""
        mock_ui_inputs([None])
        result = get_player_name(3)
        assert result == "Player 3"

    def test_returns_default_on_empty_string(self, mock_ui_inputs):
        """Test returns default name on empty string."""
        mock_ui_inputs([""])
        result = get_player_name(2)
        assert result == "Player 2"


class TestGetHostName:
    """Tests for get_host_name function."""

    def test_returns_entered_name(self, mock_ui_inputs):
        """Test returns the entered host name."""
        mock_ui_inputs(["GameMaster"])
        result = get_host_name()
        assert result == "GameMaster"

    def test_returns_default_on_empty(self, mock_ui_inputs):
        """Test returns 'Host' on empty input."""
        mock_ui_inputs([None])
        result = get_host_name()
        assert result == "Host"


class TestGetGameName:
    """Tests for get_game_name function."""

    def test_returns_entered_name(self, mock_ui_inputs):
        """Test returns the entered game name."""
        mock_ui_inputs(["Epic Heist"])
        result = get_game_name()
        assert result == "Epic Heist"

    def test_returns_default_on_empty(self, mock_ui_inputs):
        """Test returns 'LOOT RUN' on empty input."""
        mock_ui_inputs([None])
        result = get_game_name()
        assert result == "LOOT RUN"


class TestGetServerAddress:
    """Tests for get_server_address function."""

    def test_returns_scan_for_lan(self, mock_ui_inputs):
        """Test selecting LAN scan returns 'scan'."""
        mock_ui_inputs(["Scan for LAN games"])
        result = get_server_address()
        assert result == "scan"

    def test_returns_manual_address(self, mock_ui_inputs):
        """Test entering manual IP address."""
        mock_ui_inputs(["Enter IP address manually", "192.168.1.50"])
        result = get_server_address()
        assert result == "192.168.1.50"

    def test_returns_localhost_on_empty(self, mock_ui_inputs):
        """Test default to localhost on empty input."""
        mock_ui_inputs(["Enter IP address manually", None])
        result = get_server_address()
        assert result == "localhost"


class TestGetLocationChoice:
    """Tests for get_location_choice function."""

    def test_returns_first_location(self, mock_ui_inputs, mock_game_state):
        """Test selecting first location returns index 0."""
        state = mock_game_state(
            locations=[
                {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
                {"name": "Bank", "emoji": "🏦", "min_points": 10, "max_points": 20},
            ]
        )
        mock_ui_inputs(["🏪 Store (5-10 pts)"])
        result = get_location_choice(state)
        assert result == 0

    def test_returns_second_location(self, mock_ui_inputs, mock_game_state):
        """Test selecting second location returns index 1."""
        state = mock_game_state(
            locations=[
                {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
                {"name": "Bank", "emoji": "🏦", "min_points": 10, "max_points": 20},
            ]
        )
        mock_ui_inputs(["🏦 Bank (10-20 pts)"])
        result = get_location_choice(state)
        assert result == 1

    def test_returns_location_with_event(self, mock_ui_inputs, mock_game_state):
        """Test selecting location with event."""
        state = mock_game_state(
            locations=[
                {
                    "name": "Store",
                    "emoji": "🏪",
                    "min_points": 5,
                    "max_points": 10,
                    "event": {"name": "Jackpot"}
                },
            ]
        )
        mock_ui_inputs(["🏪 Store (5-10 pts) [Jackpot]"])
        result = get_location_choice(state)
        assert result == 0

    def test_default_on_none(self, mock_ui_inputs, mock_game_state):
        """Test returns 0 on None selection."""
        state = mock_game_state(
            locations=[
                {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
            ]
        )
        mock_ui_inputs([None])
        result = get_location_choice(state)
        assert result == 0


class TestGetEscapeChoice:
    """Tests for get_escape_choice function."""

    def test_returns_hide_option(self, mock_ui_inputs, mock_game_state):
        """Test selecting hide option."""
        state = mock_game_state(
            escape_options=[
                {"name": "Behind Boxes", "emoji": "📦", "type": "hide"},
                {"name": "Sprint Away", "emoji": "🏃", "type": "run"},
            ]
        )
        mock_ui_inputs(["📦 Behind Boxes [Hide]"])
        result = get_escape_choice(state)
        assert result == 0

    def test_returns_run_option(self, mock_ui_inputs, mock_game_state):
        """Test selecting run option."""
        state = mock_game_state(
            escape_options=[
                {"name": "Behind Boxes", "emoji": "📦", "type": "hide"},
                {"name": "Sprint Away", "emoji": "🏃", "type": "run"},
            ]
        )
        mock_ui_inputs(["🏃 Sprint Away [Run]"])
        result = get_escape_choice(state)
        assert result == 1

    def test_default_on_none(self, mock_ui_inputs, mock_game_state):
        """Test returns 0 on None selection."""
        state = mock_game_state(
            escape_options=[
                {"name": "Behind Boxes", "emoji": "📦", "type": "hide"},
            ]
        )
        mock_ui_inputs([None])
        result = get_escape_choice(state)
        assert result == 0


class TestGetShopChoice:
    """Tests for get_shop_choice function."""

    def test_returns_skip_on_skip_selection(self, mock_ui_inputs, mock_game_state):
        """Test selecting skip returns None."""
        state = mock_game_state(
            available_passives=[
                {"id": "passive1", "name": "Speed Boost", "emoji": "⚡", "cost": 10}
            ],
            players=[{"player_id": "p1", "username": "Player", "points": 50}]
        )
        player = state.get_player("p1")
        mock_ui_inputs(["Skip - Continue to game"])
        result = get_shop_choice(state, player)
        assert result is None

    def test_returns_passive_index(self, mock_ui_inputs, mock_game_state):
        """Test selecting a passive returns its index."""
        state = mock_game_state(
            available_passives=[
                {"id": "passive1", "name": "Speed Boost", "emoji": "⚡", "cost": 10},
                {"id": "passive2", "name": "Armor", "emoji": "🛡️", "cost": 15},
            ],
            players=[{"player_id": "p1", "username": "Player", "points": 50, "passives": []}]
        )
        player = state.get_player("p1")
        mock_ui_inputs(["🛡️ Armor (15 pts)"])
        result = get_shop_choice(state, player)
        assert result == 1

    def test_shows_owned_passive(self, mock_ui_inputs, mock_game_state):
        """Test owned passives show (Owned) status."""
        state = mock_game_state(
            available_passives=[
                {"id": "passive1", "name": "Speed Boost", "emoji": "⚡", "cost": 10},
            ],
            players=[{"player_id": "p1", "username": "Player", "points": 50, "passives": ["passive1"]}]
        )
        player = state.get_player("p1")
        mock_ui_inputs(["⚡ Speed Boost (Owned)"])
        result = get_shop_choice(state, player)
        assert result == 0

    def test_shows_too_expensive(self, mock_ui_inputs, mock_game_state):
        """Test passives too expensive show status."""
        state = mock_game_state(
            available_passives=[
                {"id": "passive1", "name": "Expensive Item", "emoji": "💎", "cost": 100},
            ],
            players=[{"player_id": "p1", "username": "Player", "points": 10, "passives": []}]
        )
        player = state.get_player("p1")
        mock_ui_inputs(["💎 Expensive Item (100 pts - Too expensive)"])
        result = get_shop_choice(state, player)
        assert result == 0

    def test_default_on_none(self, mock_ui_inputs, mock_game_state):
        """Test returns None on None selection."""
        state = mock_game_state(
            available_passives=[
                {"id": "passive1", "name": "Item", "emoji": "📦", "cost": 10},
            ],
            players=[{"player_id": "p1", "username": "Player", "points": 50, "passives": []}]
        )
        player = state.get_player("p1")
        mock_ui_inputs([None])
        result = get_shop_choice(state, player)
        assert result is None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_player_list_in_standings(self, mock_console, mock_game_state):
        """Test standings with no players."""
        mock_console.install()
        state = mock_game_state(round_num=1, players=[])
        print_standings(state)
        # Should complete without error
        assert mock_console.print_calls

    def test_empty_location_list(self, mock_console, mock_game_state):
        """Test locations with empty list."""
        mock_console.install()
        state = mock_game_state(locations=[])
        print_locations(state)
        # Should complete without error
        assert mock_console.print_calls

    def test_game_over_with_no_winner(self, mock_console, mock_game_state):
        """Test game over with no winner data."""
        mock_console.install()
        state = mock_game_state()
        state.ai_wins = False
        state.winner = None
        state.final_standings = []
        print_game_over(state)
        # Should complete without crashing, "Unknown" used for winner
        assert mock_console.print_calls

    def test_round_results_missing_data(self, mock_console, mock_game_state):
        """Test round results with missing data."""
        mock_console.install()
        state = mock_game_state(round_num=1)
        # Empty results dict
        results = {}
        print_round_results(state, results)
        # Should complete with "Unknown" for location
        assert mock_console.print_calls

    def test_escape_result_default_values(self, mock_console):
        """Test escape result with missing fields."""
        mock_console.install()
        # Minimal result dict - escaped=False is default
        result = {}
        print_escape_result(result)
        # Should complete with default values
        assert mock_console.clear_calls > 0
        assert mock_console.print_calls

    def test_lobby_with_all_player_states(self, mock_console, mock_game_state):
        """Test lobby with ready, not ready, and disconnected players."""
        mock_console.install()
        state = mock_game_state(
            game_id="test",
            players=[
                {"username": "Ready", "ready": True, "connected": True},
                {"username": "NotReady", "ready": False, "connected": True},
                {"username": "Gone", "ready": False, "connected": False},
            ]
        )
        print_lobby(state)
        # Should complete without error
        assert mock_console.print_calls

    def test_waiting_with_no_submitted(self, mock_console, mock_game_state):
        """Test waiting screen with no one submitted."""
        mock_console.install()
        state = mock_game_state(
            round_num=1,
            players=[
                {"player_id": "p1", "username": "Alice", "alive": True},
                {"player_id": "p2", "username": "Bob", "alive": True},
            ]
        )
        print_waiting_for_players(state, submitted=[])
        # Should complete showing waiting players
        assert mock_console.print_calls

    def test_waiting_handles_missing_player(self, mock_console, mock_game_state):
        """Test waiting screen handles player ID not found."""
        mock_console.install()
        state = mock_game_state(
            round_num=1,
            players=[{"player_id": "p1", "username": "Alice", "alive": True}]
        )
        # "p2" doesn't exist in players
        print_waiting_for_players(state, submitted=["p2"])
        # Should not crash, just skip the missing player
        assert mock_console.print_calls
