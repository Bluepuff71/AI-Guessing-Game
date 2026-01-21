"""Tests to verify the UI testing fixtures work correctly."""

import pytest
from client.state import ClientPhase


class TestMockUiInputs:
    """Tests for mock_ui_inputs fixture."""

    def test_mock_ui_inputs_select(self, mock_ui_inputs):
        """Test that mock_ui_inputs scripts questionary.select responses."""
        import questionary

        mock_ui_inputs(["Option A", "Option B"])

        # First call should return "Option A"
        result1 = questionary.select("Choose:", choices=["Option A", "Option B"]).ask()
        assert result1 == "Option A"

        # Second call should return "Option B"
        result2 = questionary.select("Choose:", choices=["Option A", "Option B"]).ask()
        assert result2 == "Option B"

    def test_mock_ui_inputs_text(self, mock_ui_inputs):
        """Test that mock_ui_inputs scripts questionary.text responses."""
        import questionary

        mock_ui_inputs(["Alice", "Bob"])

        result1 = questionary.text("Name:").ask()
        assert result1 == "Alice"

        result2 = questionary.text("Name:").ask()
        assert result2 == "Bob"

    def test_mock_ui_inputs_mixed(self, mock_ui_inputs):
        """Test mixed select and text responses."""
        import questionary

        mock_ui_inputs(["Option 1", "test_user", "Option 2"])

        result1 = questionary.select("Select:", choices=[]).ask()
        assert result1 == "Option 1"

        result2 = questionary.text("Username:").ask()
        assert result2 == "test_user"

        result3 = questionary.select("Select:", choices=[]).ask()
        assert result3 == "Option 2"

    def test_mock_ui_inputs_reset(self, mock_ui_inputs):
        """Test that responses can be reset."""
        import questionary

        mock_ui_inputs(["First"])
        result1 = questionary.select("", choices=[]).ask()
        assert result1 == "First"

        mock_ui_inputs(["Second", "Third"])
        result2 = questionary.select("", choices=[]).ask()
        assert result2 == "Second"
        result3 = questionary.select("", choices=[]).ask()
        assert result3 == "Third"

    def test_mock_ui_inputs_exhausted(self, mock_ui_inputs):
        """Test behavior when responses are exhausted."""
        import questionary

        mock_ui_inputs(["Only One"])
        result1 = questionary.select("", choices=[]).ask()
        assert result1 == "Only One"

        # Should return None when exhausted
        result2 = questionary.select("", choices=[]).ask()
        assert result2 is None


class TestMockNetwork:
    """Tests for mock_network fixture."""

    def test_mock_network_poll(self, mock_network):
        """Test that mock_network returns scripted poll responses."""
        responses = [
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "GAME_STATE", "data": {}},
        ]
        net = mock_network(responses)

        msg1 = net.poll()
        assert msg1["type"] == "CONNECTED"

        msg2 = net.poll()
        assert msg2["type"] == "SERVER_MESSAGE"
        assert msg2["message_type"] == "GAME_STATE"

        # Should return None when exhausted
        msg3 = net.poll()
        assert msg3 is None

    def test_mock_network_send(self, mock_network):
        """Test that mock_network records sent messages."""
        net = mock_network()

        net.send("LOCATION_CHOICE", {"location": "Store"})
        net.send("READY", {"ready": True})

        assert len(net.sent_messages) == 2
        assert net.sent_messages[0]["message_type"] == "LOCATION_CHOICE"
        assert net.sent_messages[0]["data"]["location"] == "Store"
        assert net.sent_messages[1]["message_type"] == "READY"

    def test_mock_network_start_stop(self, mock_network):
        """Test start and stop methods."""
        net = mock_network()

        result = net.start("ws://localhost:8765")
        assert result is True
        assert net._is_running is True

        net.stop()
        assert net._is_running is False

    def test_mock_network_add_responses(self, mock_network):
        """Test adding responses dynamically."""
        net = mock_network([{"type": "CONNECTED"}])

        msg1 = net.poll()
        assert msg1["type"] == "CONNECTED"

        # Add more responses
        net.add_responses([{"type": "SERVER_MESSAGE", "message_type": "NEW", "data": {}}])

        msg2 = net.poll()
        assert msg2["type"] == "SERVER_MESSAGE"
        assert msg2["message_type"] == "NEW"


