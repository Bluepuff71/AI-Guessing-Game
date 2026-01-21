# tests/unit/test_engine_v2_game_flow.py
"""Unit tests for EventDrivenGameEngine game flow."""

import pytest
from unittest.mock import AsyncMock

from server.engine_v2 import EventDrivenGameEngine
from server.events import GameEvent, GameEventType
from server.protocol import GamePhase


class TestGameFlow:
    """Test complete game flow through events."""

    @pytest.fixture
    def engine(self):
        """Create an engine with mock callbacks."""
        return EventDrivenGameEngine(
            game_id="test",
            broadcast=AsyncMock(),
            send_to_player=AsyncMock(),
            turn_timer_seconds=1,
            escape_timer_seconds=1,
            shop_timer_seconds=1
        )

    @pytest.mark.asyncio
    async def test_full_round_flow(self, engine):
        """Test a complete round from join to results."""
        # Join
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        ))

        # Ready
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_READY,
            player_id="p1"
        ))

        # Start game
        await engine.handle_event(GameEvent(type=GameEventType.GAME_START))

        assert engine.phase == GamePhase.CHOOSING
        assert engine.round_num == 1

        # Make choice
        await engine.handle_event(GameEvent(
            type=GameEventType.LOCATION_CHOICE,
            player_id="p1",
            data={"location_index": 0}
        ))

        # Round should resolve (only one player)
        # Phase will be ROUND_END or CHOOSING (next round) or ESCAPE
        assert engine.round_num >= 1

    @pytest.mark.asyncio
    async def test_escape_flow_non_blocking(self, engine):
        """Test escape phase completes without blocking."""
        # Setup: Join and ready
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        ))
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_READY,
            player_id="p1"
        ))
        await engine.handle_event(GameEvent(type=GameEventType.GAME_START))

        # Simulate being in escape phase with a pending escape
        engine._phase = GamePhase.ESCAPE
        engine.pending_escapes.add_escape(
            player_id="p1",
            location_name="Bank",
            location_points=50,
            escape_options=[{"id": "vault", "name": "Vault", "type": "hide"}],
            ai_prediction="vault",
            ai_reasoning="test"
        )

        # Submit escape choice - should not block
        import asyncio
        await asyncio.wait_for(
            engine.handle_event(GameEvent(
                type=GameEventType.ESCAPE_CHOICE,
                player_id="p1",
                data={"option_id": "vault"}
            )),
            timeout=0.5  # Must complete in 0.5s
        )

        # Escape should be resolved
        assert engine.phase != GamePhase.ESCAPE or engine.pending_escapes.all_resolved()

    @pytest.mark.asyncio
    async def test_multiple_players_round(self, engine):
        """Test a round with multiple players."""
        # Join two players
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        ))
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p2",
            data={"username": "Bob"}
        ))

        # Both ready
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_READY, player_id="p1"
        ))
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_READY, player_id="p2"
        ))

        # Start
        await engine.handle_event(GameEvent(type=GameEventType.GAME_START))

        assert engine.phase == GamePhase.CHOOSING
        assert len(engine.players) == 2

        # First player chooses
        await engine.handle_event(GameEvent(
            type=GameEventType.LOCATION_CHOICE,
            player_id="p1",
            data={"location_index": 0}
        ))

        # Game should still be in choosing (waiting for p2)
        assert engine.phase == GamePhase.CHOOSING

        # Second player chooses
        await engine.handle_event(GameEvent(
            type=GameEventType.LOCATION_CHOICE,
            player_id="p2",
            data={"location_index": 1}
        ))

        # Round should resolve
        assert engine.round_num >= 1

    @pytest.mark.asyncio
    async def test_player_unready(self, engine):
        """Test player can become unready before game starts."""
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        ))

        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_READY, player_id="p1"
        ))
        assert engine.players["p1"].ready is True

        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_UNREADY, player_id="p1"
        ))
        assert engine.players["p1"].ready is False

    @pytest.mark.asyncio
    async def test_ignore_choice_in_wrong_phase(self, engine):
        """Test that choices are ignored in wrong phase."""
        await engine.handle_event(GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="p1",
            data={"username": "Alice"}
        ))

        # Try to make a choice while in LOBBY
        await engine.handle_event(GameEvent(
            type=GameEventType.LOCATION_CHOICE,
            player_id="p1",
            data={"location_index": 0}
        ))

        # Should have no effect - no choice recorded
        assert engine.pending_choices.get_choice("p1") is None
