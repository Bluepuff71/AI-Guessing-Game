"""Integration tests for client-server communication.

Tests that the terminal client can properly connect to and communicate
with the game server.
"""

import asyncio
import pytest
import subprocess
import sys
import time
from typing import Dict, List, Any

from client.connection import ConnectionManager
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from server.protocol import ServerMessageType


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

    @pytest.mark.asyncio
    async def test_client_can_connect(self, server_process_18765):
        """Test that client can connect to server."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        await connection.connect("ws://127.0.0.1:18765")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("TestPlayer")

        # Wait for welcome response
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected and state.player_id:
                break

        assert state.connected is True
        assert state.player_id is not None
        assert state.game_id is not None

        await connection.disconnect()

    @pytest.mark.asyncio
    async def test_client_receives_lobby_state(self, server_process_18765):
        """Test that client receives lobby state after joining."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        await connection.connect("ws://127.0.0.1:18765")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("TestPlayer")

        # Wait for lobby state
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.players:
                break

        assert len(state.players) >= 1
        assert state.player_id in state.players

        player = state.players[state.player_id]
        assert player.username == "TestPlayer"

        await connection.disconnect()

    @pytest.mark.asyncio
    async def test_player_can_ready_up(self, server_process_18765):
        """Test that player can set ready status."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        await connection.connect("ws://127.0.0.1:18765")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("TestPlayer")

        # Wait for connection
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected:
                break

        await connection.send_ready()

        # Wait for ready status update
        await asyncio.sleep(0.3)

        # With single player, game might auto-start
        # Either player is ready or phase changed to SHOP
        player = state.players.get(state.player_id)
        assert player is not None
        # Game started (auto-starts with 1 player ready in single-player mode)
        # or player is marked ready
        assert player.ready or state.phase == ClientPhase.SHOP

        await connection.disconnect()


class TestClientServerGameFlow:
    """Test client-server game flow."""

    @pytest.mark.asyncio
    async def test_single_player_game_start(self, server_process_18766):
        """Test that single player can start a game."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        phase_changes = []
        async def on_phase_change(phase):
            phase_changes.append(phase)

        handler.set_callbacks(on_phase_change=on_phase_change)

        await connection.connect("ws://127.0.0.1:18766")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("SinglePlayer")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected:
                break

        # Ready up to start game
        await connection.send_ready()

        # Wait for game to start
        for _ in range(50):
            await asyncio.sleep(0.1)
            if state.phase == ClientPhase.SHOP:
                break

        assert state.phase == ClientPhase.SHOP
        assert state.round_num == 1
        assert len(state.locations) > 0

        await connection.disconnect()

    @pytest.mark.asyncio
    async def test_shop_skip_to_choosing(self, server_process_18766):
        """Test that skipping shop moves to choosing phase."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        await connection.connect("ws://127.0.0.1:18766")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("ShopTest")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected:
                break

        await connection.send_ready()

        # Wait for shop phase
        for _ in range(50):
            await asyncio.sleep(0.1)
            if state.phase == ClientPhase.SHOP:
                break

        assert state.phase == ClientPhase.SHOP

        # Skip shop
        await connection.send_skip_shop()

        # Wait for choosing phase
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.phase == ClientPhase.CHOOSING:
                break

        assert state.phase == ClientPhase.CHOOSING

        await connection.disconnect()

    @pytest.mark.asyncio
    async def test_location_choice_submission(self, server_process_18766):
        """Test that location choice can be submitted."""
        connection = ConnectionManager()
        state = GameState()
        handler = MessageHandler(state)

        results_received = []
        async def on_round_result(results):
            results_received.append(results)

        handler.set_callbacks(on_round_result=on_round_result)

        await connection.connect("ws://127.0.0.1:18766")
        connection.set_message_handler(handler.handle)
        await connection.start_receiving()

        await connection.send_join("ChoiceTest")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.connected:
                break

        await connection.send_ready()

        # Wait for shop, then skip
        for _ in range(50):
            await asyncio.sleep(0.1)
            if state.phase == ClientPhase.SHOP:
                break

        await connection.send_skip_shop()

        # Wait for choosing phase
        for _ in range(30):
            await asyncio.sleep(0.1)
            if state.phase == ClientPhase.CHOOSING:
                break

        # Submit location choice (first location)
        await connection.send_location_choice(0)

        # Wait for round result or escape phase
        for _ in range(50):
            await asyncio.sleep(0.1)
            if results_received or state.phase == ClientPhase.ESCAPE:
                break

        # Either got results or entered escape
        assert len(results_received) > 0 or state.phase == ClientPhase.ESCAPE

        await connection.disconnect()


class TestMultipleClients:
    """Test multiple clients connecting to same server."""

    @pytest.mark.asyncio
    async def test_two_players_connect(self, server_process_18767):
        """Test that two players can connect to same game."""
        # Player 1
        conn1 = ConnectionManager()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        # Player 2
        conn2 = ConnectionManager()
        state2 = GameState()
        handler2 = MessageHandler(state2)

        # Connect player 1
        await conn1.connect("ws://127.0.0.1:18767")
        conn1.set_message_handler(handler1.handle)
        await conn1.start_receiving()
        await conn1.send_join("Alice")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state1.connected:
                break

        # Connect player 2
        await conn2.connect("ws://127.0.0.1:18767")
        conn2.set_message_handler(handler2.handle)
        await conn2.start_receiving()
        await conn2.send_join("Bob")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state2.connected:
                break

        # Both should be in same game
        assert state1.game_id == state2.game_id

        # Wait for both to receive player list updates
        await asyncio.sleep(0.5)

        # Both states should show 2 players
        assert len(state1.players) == 2
        assert len(state2.players) == 2

        await conn1.disconnect()
        await conn2.disconnect()

    @pytest.mark.asyncio
    async def test_two_players_start_game(self, server_process_18767):
        """Test that two players can start a game together."""
        conn1 = ConnectionManager()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        conn2 = ConnectionManager()
        state2 = GameState()
        handler2 = MessageHandler(state2)

        # Connect both
        await conn1.connect("ws://127.0.0.1:18767")
        conn1.set_message_handler(handler1.handle)
        await conn1.start_receiving()
        await conn1.send_join("Alice")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state1.connected:
                break

        await conn2.connect("ws://127.0.0.1:18767")
        conn2.set_message_handler(handler2.handle)
        await conn2.start_receiving()
        await conn2.send_join("Bob")

        for _ in range(30):
            await asyncio.sleep(0.1)
            if state2.connected:
                break

        # Both ready up
        await conn1.send_ready()
        await conn2.send_ready()

        # Wait for game to start
        for _ in range(50):
            await asyncio.sleep(0.1)
            if state1.phase == ClientPhase.SHOP and state2.phase == ClientPhase.SHOP:
                break

        # Both should be in shop phase
        assert state1.phase == ClientPhase.SHOP
        assert state2.phase == ClientPhase.SHOP
        assert state1.round_num == 1
        assert state2.round_num == 1

        await conn1.disconnect()
        await conn2.disconnect()
