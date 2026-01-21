# tests/unit/test_server_timers.py
"""Unit tests for timer manager."""

import asyncio
import pytest
from server.timers import TimerManager
from server.events import GameEvent, GameEventType


class TestTimerManager:
    """Test TimerManager."""

    @pytest.mark.asyncio
    async def test_start_timer_fires_event(self):
        """Test that a timer fires an event when it expires."""
        events_received = []

        async def on_event(event: GameEvent):
            events_received.append(event)

        manager = TimerManager(on_event)

        # Start a 0.1 second timer
        manager.start_timer(
            timer_id="test",
            duration_seconds=0.1,
            event_type=GameEventType.CHOICE_TIMEOUT
        )

        # Wait for timer to fire
        await asyncio.sleep(0.15)

        assert len(events_received) == 1
        assert events_received[0].type == GameEventType.CHOICE_TIMEOUT

    @pytest.mark.asyncio
    async def test_cancel_timer_prevents_event(self):
        """Test that cancelling a timer prevents the event."""
        events_received = []

        async def on_event(event: GameEvent):
            events_received.append(event)

        manager = TimerManager(on_event)

        manager.start_timer("test", 0.1, GameEventType.CHOICE_TIMEOUT)
        manager.cancel_timer("test")

        await asyncio.sleep(0.15)

        assert len(events_received) == 0

    @pytest.mark.asyncio
    async def test_cancel_all_timers(self):
        """Test cancelling all timers."""
        events_received = []

        async def on_event(event: GameEvent):
            events_received.append(event)

        manager = TimerManager(on_event)

        manager.start_timer("t1", 0.1, GameEventType.SHOP_TIMEOUT)
        manager.start_timer("t2", 0.1, GameEventType.CHOICE_TIMEOUT)
        manager.cancel_all()

        await asyncio.sleep(0.15)

        assert len(events_received) == 0

    @pytest.mark.asyncio
    async def test_timer_with_data(self):
        """Test timer event includes custom data."""
        events_received = []

        async def on_event(event: GameEvent):
            events_received.append(event)

        manager = TimerManager(on_event)

        manager.start_timer(
            "test", 0.1, GameEventType.ESCAPE_TIMEOUT,
            data={"player_id": "p1"}
        )

        await asyncio.sleep(0.15)

        assert events_received[0].data["player_id"] == "p1"
