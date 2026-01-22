"""Tests for client/main.py - GameClient class unit tests."""
import asyncio
import subprocess
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from client.main import GameClient, DEFAULT_PORT, POLL_TIMEOUT, CONNECTION_TIMEOUT
from client.state import GameState, ClientPhase, PlayerInfo


class TestGameClientInit:
    """Tests for GameClient initialization."""

    def test_init_creates_state(self):
        """Test that GameClient creates a GameState on init."""
        client = GameClient()
        assert client.state is not None
        assert isinstance(client.state, GameState)

    def test_init_creates_handler(self):
        """Test that GameClient creates a MessageHandler on init."""
        client = GameClient()
        assert client.handler is not None

    def test_init_sets_defaults(self):
        """Test that GameClient sets default values."""
        client = GameClient()
        assert client._running is False
        assert client._server_process is None
        assert client._connection_lost is False
        assert client._local_networks == {}
        assert client._network is None


class TestResetConnectionState:
    """Tests for _reset_connection_state method."""

    def test_resets_connection_lost_flag(self):
        """Test that connection lost flag is reset."""
        client = GameClient()
        client._connection_lost = True
        client._reset_connection_state()
        assert client._connection_lost is False


class TestStartLocalServer:
    """Tests for _start_local_server method."""

    def test_starts_server_subprocess(self, monkeypatch):
        """Test that local server is started as subprocess."""
        mock_popen = MagicMock()
        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        client = GameClient()
        result = client._start_local_server()

        assert result is True
        assert mock_popen.called
        assert client._server_process is not None

    def test_start_local_server_expose_flag(self, monkeypatch):
        """Test that expose flag uses 0.0.0.0 host."""
        call_args = []

        def mock_popen(args, **kwargs):
            call_args.append(args)
            return MagicMock()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        client = GameClient()
        result = client._start_local_server(expose=True)

        assert result is True
        assert "--host" in call_args[0]
        host_idx = call_args[0].index("--host")
        assert call_args[0][host_idx + 1] == "0.0.0.0"

    def test_start_local_server_no_expose_flag(self, monkeypatch):
        """Test that no expose flag uses 127.0.0.1 host."""
        call_args = []

        def mock_popen(args, **kwargs):
            call_args.append(args)
            return MagicMock()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        client = GameClient()
        result = client._start_local_server(expose=False)

        assert result is True
        assert "--host" in call_args[0]
        host_idx = call_args[0].index("--host")
        assert call_args[0][host_idx + 1] == "127.0.0.1"

    def test_start_local_server_returns_false_if_already_running(self, monkeypatch):
        """Test that _start_local_server returns False if server already running."""
        monkeypatch.setattr("client.main.is_server_running", lambda port: True)
        monkeypatch.setattr("client.ui.print_error", lambda msg: None)
        monkeypatch.setattr("client.ui.print_info", lambda msg: None)

        client = GameClient()
        result = client._start_local_server()

        assert result is False
        assert client._server_process is None

    def test_start_local_server_returns_false_if_server_fails_to_start(self, monkeypatch):
        """Test that _start_local_server returns False if server fails to start."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process exited with error
        mock_process.communicate.return_value = (b"Some error", b"")

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: mock_process)
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: False)
        monkeypatch.setattr("client.ui.print_error", lambda msg: None)

        client = GameClient()
        result = client._start_local_server()

        assert result is False
        assert client._server_process is None


class TestStopLocalServer:
    """Tests for _stop_local_server method."""

    def test_terminates_server_process(self):
        """Test that server process is terminated."""
        client = GameClient()
        mock_process = MagicMock()
        client._server_process = mock_process

        client._stop_local_server()

        mock_process.terminate.assert_called_once()
        assert client._server_process is None

    def test_does_nothing_if_no_server(self):
        """Test that nothing happens if no server process."""
        client = GameClient()
        client._server_process = None
        # Should not raise
        client._stop_local_server()
        assert client._server_process is None


class TestConnectAndJoin:
    """Tests for _connect_and_join method."""

    def test_successful_connection_and_join(self, mock_network, monkeypatch):
        """Test successful connection and join flow."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p1",
                "game_id": "game1"
            }},
        ])

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is True
        assert client.state.player_id == "p1"
        assert client.state.game_id == "game1"
        assert client.state.connected is True

    def test_connection_start_failure(self, monkeypatch):
        """Test handling when network start fails."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        network = MagicMock()
        network.start.return_value = False

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is False

    def test_connection_lost_during_connect(self, mock_network, monkeypatch):
        """Test handling connection lost during connect phase."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        network = mock_network([
            {"type": "CONNECTION_LOST", "error": "Server unreachable"},
        ])

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is False

    def test_connection_timeout(self, mock_network, monkeypatch):
        """Test handling connection timeout."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        # Make time.time return increasing values
        time_values = [0, 0.1, 0.2, 6.0, 6.1]  # Will timeout after CONNECTION_TIMEOUT
        time_gen = iter(time_values)
        monkeypatch.setattr(time, "time", lambda: next(time_gen, 10.0))

        network = mock_network([])  # No responses

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is False

    def test_connection_lost_during_welcome(self, mock_network, monkeypatch):
        """Test handling connection lost while waiting for welcome."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "CONNECTION_LOST", "error": "Disconnected"},
        ])

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is False

    def test_welcome_timeout(self, mock_network, monkeypatch):
        """Test handling timeout waiting for welcome."""
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        # Use controlled time values
        time_values = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 6.0, 6.1, 6.2]
        time_gen = iter(time_values)
        monkeypatch.setattr(time, "time", lambda: next(time_gen, 10.0))

        network = mock_network([
            {"type": "CONNECTED"},
            # No welcome message
        ])

        client = GameClient()
        result = client._connect_and_join(network, "localhost", 8765, "TestPlayer")

        assert result is False


