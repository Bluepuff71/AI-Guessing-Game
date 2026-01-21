"""Integration tests for client-server communication.

Tests that the terminal client can properly connect to and communicate
with the game server using the new NetworkThread-based architecture.
"""

import pytest
import subprocess
import sys
import time

# Mark all tests in this module as slow and set a timeout
pytestmark = [pytest.mark.slow, pytest.mark.timeout(30)]

from typing import Dict, List, Any

from client.network_thread import NetworkThread
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from server.protocol import ServerMessageType
from version import VERSION


# Test timeouts
POLL_TIMEOUT = 0.1
CONNECTION_TIMEOUT = 5.0


def connect_and_join(network: NetworkThread, handler: MessageHandler, state: GameState,
                     host: str, port: int, username: str) -> bool:
    """Helper to connect and join a game.

    Returns True if successful, False otherwise.
    """
    if not network.start(f"ws://{host}:{port}"):
        return False

    # Wait for connection
    start_time = time.time()
    connected = False
    while time.time() - start_time < CONNECTION_TIMEOUT:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg:
            if msg["type"] == "CONNECTED":
                connected = True
                break
            elif msg["type"] == "CONNECTION_LOST":
                return False

    if not connected:
        return False

    # Send JOIN message
    network.send("JOIN", {"username": username, "version": VERSION})

    # Wait for WELCOME response
    start_time = time.time()
    while time.time() - start_time < CONNECTION_TIMEOUT:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg:
            if msg["type"] == "SERVER_MESSAGE":
                handler.handle(msg["message_type"], msg["data"])
                if state.connected and state.player_id:
                    return True
            elif msg["type"] == "CONNECTION_LOST":
                return False

    return False


def poll_until(network: NetworkThread, handler: MessageHandler, condition, timeout: float = 5.0):
    """Poll until condition is true or timeout.

    Args:
        network: NetworkThread to poll
        handler: MessageHandler to process messages
        condition: Callable that returns True when done
        timeout: Maximum time to wait

    Returns:
        True if condition became true, False on timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg and msg["type"] == "SERVER_MESSAGE":
            handler.handle(msg["message_type"], msg["data"])
        if condition():
            return True
    return False


@pytest.fixture
def server_process_18765():
    """Start a server on port 18765 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18765"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for server to be ready
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture
def server_process_18766():
    """Start a server on port 18766 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18766"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture
def server_process_18767():
    """Start a server on port 18767 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18767"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


class TestClientServerConnection:
    """Test client connection to server."""

    def test_client_can_connect(self, server_process_18765):
        """Test that client can connect to server."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18765, "TestPlayer")

            assert result is True
            assert state.connected is True
            assert state.player_id is not None
            assert state.game_id is not None
        finally:
            network.stop()

    def test_client_receives_lobby_state(self, server_process_18765):
        """Test that client receives lobby state after joining."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18765, "TestPlayer")
            assert result is True

            # Poll until we have players
            poll_until(network, handler, lambda: len(state.players) >= 1)

            assert len(state.players) >= 1
            assert state.player_id in state.players

            player = state.players[state.player_id]
            assert player.username == "TestPlayer"
        finally:
            network.stop()

    def test_player_can_ready_up(self, server_process_18765):
        """Test that player can set ready status."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18765, "TestPlayer")
            assert result is True

            # Send ready
            network.send("READY", {})

            # Wait for ready status update or game start
            poll_until(network, handler,
                      lambda: (state.players.get(state.player_id) and
                               state.players[state.player_id].ready) or
                              state.phase == ClientPhase.SHOP)

            # With single player, game might auto-start
            player = state.players.get(state.player_id)
            assert player is not None
            assert player.ready or state.phase == ClientPhase.SHOP
        finally:
            network.stop()


class TestClientServerGameFlow:
    """Test client-server game flow."""

    def test_single_player_game_start(self, server_process_18766):
        """Test that single player can start a game."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18766, "SinglePlayer")
            assert result is True

            # Ready up to start game
            network.send("READY", {})

            # Wait for game to start (shop phase)
            poll_until(network, handler, lambda: state.phase == ClientPhase.SHOP)

            assert state.phase == ClientPhase.SHOP
            assert state.round_num == 1
            assert len(state.locations) > 0
        finally:
            network.stop()

    def test_shop_skip_to_choosing(self, server_process_18766):
        """Test that skipping shop moves to choosing phase."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18766, "ShopTest")
            assert result is True

            network.send("READY", {})

            # Wait for shop phase
            poll_until(network, handler, lambda: state.phase == ClientPhase.SHOP)
            assert state.phase == ClientPhase.SHOP

            # Skip shop
            network.send("SKIP_SHOP", {})

            # Wait for choosing phase
            poll_until(network, handler, lambda: state.phase == ClientPhase.CHOOSING)

            assert state.phase == ClientPhase.CHOOSING
        finally:
            network.stop()

    def test_location_choice_submission(self, server_process_18766):
        """Test that location choice can be submitted."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            result = connect_and_join(network, handler, state, "127.0.0.1", 18766, "ChoiceTest")
            assert result is True

            network.send("READY", {})

            # Wait for shop, then skip
            poll_until(network, handler, lambda: state.phase == ClientPhase.SHOP)
            network.send("SKIP_SHOP", {})

            # Wait for choosing phase
            poll_until(network, handler, lambda: state.phase == ClientPhase.CHOOSING)

            # Submit location choice (first location)
            network.send("LOCATION_CHOICE", {"location_index": 0})

            # Wait for round result or escape phase
            poll_until(network, handler,
                      lambda: handler.last_round_result is not None or
                              state.phase == ClientPhase.ESCAPE,
                      timeout=10.0)

            # Either got results or entered escape
            assert handler.last_round_result is not None or state.phase == ClientPhase.ESCAPE
        finally:
            network.stop()


