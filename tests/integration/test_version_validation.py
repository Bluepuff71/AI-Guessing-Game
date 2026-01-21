"""Integration tests for version validation between client and server.

Tests that the server properly validates client version during join.
"""

import asyncio
import pytest
import subprocess
import sys
import time
import json
from unittest.mock import patch

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from client.connection import ConnectionManager
from client.state import GameState
from client.handler import MessageHandler
from server.protocol import Message, ClientMessageType, ServerMessageType
from version import VERSION


@pytest.fixture
def server_process_18770():
    """Start a server on port 18770 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18770"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for server to be ready
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


@pytest.fixture
def server_process_18771():
    """Start a server on port 18771 for testing."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", "18771"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    # Wait for server to be ready
    time.sleep(0.8)
    yield proc
    proc.terminate()
    proc.wait()


class TestVersionValidation:
    """Test version validation during client join."""

    @pytest.mark.asyncio
    async def test_matching_version_allows_join(self, server_process_18770):
        """Test that a client with matching version can join successfully."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        await connection.connect("ws://127.0.0.1:18770")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        # send_join now includes the VERSION automatically
        await connection.send_join("TestPlayer")

        # Wait for welcome response
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected and state.player_id:
                break

        # Should successfully join
        assert state.connected is True
        assert state.player_id is not None
        assert state.game_id is not None

        await connection.disconnect()

    @pytest.mark.asyncio
    async def test_mismatched_version_rejected(self, server_process_18771):
        """Test that a client with mismatched version is rejected."""
        if not WEBSOCKETS_AVAILABLE:
            pytest.skip("websockets library not available")

        # Connect directly with raw websocket to send custom version
        async with websockets.connect("ws://127.0.0.1:18771") as websocket:
            # Send join with wrong version
            join_message = Message(
                type=ClientMessageType.JOIN.value,
                data={
                    "username": "TestPlayer",
                    "profile_id": None,
                    "version": "wrong_version_1.0.0"
                }
            )
            await websocket.send(join_message.to_json())

            # Should receive error message
            response_raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response = Message.from_json(response_raw)

            assert response.type == ServerMessageType.ERROR.value
            assert response.data.get("error_type") == "version_mismatch"
            assert "Version mismatch" in response.data.get("message", "")
            assert "wrong_version_1.0.0" in response.data.get("message", "")
            assert VERSION in response.data.get("message", "")

    @pytest.mark.asyncio
    async def test_missing_version_rejected(self, server_process_18771):
        """Test that a client with no version is rejected."""
        if not WEBSOCKETS_AVAILABLE:
            pytest.skip("websockets library not available")

        # Connect directly with raw websocket to send message without version
        async with websockets.connect("ws://127.0.0.1:18771") as websocket:
            # Send join without version field
            join_message = Message(
                type=ClientMessageType.JOIN.value,
                data={
                    "username": "TestPlayer",
                    "profile_id": None
                }
            )
            await websocket.send(join_message.to_json())

            # Should receive error message
            response_raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response = Message.from_json(response_raw)

            assert response.type == ServerMessageType.ERROR.value
            assert response.data.get("error_type") == "version_mismatch"
            assert "Version mismatch" in response.data.get("message", "")
            assert "None" in response.data.get("message", "")

    @pytest.mark.asyncio
    async def test_send_join_includes_version(self):
        """Test that send_join includes the VERSION in the message."""
        # This tests that the ConnectionManager.send_join properly includes version
        connection = ConnectionManager()

        # Mock the send method to capture the message
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        connection.send = mock_send
        connection.connected = True  # Pretend we're connected

        await connection.send_join("TestPlayer", "profile123")

        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert msg.type == ClientMessageType.JOIN.value
        assert msg.data["username"] == "TestPlayer"
        assert msg.data["profile_id"] == "profile123"
        assert msg.data["version"] == VERSION


class TestParseJoinMessage:
    """Test the parse_join_message function includes version."""

    def test_parse_join_message_with_version(self):
        """Test parsing join message with version."""
        from server.protocol import parse_join_message

        data = {
            "username": "TestPlayer",
            "profile_id": "profile123",
            "version": "v1.0.0"
        }
        parsed = parse_join_message(data)

        assert parsed["username"] == "TestPlayer"
        assert parsed["profile_id"] == "profile123"
        assert parsed["version"] == "v1.0.0"

    def test_parse_join_message_without_version(self):
        """Test parsing join message without version returns None."""
        from server.protocol import parse_join_message

        data = {
            "username": "TestPlayer",
            "profile_id": "profile123"
        }
        parsed = parse_join_message(data)

        assert parsed["username"] == "TestPlayer"
        assert parsed["profile_id"] == "profile123"
        assert parsed["version"] is None

    def test_parse_join_message_empty_version(self):
        """Test parsing join message with empty version."""
        from server.protocol import parse_join_message

        data = {
            "username": "TestPlayer",
            "version": ""
        }
        parsed = parse_join_message(data)

        assert parsed["version"] == ""