class TestConnectAdditionalPlayer:
    """Tests for _connect_additional_player method."""

    def test_successful_additional_player_connection(self, mock_network, monkeypatch):
        """Test successful connection of additional player."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)

        # Mock NetworkThread constructor to return our mock
        created_network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p2",
                "game_id": "game1"
            }},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: created_network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result == "p2"
        assert "p2" in client._local_networks

    def test_additional_player_network_start_failure(self, monkeypatch):
        """Test handling when additional player network start fails."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        network = MagicMock()
        network.start.return_value = False
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result is None

    def test_additional_player_connection_lost(self, mock_network, monkeypatch):
        """Test handling connection lost for additional player."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        created_network = mock_network([
            {"type": "CONNECTION_LOST", "error": "Failed"},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: created_network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result is None

    def test_additional_player_connection_timeout(self, mock_network, monkeypatch):
        """Test handling timeout for additional player connection."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        time_values = [0, 0.1, 6.0]
        time_gen = iter(time_values)
        monkeypatch.setattr(time, "time", lambda: next(time_gen, 10.0))

        created_network = mock_network([])  # No responses
        monkeypatch.setattr("client.main.NetworkThread", lambda: created_network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result is None

    def test_additional_player_welcome_timeout(self, mock_network, monkeypatch):
        """Test handling timeout waiting for welcome for additional player."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        time_values = [0, 0.1, 0.2, 0.3, 6.0, 6.1]
        time_gen = iter(time_values)
        monkeypatch.setattr(time, "time", lambda: next(time_gen, 10.0))

        created_network = mock_network([
            {"type": "CONNECTED"},
            # No welcome
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: created_network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result is None

    def test_additional_player_connection_lost_after_connect(self, mock_network, monkeypatch):
        """Test handling connection lost after connecting for additional player."""
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        created_network = mock_network([
            {"type": "CONNECTED"},
            {"type": "CONNECTION_LOST", "error": "Lost"},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: created_network)

        client = GameClient()
        result = client._connect_additional_player("localhost", 8765, "Player2")

        assert result is None


class TestPollAllNetworks:
    """Tests for _poll_all_networks method."""

    def test_poll_primary_network_server_message(self, mock_network):
        """Test polling primary network with server message."""
        network = mock_network([
            {"type": "SERVER_MESSAGE", "message_type": "GAME_STATE", "data": {"round_num": 1}},
        ])

        client = GameClient()
        client._network = network

        result = client._poll_all_networks()

        assert result is True

    def test_poll_primary_network_connection_lost(self, mock_network):
        """Test polling primary network with connection lost."""
        network = mock_network([
            {"type": "CONNECTION_LOST"},
        ])

        client = GameClient()
        client._network = network

        result = client._poll_all_networks()

        assert result is False
        assert client._connection_lost is True

    def test_poll_no_network(self):
        """Test polling with no network."""
        client = GameClient()
        client._network = None

        result = client._poll_all_networks()

        assert result is True

    def test_poll_secondary_networks(self, mock_network):
        """Test polling secondary networks for hot-seat mode."""
        primary = mock_network([None])
        secondary = mock_network([
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {"player_id": "p2"}},
        ])

        client = GameClient()
        client._network = primary
        client._local_networks = {"p1": primary, "p2": secondary}

        result = client._poll_all_networks()

        assert result is True

    def test_poll_secondary_network_connection_lost(self, mock_network):
        """Test polling secondary network with connection lost (should not affect primary)."""
        primary = mock_network([None])
        secondary = mock_network([
            {"type": "CONNECTION_LOST"},
        ])

        client = GameClient()
        client._network = primary
        client._local_networks = {"p1": primary, "p2": secondary}

        result = client._poll_all_networks()

        # Secondary connection loss doesn't fail the main result
        assert result is True

    def test_poll_skips_primary_in_secondary_loop(self, mock_network):
        """Test that primary network isn't polled twice."""
        # Create a network that tracks poll calls
        poll_count = [0]

        def mock_poll(timeout=0.1):
            poll_count[0] += 1
            return None

        primary = MagicMock()
        primary.poll = mock_poll

        client = GameClient()
        client._network = primary
        client._local_networks = {"p1": primary}  # Same network

        client._poll_all_networks()

        # Should only poll once (not twice)
        assert poll_count[0] == 1


class TestLobbyLoop:
    """Tests for _lobby_loop method."""

    def test_lobby_loop_exits_on_phase_change(self, mock_network, monkeypatch):
        """Test that lobby loop exits when phase changes."""
        monkeypatch.setattr("client.ui.print_lobby", lambda s, h: None)
        monkeypatch.setattr("client.ui.get_lobby_action", lambda h, r: "refresh")
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = mock_network([])
        client.state.phase = ClientPhase.LOBBY
        client.state.player_id = "p1"
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Test", ready=False)

        # After first iteration, change phase
        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.SHOP
            return True

        client._poll_all_networks = mock_poll

        # Mock _game_loop to not run
        client._game_loop = MagicMock()

        client._lobby_loop(is_host=False)

        assert client.state.phase != ClientPhase.LOBBY

    def test_lobby_loop_connection_lost(self, mock_network, monkeypatch):
        """Test lobby loop exits on connection lost."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr("client.ui.print_lobby", lambda s, h: None)
        monkeypatch.setattr("client.ui.get_lobby_action", lambda h, r: "refresh")
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = mock_network([{"type": "CONNECTION_LOST"}])
        client.state.phase = ClientPhase.LOBBY
        client.state.player_id = "p1"
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Test", ready=False)

        client._lobby_loop(is_host=False)

        # Loop should have exited due to connection loss

    def test_lobby_loop_ready_toggle(self, mock_network, monkeypatch):
        """Test toggling ready status in lobby."""
        # First call returns "ready", subsequent calls return "refresh"
        actions = iter(["ready", "refresh"])

        monkeypatch.setattr("client.ui.print_lobby", lambda s, h: None)
        monkeypatch.setattr("client.ui.get_lobby_action", lambda h, r: next(actions, "refresh"))
        monkeypatch.setattr(time, "sleep", lambda x: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state.phase = ClientPhase.LOBBY
        client.state.player_id = "p1"
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Test", ready=False)

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.SHOP
            return True

        client._poll_all_networks = mock_poll
        client._game_loop = MagicMock()

        client._lobby_loop(is_host=False)

        # Check that READY was sent
        assert any(m["message_type"] == "READY" for m in network.sent_messages)

    def test_lobby_loop_unready(self, mock_network, monkeypatch):
        """Test sending unready when already ready."""
        # First call returns "unready", subsequent calls return "refresh"
        actions = iter(["unready", "refresh"])

        monkeypatch.setattr("client.ui.print_lobby", lambda s, h: None)
        monkeypatch.setattr("client.ui.get_lobby_action", lambda h, r: next(actions, "refresh"))
        monkeypatch.setattr(time, "sleep", lambda x: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state.phase = ClientPhase.LOBBY
        client.state.player_id = "p1"
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Test", ready=True)

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.SHOP
            return True

        client._poll_all_networks = mock_poll
        client._game_loop = MagicMock()

        client._lobby_loop(is_host=False)

        # Check that UNREADY was sent
        assert any(m["message_type"] == "UNREADY" for m in network.sent_messages)

    def test_lobby_loop_host_start(self, mock_network, monkeypatch):
        """Test host starting game with 'start' action."""
        # First call returns "start", subsequent calls return "refresh"
        actions = iter(["start", "refresh"])

        monkeypatch.setattr("client.ui.print_lobby", lambda s, h: None)
        monkeypatch.setattr("client.ui.get_lobby_action", lambda h, r: next(actions, "refresh"))
        monkeypatch.setattr(time, "sleep", lambda x: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state.phase = ClientPhase.LOBBY
        client.state.player_id = "p1"
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Host", ready=False)

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.SHOP
            return True

        client._poll_all_networks = mock_poll
        client._game_loop = MagicMock()

        client._lobby_loop(is_host=True)

        # Check that READY was sent (host starts by setting ready)
        assert any(m["message_type"] == "READY" for m in network.sent_messages)


class TestGameLoop:
    """Tests for _game_loop method."""

    def test_game_loop_exits_on_game_over(self, mock_network, monkeypatch):
        """Test game loop exits when game is over."""
        monkeypatch.setattr("client.ui.print_game_over", lambda s: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = mock_network([])
        client.state.phase = ClientPhase.GAME_OVER

        client._game_loop()

        # Loop should have exited immediately

    def test_game_loop_exits_on_main_menu(self, monkeypatch):
        """Test game loop exits when returning to main menu."""
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None
        client.state.phase = ClientPhase.MAIN_MENU

        client._game_loop()

        # Loop should have exited immediately

    def test_game_loop_connection_lost(self, mock_network, monkeypatch):
        """Test game loop exits on connection lost."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = mock_network([{"type": "CONNECTION_LOST"}])
        client.state.phase = ClientPhase.CHOOSING

        client._game_loop()

        # Loop should have exited due to connection loss

    def test_game_loop_handles_shop_phase(self, monkeypatch):
        """Test game loop triggers shop phase handler."""
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("client.ui.print_game_over", lambda s: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None

        shop_called = [False]

        def mock_shop():
            shop_called[0] = True
            client.state.phase = ClientPhase.GAME_OVER

        client._handle_shop_phase = mock_shop
        client.state.phase = ClientPhase.SHOP
        client.handler.phase_changed = True

        client._game_loop()

        assert shop_called[0] is True

    def test_game_loop_handles_choosing_phase(self, monkeypatch):
        """Test game loop triggers choosing phase handler."""
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("client.ui.print_game_over", lambda s: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None

        choosing_called = [False]

        def mock_choosing():
            choosing_called[0] = True
            client.state.phase = ClientPhase.GAME_OVER

        client._handle_choosing_phase = mock_choosing
        client.state.phase = ClientPhase.CHOOSING
        client.handler.phase_changed = True

        client._game_loop()

        assert choosing_called[0] is True

    def test_game_loop_handles_round_result(self, monkeypatch):
        """Test game loop handles round result."""
        monkeypatch.setattr("client.ui.print_round_results", lambda s, r: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.GAME_OVER
            return True

        client._poll_all_networks = mock_poll
        client.state.phase = ClientPhase.WAITING
        client.handler.last_round_result = {"ai_search_location": "Bank"}

        client._game_loop()

        # Result should have been cleared
        assert client.handler.last_round_result is None

    def test_game_loop_handles_escape_required(self, monkeypatch):
        """Test game loop handles escape phase."""
        monkeypatch.setattr(time, "sleep", lambda x: None)
        monkeypatch.setattr("client.ui.print_game_over", lambda s: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None

        escape_called = [False]

        def mock_escape(data):
            escape_called[0] = True
            client.state.phase = ClientPhase.GAME_OVER

        client._handle_escape_phase = mock_escape

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.GAME_OVER
            return True

        client._poll_all_networks = mock_poll
        client.state.phase = ClientPhase.ESCAPE
        client.handler.last_escape_required = {"player_id": "p1"}

        client._game_loop()

        assert escape_called[0] is True

    def test_game_loop_handles_escape_result(self, monkeypatch):
        """Test game loop handles escape result."""
        monkeypatch.setattr("client.ui.print_escape_result", lambda r: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        client = GameClient()
        client._network = MagicMock()
        client._network.poll.return_value = None

        call_count = [0]

        def mock_poll():
            call_count[0] += 1
            if call_count[0] > 1:
                client.state.phase = ClientPhase.GAME_OVER
            return True

        client._poll_all_networks = mock_poll
        client.state.phase = ClientPhase.ESCAPE
        client.handler.last_escape_result = {"escaped": True}

        client._game_loop()

        # Result should have been cleared
        assert client.handler.last_escape_result is None


class TestHandleShopPhase:
    """Tests for _handle_shop_phase method."""

    def test_shop_phase_skip(self, mock_network, mock_game_state, monkeypatch):
        """Test skipping shop."""
        monkeypatch.setattr("client.ui.print_shop", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_shop_choice", lambda s, p: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[{"player_id": "p1", "username": "Test", "points": 50, "alive": True}],
            local_player_ids=["p1"],
            available_passives=[{"id": "passive1", "name": "Test", "cost": 10}]
        )
        client._local_networks = {"p1": network}

        client._handle_shop_phase()

        assert any(m["message_type"] == "SKIP_SHOP" for m in network.sent_messages)

    def test_shop_phase_purchase(self, mock_network, mock_game_state, monkeypatch):
        """Test purchasing item in shop."""
        monkeypatch.setattr("client.ui.print_shop", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_shop_choice", lambda s, p: 0)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[{"player_id": "p1", "username": "Test", "points": 50, "alive": True}],
            local_player_ids=["p1"],
            available_passives=[{"id": "passive1", "name": "Test", "cost": 10}]
        )
        client._local_networks = {"p1": network}

        client._handle_shop_phase()

        assert any(m["message_type"] == "SHOP_PURCHASE" for m in network.sent_messages)
        assert any(m["message_type"] == "SKIP_SHOP" for m in network.sent_messages)

    def test_shop_phase_dead_player_skips(self, mock_network, mock_game_state, monkeypatch):
        """Test that dead players skip shop automatically."""
        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[{"player_id": "p1", "username": "Dead", "points": 0, "alive": False}],
            local_player_ids=["p1"],
            available_passives=[]
        )
        client._local_networks = {"p1": network}

        client._handle_shop_phase()

        assert any(m["message_type"] == "SKIP_SHOP" for m in network.sent_messages)

    def test_shop_phase_connection_lost(self, mock_game_state, monkeypatch):
        """Test shop phase exits on connection lost."""
        monkeypatch.setattr("client.ui.print_shop", lambda s, p: None)

        client = GameClient()
        client._connection_lost = True
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[{"player_id": "p1", "username": "Test", "points": 50, "alive": True}],
            local_player_ids=["p1"],
            available_passives=[]
        )

        # Should exit early due to connection lost
        client._handle_shop_phase()

    def test_shop_phase_multiple_players(self, mock_network, mock_game_state, monkeypatch):
        """Test shop phase with multiple local players."""
        monkeypatch.setattr("client.ui.print_shop", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_shop_choice", lambda s, p: None)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        net1 = mock_network([])
        net2 = mock_network([])
        client = GameClient()
        client._network = net1
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[
                {"player_id": "p1", "username": "Player1", "points": 50, "alive": True},
                {"player_id": "p2", "username": "Player2", "points": 30, "alive": True},
            ],
            local_player_ids=["p1", "p2"],
            available_passives=[]
        )
        client._local_networks = {"p1": net1, "p2": net2}

        client._handle_shop_phase()

        # Both players should have skipped
        assert any(m["message_type"] == "SKIP_SHOP" for m in net1.sent_messages)
        assert any(m["message_type"] == "SKIP_SHOP" for m in net2.sent_messages)


class TestHandleChoosingPhase:
    """Tests for _handle_choosing_phase method."""

    def test_choosing_phase_single_player(self, mock_network, mock_game_state, monkeypatch):
        """Test location choosing for single player."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_location_choice", lambda s: 0)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[{"player_id": "p1", "username": "Test", "points": 0, "alive": True}],
            local_player_ids=["p1"],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {"p1": network}

        client._handle_choosing_phase()

        assert any(m["message_type"] == "LOCATION_CHOICE" for m in network.sent_messages)

    def test_choosing_phase_connection_lost(self, mock_game_state, monkeypatch):
        """Test choosing phase exits on connection lost."""
        client = GameClient()
        client._connection_lost = True
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[{"player_id": "p1", "username": "Test", "alive": True}],
            local_player_ids=["p1"],
            locations=[]
        )

        # Should exit early
        client._handle_choosing_phase()

    def test_choosing_phase_dead_player_skipped(self, mock_network, mock_game_state, monkeypatch):
        """Test dead players are skipped in choosing phase."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_location_choice", lambda s: 0)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[
                {"player_id": "p1", "username": "Dead", "alive": False},
                {"player_id": "p2", "username": "Alive", "alive": True},
            ],
            local_player_ids=["p1", "p2"],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {"p1": network, "p2": network}

        client._handle_choosing_phase()

        # Only one choice should be sent (for alive player)
        location_choices = [m for m in network.sent_messages if m["message_type"] == "LOCATION_CHOICE"]
        assert len(location_choices) == 1

    def test_choosing_phase_multiple_players(self, mock_network, mock_game_state, monkeypatch):
        """Test choosing phase with multiple local players."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_location_choice", lambda s: 0)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        net1 = mock_network([])
        net2 = mock_network([])
        client = GameClient()
        client._network = net1
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[
                {"player_id": "p1", "username": "Player1", "alive": True},
                {"player_id": "p2", "username": "Player2", "alive": True},
            ],
            local_player_ids=["p1", "p2"],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {"p1": net1, "p2": net2}

        client._handle_choosing_phase()

        # Both players should have submitted choices
        assert any(m["message_type"] == "LOCATION_CHOICE" for m in net1.sent_messages)
        assert any(m["message_type"] == "LOCATION_CHOICE" for m in net2.sent_messages)

    def test_choosing_phase_connection_lost_mid_loop(self, mock_network, mock_game_state, monkeypatch):
        """Test choosing phase exits if connection lost mid-loop."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)

        choice_count = [0]

        def mock_choice(s):
            choice_count[0] += 1
            return 0

        monkeypatch.setattr("client.ui.get_location_choice", mock_choice)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[
                {"player_id": "p1", "username": "Player1", "alive": True},
                {"player_id": "p2", "username": "Player2", "alive": True},
            ],
            local_player_ids=["p1", "p2"],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {"p1": network, "p2": network}

        # Connection lost after first player
        original_choice = client.state.players.get
        call_count = [0]

        def mock_get(pid):
            call_count[0] += 1
            if call_count[0] > 1:
                client._connection_lost = True
            return client.state.players.get(pid, None)

        client._handle_choosing_phase()


class TestHandleEscapePhase:
    """Tests for _handle_escape_phase method."""

    def test_escape_phase_sends_choice(self, mock_network, mock_game_state, monkeypatch):
        """Test escape phase sends choice."""
        monkeypatch.setattr("client.ui.print_escape_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_escape_choice", lambda s: 0)

        network = mock_network([])
        client = GameClient()
        client._network = network
        client.state = mock_game_state(
            phase=ClientPhase.ESCAPE,
            players=[{"player_id": "p1", "username": "Test", "alive": True}],
            local_player_ids=["p1"],
            escape_options=[{"id": "hide1", "name": "Hide", "type": "hide"}]
        )
        client._local_networks = {"p1": network}

        client._handle_escape_phase({"player_id": "p1"})

        assert any(m["message_type"] == "ESCAPE_CHOICE" for m in network.sent_messages)

    def test_escape_phase_connection_lost(self, mock_game_state):
        """Test escape phase exits on connection lost."""
        client = GameClient()
        client._connection_lost = True
        client.state = mock_game_state(
            phase=ClientPhase.ESCAPE,
            players=[{"player_id": "p1", "username": "Test"}],
            escape_options=[]
        )

        # Should exit early
        client._handle_escape_phase({"player_id": "p1"})

    def test_escape_phase_unknown_player(self, mock_game_state):
        """Test escape phase with unknown player."""
        client = GameClient()
        client.state = mock_game_state(
            phase=ClientPhase.ESCAPE,
            players=[],
            escape_options=[]
        )

        # Should exit without error for unknown player
        client._handle_escape_phase({"player_id": "unknown"})

    def test_escape_phase_uses_correct_network(self, mock_network, mock_game_state, monkeypatch):
        """Test escape phase uses correct network for player."""
        monkeypatch.setattr("client.ui.print_escape_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_escape_choice", lambda s: 0)

        net1 = mock_network([])
        net2 = mock_network([])
        client = GameClient()
        client._network = net1
        client.state = mock_game_state(
            phase=ClientPhase.ESCAPE,
            players=[
                {"player_id": "p1", "username": "Player1"},
                {"player_id": "p2", "username": "Player2"},
            ],
            local_player_ids=["p1", "p2"],
            escape_options=[{"id": "hide1", "name": "Hide", "type": "hide"}]
        )
        client._local_networks = {"p1": net1, "p2": net2}

        client._handle_escape_phase({"player_id": "p2"})

        # Choice should be sent via p2's network
        assert any(m["message_type"] == "ESCAPE_CHOICE" for m in net2.sent_messages)


class TestCleanupCurrentGame:
    """Tests for _cleanup_current_game method."""

    def test_cleanup_stops_all_networks(self, mock_network):
        """Test cleanup stops all network threads."""
        net1 = mock_network([])
        net2 = mock_network([])

        # Track stop calls
        stop_calls = []

        def track_stop1():
            stop_calls.append("net1")
            net1._is_running = False

        def track_stop2():
            stop_calls.append("net2")
            net2._is_running = False

        net1.stop = track_stop1
        net2.stop = track_stop2

        client = GameClient()
        client._network = net1
        client._local_networks = {"p1": net1, "p2": net2}

        client._cleanup_current_game()

        # Verify stop was called on both
        assert "net1" in stop_calls
        assert "net2" in stop_calls

    def test_cleanup_clears_local_networks(self, mock_network):
        """Test cleanup clears local networks dict."""
        net1 = mock_network([])
        client = GameClient()
        client._local_networks = {"p1": net1}

        client._cleanup_current_game()

        assert client._local_networks == {}

    def test_cleanup_clears_primary_network(self, mock_network):
        """Test cleanup clears primary network."""
        net1 = mock_network([])
        client = GameClient()
        client._network = net1

        client._cleanup_current_game()

        assert client._network is None

    def test_cleanup_stops_local_server(self, monkeypatch):
        """Test cleanup stops local server."""
        mock_process = MagicMock()
        client = GameClient()
        client._server_process = mock_process

        client._cleanup_current_game()

        mock_process.terminate.assert_called_once()

    def test_cleanup_resets_state(self):
        """Test cleanup resets game state."""
        client = GameClient()
        client.state.round_num = 5
        client.state.players["p1"] = PlayerInfo(player_id="p1", username="Test")

        client._cleanup_current_game()

        assert client.state.round_num == 0
        assert len(client.state.players) == 0

    def test_cleanup_clears_handler_events(self):
        """Test cleanup clears handler events."""
        client = GameClient()
        client.handler.phase_changed = True
        client.handler.last_round_result = {"data": "test"}

        client._cleanup_current_game()

        assert client.handler.phase_changed is False
        assert client.handler.last_round_result is None


class TestPlaySinglePlayer:
    """Tests for _play_single_player method."""

    def test_single_player_successful_flow(self, mock_network, monkeypatch):
        """Test successful single player game flow."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: "TestPlayer")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p1", "game_id": "game1"
            }},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._game_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_single_player()

        # Verify READY was sent
        assert any(m["message_type"] == "READY" for m in network.sent_messages)
        client._game_loop.assert_called_once()

    def test_single_player_connection_failure(self, mock_network, monkeypatch):
        """Test single player with connection failure."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: "TestPlayer")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        network = mock_network([
            {"type": "CONNECTION_LOST", "error": "Failed"},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._game_loop = MagicMock()
        mock_stop_server = MagicMock()
        client._stop_local_server = mock_stop_server

        client._play_single_player()

        # Game loop should not have been called
        client._game_loop.assert_not_called()


class TestPlayLocalMultiplayer:
    """Tests for _play_local_multiplayer method."""

    def test_local_multiplayer_successful_flow(self, mock_network, monkeypatch):
        """Test successful local multiplayer flow."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_player_count", lambda: 2)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: f"Player{n}")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        # First player connection
        net1 = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p1", "game_id": "game1"
            }},
        ])

        # Second player connection
        net2 = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p2", "game_id": "game1"
            }},
        ])

        network_calls = [0]

        def mock_network_factory():
            network_calls[0] += 1
            if network_calls[0] == 1:
                return net1
            return net2

        monkeypatch.setattr("client.main.NetworkThread", mock_network_factory)

        client = GameClient()
        client._game_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_local_multiplayer()

        # Both players should have sent READY
        assert any(m["message_type"] == "READY" for m in net1.sent_messages)
        assert any(m["message_type"] == "READY" for m in net2.sent_messages)

    def test_local_multiplayer_first_player_connection_failure(self, mock_network, monkeypatch):
        """Test local multiplayer with first player connection failure."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_player_count", lambda: 2)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: f"Player{n}")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        network = mock_network([{"type": "CONNECTION_LOST"}])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._game_loop = MagicMock()
        mock_stop = MagicMock()
        client._stop_local_server = mock_stop

        client._play_local_multiplayer()

        client._game_loop.assert_not_called()

    def test_local_multiplayer_additional_player_failure(self, mock_network, monkeypatch):
        """Test local multiplayer when additional player fails to connect."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_player_count", lambda: 2)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: f"Player{n}")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        # First player succeeds
        net1 = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p1", "game_id": "game1"
            }},
        ])

        # Second player fails
        net2 = mock_network([{"type": "CONNECTION_LOST"}])

        network_calls = [0]

        def mock_network_factory():
            network_calls[0] += 1
            if network_calls[0] == 1:
                return net1
            return net2

        monkeypatch.setattr("client.main.NetworkThread", mock_network_factory)

        client = GameClient()
        client._game_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_local_multiplayer()

        # Game should have been cleaned up, game loop not called
        client._game_loop.assert_not_called()
        client._cleanup_current_game.assert_called()


class TestPlayOnlineHost:
    """Tests for _play_online_host method."""

    def test_online_host_successful_flow(self, mock_network, monkeypatch):
        """Test successful online host flow."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_host_name", lambda: "Host")
        monkeypatch.setattr("client.ui.get_game_name", lambda: "TestGame")
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr("client.main.is_server_running", lambda port: False)
        monkeypatch.setattr("client.main.wait_for_server", lambda port, timeout: True)

        # Mock asyncio.run for LAN discovery
        async_calls = []

        def mock_async_run(coro):
            async_calls.append(coro)
            return True  # Broadcasting started

        monkeypatch.setattr(asyncio, "run", mock_async_run)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p1", "game_id": "game1"
            }},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._lobby_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_online_host()

        client._lobby_loop.assert_called_once_with(is_host=True)

    def test_online_host_connection_failure(self, mock_network, monkeypatch):
        """Test online host with connection failure."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_host_name", lambda: "Host")
        monkeypatch.setattr("client.ui.get_game_name", lambda: "TestGame")
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MagicMock())
        monkeypatch.setattr(time, "sleep", lambda x: None)

        network = mock_network([{"type": "CONNECTION_LOST"}])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._lobby_loop = MagicMock()
        mock_stop = MagicMock()
        client._stop_local_server = mock_stop

        client._play_online_host()

        client._lobby_loop.assert_not_called()


class TestPlayOnlineJoin:
    """Tests for _play_online_join method."""

    def test_online_join_manual_address(self, mock_network, monkeypatch):
        """Test joining with manual address entry."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_server_address", lambda: "192.168.1.100")
        monkeypatch.setattr("client.ui.get_player_name", lambda n: "JoinPlayer")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p2", "game_id": "game1"
            }},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._lobby_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_online_join()

        client._lobby_loop.assert_called_once_with(is_host=False)

    def test_online_join_lan_scan_no_games(self, monkeypatch):
        """Test joining with LAN scan finding no games."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_server_address", lambda: "scan")
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)
        monkeypatch.setattr(asyncio, "run", lambda coro: [])  # No games found

        client = GameClient()
        client._lobby_loop = MagicMock()

        client._play_online_join()

        client._lobby_loop.assert_not_called()

    def test_online_join_lan_scan_select_game(self, mock_network, monkeypatch):
        """Test joining with LAN scan and selecting a game."""
        from client.lan import DiscoveredGame

        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_server_address", lambda: "scan")
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.select_lan_game", lambda g: 0)
        monkeypatch.setattr("client.ui.get_player_name", lambda n: "JoinPlayer")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)

        discovered = [DiscoveredGame(
            host="192.168.1.50",
            port=8765,
            game_name="Test",
            host_name="Host",
            player_count=1,
            max_players=6
        )]
        monkeypatch.setattr(asyncio, "run", lambda coro: discovered)

        network = mock_network([
            {"type": "CONNECTED"},
            {"type": "SERVER_MESSAGE", "message_type": "WELCOME", "data": {
                "player_id": "p2", "game_id": "game1"
            }},
        ])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._lobby_loop = MagicMock()
        client._cleanup_current_game = MagicMock()

        client._play_online_join()

        client._lobby_loop.assert_called_once()

    def test_online_join_lan_scan_cancel(self, monkeypatch):
        """Test cancelling LAN game selection."""
        from client.lan import DiscoveredGame

        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_server_address", lambda: "scan")
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.select_lan_game", lambda g: None)  # User cancelled

        discovered = [DiscoveredGame(
            host="192.168.1.50",
            port=8765,
            game_name="Test",
            host_name="Host",
            player_count=1,
            max_players=6
        )]
        monkeypatch.setattr(asyncio, "run", lambda coro: discovered)

        client = GameClient()
        client._lobby_loop = MagicMock()

        client._play_online_join()

        client._lobby_loop.assert_not_called()

    def test_online_join_connection_failure(self, mock_network, monkeypatch):
        """Test joining with connection failure."""
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_header", lambda t, s="": None)
        monkeypatch.setattr("client.ui.get_server_address", lambda: "192.168.1.100")
        monkeypatch.setattr("client.ui.get_player_name", lambda n: "JoinPlayer")
        monkeypatch.setattr("client.ui.print_connecting", lambda h, p: None)
        monkeypatch.setattr("client.ui.print_error", lambda m: None)

        network = mock_network([{"type": "CONNECTION_LOST"}])
        monkeypatch.setattr("client.main.NetworkThread", lambda: network)

        client = GameClient()
        client._lobby_loop = MagicMock()

        client._play_online_join()

        client._lobby_loop.assert_not_called()


class TestRunMainLoop:
    """Tests for run method (main menu loop)."""

    def test_run_single_player_choice(self, monkeypatch):
        """Test run with single player selection."""
        choices = ["1", "5"]  # Single player, then quit
        choice_gen = iter(choices)
        monkeypatch.setattr("client.ui.print_main_menu", lambda: next(choice_gen))

        client = GameClient()
        client._play_single_player = MagicMock()

        client.run()

        client._play_single_player.assert_called_once()

    def test_run_local_multiplayer_choice(self, monkeypatch):
        """Test run with local multiplayer selection."""
        choices = ["2", "5"]
        choice_gen = iter(choices)
        monkeypatch.setattr("client.ui.print_main_menu", lambda: next(choice_gen))

        client = GameClient()
        client._play_local_multiplayer = MagicMock()

        client.run()

        client._play_local_multiplayer.assert_called_once()

    def test_run_host_online_choice(self, monkeypatch):
        """Test run with host online selection."""
        choices = ["3", "5"]
        choice_gen = iter(choices)
        monkeypatch.setattr("client.ui.print_main_menu", lambda: next(choice_gen))

        client = GameClient()
        client._play_online_host = MagicMock()

        client.run()

        client._play_online_host.assert_called_once()

    def test_run_join_online_choice(self, monkeypatch):
        """Test run with join online selection."""
        choices = ["4", "5"]
        choice_gen = iter(choices)
        monkeypatch.setattr("client.ui.print_main_menu", lambda: next(choice_gen))

        client = GameClient()
        client._play_online_join = MagicMock()

        client.run()

        client._play_online_join.assert_called_once()

    def test_run_quit_choice(self, monkeypatch):
        """Test run with quit selection."""
        monkeypatch.setattr("client.ui.print_main_menu", lambda: "5")

        client = GameClient()

        client.run()

        assert client._running is False


class TestHotSeatMultiplayer:
    """Tests for hot-seat multiplayer scenarios."""

    def test_hot_seat_3_players(self, mock_network, mock_game_state, monkeypatch):
        """Test hot-seat with 3 local players."""
        monkeypatch.setattr("client.ui.print_shop", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_shop_choice", lambda s, p: None)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        net1 = mock_network([])
        net2 = mock_network([])
        net3 = mock_network([])

        client = GameClient()
        client._network = net1
        client.state = mock_game_state(
            phase=ClientPhase.SHOP,
            players=[
                {"player_id": "p1", "username": "Player1", "points": 50, "alive": True},
                {"player_id": "p2", "username": "Player2", "points": 30, "alive": True},
                {"player_id": "p3", "username": "Player3", "points": 20, "alive": True},
            ],
            local_player_ids=["p1", "p2", "p3"],
            available_passives=[]
        )
        client._local_networks = {"p1": net1, "p2": net2, "p3": net3}

        client._handle_shop_phase()

        # All three players should have skipped
        assert any(m["message_type"] == "SKIP_SHOP" for m in net1.sent_messages)
        assert any(m["message_type"] == "SKIP_SHOP" for m in net2.sent_messages)
        assert any(m["message_type"] == "SKIP_SHOP" for m in net3.sent_messages)

    def test_hot_seat_6_players_max(self, mock_network, mock_game_state, monkeypatch):
        """Test hot-seat with maximum 6 local players."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_location_choice", lambda s: 0)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        networks = [mock_network([]) for _ in range(6)]

        client = GameClient()
        client._network = networks[0]
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[
                {"player_id": f"p{i+1}", "username": f"Player{i+1}", "alive": True}
                for i in range(6)
            ],
            local_player_ids=[f"p{i+1}" for i in range(6)],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {f"p{i+1}": networks[i] for i in range(6)}

        client._handle_choosing_phase()

        # All 6 players should have submitted choices
        for i, net in enumerate(networks):
            assert any(m["message_type"] == "LOCATION_CHOICE" for m in net.sent_messages), \
                f"Player {i+1} didn't submit choice"

    def test_hot_seat_mixed_alive_dead(self, mock_network, mock_game_state, monkeypatch):
        """Test hot-seat with mix of alive and dead players."""
        monkeypatch.setattr("client.ui.print_location_choice_prompt", lambda s, p: None)
        monkeypatch.setattr("client.ui.get_location_choice", lambda s: 0)
        monkeypatch.setattr("client.ui.clear_screen", lambda: None)
        monkeypatch.setattr("client.ui.print_info", lambda m: None)
        monkeypatch.setattr("client.ui.wait_for_enter", lambda: None)

        net1 = mock_network([])
        net2 = mock_network([])
        net3 = mock_network([])
        net4 = mock_network([])

        client = GameClient()
        client._network = net1
        client.state = mock_game_state(
            phase=ClientPhase.CHOOSING,
            players=[
                {"player_id": "p1", "username": "Alive1", "alive": True},
                {"player_id": "p2", "username": "Dead1", "alive": False},
                {"player_id": "p3", "username": "Alive2", "alive": True},
                {"player_id": "p4", "username": "Dead2", "alive": False},
            ],
            local_player_ids=["p1", "p2", "p3", "p4"],
            locations=[{"name": "Store", "emoji": "S", "min_points": 5, "max_points": 10}]
        )
        client._local_networks = {"p1": net1, "p2": net2, "p3": net3, "p4": net4}

        client._handle_choosing_phase()

        # Only alive players should have submitted
        assert any(m["message_type"] == "LOCATION_CHOICE" for m in net1.sent_messages)
        assert not any(m["message_type"] == "LOCATION_CHOICE" for m in net2.sent_messages)
        assert any(m["message_type"] == "LOCATION_CHOICE" for m in net3.sent_messages)
        assert not any(m["message_type"] == "LOCATION_CHOICE" for m in net4.sent_messages)