class TestMultipleClients:
    """Test multiple clients connecting to same server."""

    def test_two_players_connect(self, server_process_18767):
        """Test that two players can connect to same game."""
        # Player 1
        network1 = NetworkThread()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        # Player 2
        network2 = NetworkThread()
        state2 = GameState()
        handler2 = MessageHandler(state2)

        try:
            # Connect player 1
            result1 = connect_and_join(network1, handler1, state1, "127.0.0.1", 18767, "Alice")
            assert result1 is True

            # Connect player 2
            result2 = connect_and_join(network2, handler2, state2, "127.0.0.1", 18767, "Bob")
            assert result2 is True

            # Both should be in same game
            assert state1.game_id == state2.game_id

            # Poll both to receive player list updates
            for _ in range(50):
                msg1 = network1.poll(timeout=0.05)
                if msg1 and msg1["type"] == "SERVER_MESSAGE":
                    handler1.handle(msg1["message_type"], msg1["data"])

                msg2 = network2.poll(timeout=0.05)
                if msg2 and msg2["type"] == "SERVER_MESSAGE":
                    handler2.handle(msg2["message_type"], msg2["data"])

                if len(state1.players) == 2 and len(state2.players) == 2:
                    break

            # Both states should show 2 players
            assert len(state1.players) == 2
            assert len(state2.players) == 2
        finally:
            network1.stop()
            network2.stop()

    def test_two_players_start_game(self, server_process_18767):
        """Test that two players can start a game together."""
        network1 = NetworkThread()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        network2 = NetworkThread()
        state2 = GameState()
        handler2 = MessageHandler(state2)

        try:
            # Connect both
            result1 = connect_and_join(network1, handler1, state1, "127.0.0.1", 18767, "Alice")
            assert result1 is True

            result2 = connect_and_join(network2, handler2, state2, "127.0.0.1", 18767, "Bob")
            assert result2 is True

            # Both ready up
            network1.send("READY", {})
            network2.send("READY", {})

            # Poll both until game starts
            for _ in range(100):
                msg1 = network1.poll(timeout=0.05)
                if msg1 and msg1["type"] == "SERVER_MESSAGE":
                    handler1.handle(msg1["message_type"], msg1["data"])

                msg2 = network2.poll(timeout=0.05)
                if msg2 and msg2["type"] == "SERVER_MESSAGE":
                    handler2.handle(msg2["message_type"], msg2["data"])

                if state1.phase == ClientPhase.SHOP and state2.phase == ClientPhase.SHOP:
                    break

            # Both should be in shop phase
            assert state1.phase == ClientPhase.SHOP
            assert state2.phase == ClientPhase.SHOP
            assert state1.round_num == 1
            assert state2.round_num == 1
        finally:
            network1.stop()
            network2.stop()
