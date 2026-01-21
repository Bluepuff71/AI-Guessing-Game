# server/timers.py
"""Timer manager for the event-driven game engine."""

import asyncio
from typing import Any, Callable, Awaitable, Dict, Optional

from server.events import GameEvent, GameEventType


class TimerManager:
    """Manages game timers that fire events when they expire."""

    def __init__(self, event_callback: Callable[[GameEvent], Awaitable[None]]):
        """Initialize timer manager.

        Args:
            event_callback: Async function to call when a timer expires.
        """
        self._event_callback = event_callback
        self._timers: Dict[str, asyncio.Task] = {}

    def start_timer(
        self,
        timer_id: str,
        duration_seconds: float,
        event_type: GameEventType,
        data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Start a timer that fires an event when it expires.

        Args:
            timer_id: Unique identifier for this timer.
            duration_seconds: How long until the timer fires.
            event_type: The event type to fire.
            data: Optional data to include in the event.
        """
        # Cancel existing timer with same ID
        self.cancel_timer(timer_id)

        async def timer_task():
            try:
                await asyncio.sleep(duration_seconds)
                event = GameEvent(type=event_type, data=data or {})
                await self._event_callback(event)
            except asyncio.CancelledError:
                pass  # Timer was cancelled, don't fire event
            finally:
                # Clean up reference
                self._timers.pop(timer_id, None)

        self._timers[timer_id] = asyncio.create_task(timer_task())

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a timer if it exists.

        Args:
            timer_id: The timer to cancel.

        Returns:
            True if a timer was cancelled, False if no such timer.
        """
        task = self._timers.pop(timer_id, None)
        if task:
            task.cancel()
            return True
        return False

    def cancel_all(self) -> None:
        """Cancel all active timers."""
        for task in self._timers.values():
            task.cancel()
        self._timers.clear()

    def is_active(self, timer_id: str) -> bool:
        """Check if a timer is currently active."""
        return timer_id in self._timers
