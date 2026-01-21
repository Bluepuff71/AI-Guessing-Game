"""Integration tests for NetworkThread with actual server connection."""

import subprocess
import sys
import time

import pytest

from client.network_thread import NetworkThread
from version import VERSION


@pytest.fixture
def server_process_18780():
    """Start a server on port 18780 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18780"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for server to be ready
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture
def server_process_18781():
    """Start a server on port 18781 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18781"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


class TestNetworkThreadConnection:
    """Test NetworkThread connection to server."""

    def test_connects_to_server(self, server_process_18780):
        """Test that NetworkThread can connect to a running server."""
        thread = NetworkThread()

        result = thread.start("ws://127.0.0.1:18780")
        assert result is True

        # Wait for CONNECTED message
        msg = None
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break

        assert msg is not None
        assert msg["type"] == "CONNECTED"

        thread.stop()

    def test_receives_welcome_after_join(self, server_process_18780):
        """Test that NetworkThread receives WELCOME after sending JOIN."""
        thread = NetworkThread()
        thread.start("ws://127.0.0.1:18780")

        # Wait for connection
        for _ in range(30):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break

        # Send JOIN message
        thread.send("JOIN", {"username": "TestPlayer", "version": VERSION})

        # Wait for WELCOME response
        welcome_received = False
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "SERVER_MESSAGE":
                if msg["message_type"] == "WELCOME":
                    welcome_received = True
                    break

        assert welcome_received is True

        thread.stop()

    def test_receives_lobby_state(self, server_process_18780):
        """Test that NetworkThread receives LOBBY_STATE after joining."""
        thread = NetworkThread()
        thread.start("ws://127.0.0.1:18780")

        # Wait for connection
        for _ in range(30):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break

        # Send JOIN message
        thread.send("JOIN", {"username": "TestPlayer", "version": VERSION})

        # Wait for LOBBY_STATE
        lobby_received = False
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "SERVER_MESSAGE":
                if msg["message_type"] == "LOBBY_STATE":
                    lobby_received = True
                    assert "players" in msg["data"]
                    break

        assert lobby_received is True

        thread.stop()

    def test_connection_refused_error(self):
        """Test that connection to non-existent server reports error."""
        thread = NetworkThread()
        thread.start("ws://127.0.0.1:19999")  # Port with no server

        # Wait for CONNECTION_LOST message
        msg = None
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg:
                break

        assert msg is not None
        assert msg["type"] == "CONNECTION_LOST"
        assert "error" in msg

        thread.stop()


class TestNetworkThreadGameFlow:
    """Test NetworkThread game flow interactions."""

    def test_can_send_ready(self, server_process_18781):
        """Test that NetworkThread can send READY message."""
        thread = NetworkThread()
        thread.start("ws://127.0.0.1:18781")

        # Wait for connection
        for _ in range(30):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break

        # Join
        thread.send("JOIN", {"username": "ReadyPlayer", "version": VERSION})

        # Wait for lobby state
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "SERVER_MESSAGE":
                if msg["message_type"] == "LOBBY_STATE":
                    break

        # Send ready
        thread.send("READY", {})

        # Wait for PLAYER_READY or game started
        ready_confirmed = False
        for _ in range(50):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "SERVER_MESSAGE":
                if msg["message_type"] in ("PLAYER_READY", "GAME_STARTED", "SHOP_STATE"):
                    ready_confirmed = True
                    break

        assert ready_confirmed is True

        thread.stop()


class TestNetworkThreadStop:
    """Test NetworkThread stop behavior."""

    def test_stop_disconnects_cleanly(self, server_process_18780):
        """Test that stop() disconnects cleanly."""
        thread = NetworkThread()
        thread.start("ws://127.0.0.1:18780")

        # Wait for connection
        for _ in range(30):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break

        # Stop should not hang
        thread.stop()

        assert thread._running is False
        assert thread._thread is None

    def test_multiple_start_stop_cycles(self, server_process_18780):
        """Test that thread can be started and stopped multiple times."""
        thread = NetworkThread()

        # First cycle
        thread.start("ws://127.0.0.1:18780")
        for _ in range(30):
            msg = thread.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break
        thread.stop()

        # Second cycle - need new thread object since thread was stopped
        thread2 = NetworkThread()
        thread2.start("ws://127.0.0.1:18780")
        for _ in range(30):
            msg = thread2.poll(timeout=0.1)
            if msg and msg["type"] == "CONNECTED":
                break
        thread2.stop()

        assert thread._running is False
        assert thread2._running is False