class TestMockGameState:
    """Tests for mock_game_state fixture."""

    def test_mock_game_state_defaults(self, mock_game_state):
        """Test default values."""
        state = mock_game_state()

        assert state.connected is True
        assert state.phase == ClientPhase.MAIN_MENU
        assert state.round_num == 1
        assert state.game_id == "test_game"

    def test_mock_game_state_with_players(self, mock_game_state):
        """Test creating state with players."""
        state = mock_game_state(
            players=[
                {"username": "Alice", "points": 50, "alive": True},
                {"username": "Bob", "points": 30, "alive": False},
            ]
        )

        assert len(state.players) == 2
        alice = state.players["player_1"]
        assert alice.username == "Alice"
        assert alice.points == 50
        assert alice.alive is True

        bob = state.players["player_2"]
        assert bob.username == "Bob"
        assert bob.points == 30
        assert bob.alive is False

    def test_mock_game_state_with_locations(self, mock_game_state):
        """Test creating state with locations."""
        state = mock_game_state(
            locations=[
                {"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10},
                {"name": "Bank", "emoji": "B", "min_points": 10, "max_points": 20},
            ]
        )

        assert len(state.locations) == 2
        assert state.locations[0].name == "Store"
        assert state.locations[0].min_points == 5
        assert state.locations[1].name == "Bank"
        assert state.locations[1].max_points == 20

    def test_mock_game_state_phase(self, mock_game_state):
        """Test creating state with specific phase."""
        state = mock_game_state(phase=ClientPhase.CHOOSING, round_num=5)

        assert state.phase == ClientPhase.CHOOSING
        assert state.round_num == 5

    def test_mock_game_state_escape_options(self, mock_game_state):
        """Test creating state with escape options."""
        state = mock_game_state(
            phase=ClientPhase.ESCAPE,
            escape_options=[
                {"id": "hide1", "name": "Behind boxes", "type": "hide", "emoji": "H"},
                {"id": "run1", "name": "Back door", "type": "run", "emoji": "R"},
            ],
            caught_location="Store",
            caught_points=25,
        )

        assert state.phase == ClientPhase.ESCAPE
        assert len(state.escape_options) == 2
        assert state.caught_location == "Store"
        assert state.caught_points == 25

    def test_mock_game_state_local_player_ids(self, mock_game_state):
        """Test local player IDs are set correctly."""
        state = mock_game_state(
            players=[
                {"player_id": "p1", "username": "Alice"},
                {"player_id": "p2", "username": "Bob"},
            ],
            local_player_ids=["p1", "p2"],
        )

        assert state.local_player_ids == ["p1", "p2"]

    def test_mock_game_state_default_local_player(self, mock_game_state):
        """Test default local player is first player."""
        state = mock_game_state(
            players=[
                {"player_id": "p1", "username": "Alice"},
                {"player_id": "p2", "username": "Bob"},
            ]
        )

        assert state.local_player_ids == ["p1"]


class TestMockConsole:
    """Tests for mock_console fixture."""

    def test_mock_console_captures_output(self, mock_console):
        """Test that mock_console captures print output."""
        mock_console.install()

        import client.ui as ui

        ui.console.print("Hello, World!")
        ui.console.print("Test message")

        assert "Hello, World!" in mock_console.output
        assert "Test message" in mock_console.output

    def test_mock_console_clear_method(self, mock_console):
        """Test mock_console clear method."""
        mock_console.install()

        import client.ui as ui

        ui.console.print("Before clear")
        assert "Before clear" in mock_console.output

        mock_console.clear()
        assert mock_console.output == ""
        assert len(mock_console.print_calls) == 0

    def test_mock_console_tracks_clear_calls(self, mock_console):
        """Test that mock_console tracks console.clear() calls."""
        mock_console.install()

        import client.ui as ui

        assert mock_console.clear_calls == 0
        ui.console.clear()
        assert mock_console.clear_calls == 1
        ui.console.clear()
        assert mock_console.clear_calls == 2

    def test_mock_console_input_responses(self, mock_console):
        """Test mock_console input responses."""
        mock_console.install()
        mock_console.set_input_responses(["response1", "response2"])

        import client.ui as ui

        result1 = ui.console.input("Prompt: ")
        assert result1 == "response1"

        result2 = ui.console.input("Prompt: ")
        assert result2 == "response2"

    def test_mock_console_print_calls(self, mock_console):
        """Test that mock_console tracks print call details."""
        mock_console.install()

        import client.ui as ui

        ui.console.print("Test", style="bold")

        assert len(mock_console.print_calls) == 1
        assert mock_console.print_calls[0]["args"] == ("Test",)
        assert mock_console.print_calls[0]["kwargs"] == {"style": "bold"}
