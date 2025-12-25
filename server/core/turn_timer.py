"""
Turn timer management for synchronized gameplay.

Handles:
- Countdown timers for turns
- Timer synchronization across clients
- Timeout handling
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional
from dataclasses import dataclass


@dataclass
class TimerState:
    """Current state of a timer."""
    total_seconds: int
    remaining_seconds: int
    started_at: datetime
    expired: bool = False


class TurnTimer:
    """
    Manages a countdown timer for game turns.

    Features:
    - Async countdown with callbacks
    - Periodic sync emissions
    - Clean cancellation
    """

    def __init__(
        self,
        duration_seconds: int,
        on_tick: Optional[Callable[[int], Awaitable[None]]] = None,
        on_expire: Optional[Callable[[], Awaitable[None]]] = None,
        sync_interval: int = 5,
    ):
        self.duration = duration_seconds
        self.on_tick = on_tick
        self.on_expire = on_expire
        self.sync_interval = sync_interval

        self._task: Optional[asyncio.Task] = None
        self._state: Optional[TimerState] = None
        self._cancelled = False

    @property
    def state(self) -> Optional[TimerState]:
        """Get current timer state."""
        return self._state

    @property
    def remaining(self) -> int:
        """Get remaining seconds."""
        if self._state:
            return self._state.remaining_seconds
        return 0

    @property
    def is_running(self) -> bool:
        """Check if timer is currently running."""
        return self._task is not None and not self._task.done()

    async def start(self):
        """Start the timer."""
        if self._task and not self._task.done():
            self._task.cancel()

        self._cancelled = False
        self._state = TimerState(
            total_seconds=self.duration,
            remaining_seconds=self.duration,
            started_at=datetime.now(timezone.utc),
        )

        self._task = asyncio.create_task(self._countdown())

    async def _countdown(self):
        """Internal countdown loop."""
        try:
            remaining = self.duration

            while remaining > 0 and not self._cancelled:
                await asyncio.sleep(1)
                remaining -= 1

                if self._state:
                    self._state.remaining_seconds = remaining

                # Emit sync at intervals
                if remaining > 0 and remaining % self.sync_interval == 0:
                    if self.on_tick:
                        await self.on_tick(remaining)

            # Timer expired
            if not self._cancelled and self._state:
                self._state.expired = True
                if self.on_expire:
                    await self.on_expire()

        except asyncio.CancelledError:
            pass

    def cancel(self):
        """Cancel the timer."""
        self._cancelled = True
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    def get_sync_message(self) -> dict:
        """Get a timer sync message for clients."""
        return {
            "remaining_seconds": self.remaining,
            "server_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }


class EscapeTimer(TurnTimer):
    """Specialized timer for escape phases (shorter duration)."""

    def __init__(
        self,
        on_tick: Optional[Callable[[int], Awaitable[None]]] = None,
        on_expire: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        super().__init__(
            duration_seconds=15,
            on_tick=on_tick,
            on_expire=on_expire,
            sync_interval=3,  # More frequent syncs for shorter timer
        )
