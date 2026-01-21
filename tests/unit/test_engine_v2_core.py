# tests/unit/test_engine_v2_core.py
"""Unit tests for EventDrivenGameEngine core functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from server.engine_v2 import EventDrivenGameEngine
from server.events import GameEvent, GameEventType
from server.protocol import GamePhase


class TestEngineCore:
    """Test engine initialization and basic operations."""

    def test_engine_initializes_in_lobby_phase(self):
        """Test engine starts in lobby phase."""
        engine = EventDrivenGameEngine(
            game_id="test-game",
            broadcast=AsyncMock(),
            send_to_player=AsyncMock()
        )

        assert engine.phase == GamePhase.LOBBY
        assert engine.round_num == 0
        assert len(engine.players) == 0

    @pytest.mark.asyncio
    async def test_handle_event_dispatches_to_handler(self):
        """Test that handle_event dispatches to correct handler."""
        engine = EventDrivenGameEngine(
            game_id="test-game",
            broadcast=AsyncMock(),
            send_to_player=AsyncMock()
        )

        # Handle a player join event
        event = GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        )
        await engine.handle_event(event)

        # Player should be added
        assert "p1" in engine.players
        assert engine.players["p1"].username == "Alice"

    @pytest.mark.asyncio
    async def test_handle_event_returns_immediately(self):
        """Test that handle_event never blocks."""
        engine = EventDrivenGameEngine(
            game_id="test-game",
            broadcast=AsyncMock(),
            send_to_player=AsyncMock()
        )

        # This should return immediately, not block
        import asyncio
        event = GameEvent(type=GameEventType.PLAYER_JOIN, player_id="p1", data={"username": "Test"})

        # If this takes more than 0.1s, it's blocking
        await asyncio.wait_for(engine.handle_event(event), timeout=0.1)


class TestPhaseTransitions:
    """Test phase transition guards."""

    @pytest.mark.asyncio
    async def test_cannot_start_game_from_wrong_phase(self):
        """Test that GAME_START is ignored when not in lobby."""
        engine = EventDrivenGameEngine(
            game_id="test-game",
            broadcast=AsyncMock(),
            send_to_player=AsyncMock()
        )

        # Force into shop phase
        engine._phase = GamePhase.SHOP

        # Try to start game
        event = GameEvent(type=GameEventType.GAME_START)
        await engine.handle_event(event)

        # Should still be in shop (event ignored)
        assert engine.phase == GamePhase.SHOP
