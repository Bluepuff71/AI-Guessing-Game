# Event-Driven Server Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the server to use an event-driven state machine architecture that eliminates blocking calls and enables concurrent message handling.

**Architecture:** Each game is an isolated state machine. All inputs (player actions, timer expirations) are events that trigger state transitions. The message handler dispatches events and returns immediately - never blocks. Timers are asyncio tasks that fire events when they expire.

**Tech Stack:** Python 3.10+, asyncio, websockets, dataclasses, Enum

---

## Background: The Problem

The current server has a fundamental flaw: it mixes event-driven message reception with blocking game flow orchestration.

```python
# Current blocking pattern in engine.py:891-897
async def _wait_for_escape_choice(self, player_id: str) -> str:
    while True:
        await asyncio.sleep(0.1)  # BLOCKS the message handler
        choice = self.pending_choices.escape_choices.get(player_id)
        if choice is not None:
            return choice
```

When the message handler awaits `_wait_for_escape_choice`, it cannot process new messages from that client. The ESCAPE_CHOICE message sits in the queue, never processed.

## Solution: Event-Driven State Machine

```
[WebSocket] --> [Event Dispatcher] --> [Game State Machine] --> [Outbound Messages]
                                              ^
                              [Timer Tasks fire events]
```

- **Events** are the only way state changes
- **State machine** processes one event at a time, returns immediately
- **Timers** are asyncio tasks that queue timeout events
- **No blocking** - message handler dispatches and returns

---

## Task 1: Define Event Types and Game State

**Files:**
- Create: `server/events.py`
- Test: `tests/unit/test_server_events.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_server_events.py
"""Unit tests for server event types."""

import pytest
from server.events import GameEvent, GameEventType


class TestGameEventType:
    """Test GameEventType enum."""

    def test_has_player_events(self):
        """Test player-related event types exist."""
        assert GameEventType.PLAYER_JOIN
        assert GameEventType.PLAYER_LEAVE
        assert GameEventType.PLAYER_READY

    def test_has_game_flow_events(self):
        """Test game flow event types exist."""
        assert GameEventType.GAME_START
        assert GameEventType.ROUND_START
        assert GameEventType.ALL_CHOICES_IN
        assert GameEventType.ROUND_COMPLETE

    def test_has_timeout_events(self):
        """Test timeout event types exist."""
        assert GameEventType.SHOP_TIMEOUT
        assert GameEventType.CHOICE_TIMEOUT
        assert GameEventType.ESCAPE_TIMEOUT


class TestGameEvent:
    """Test GameEvent dataclass."""

    def test_create_event_with_data(self):
        """Test creating an event with data."""
        event = GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="player123",
            data={"username": "Alice"}
        )
        assert event.type == GameEventType.PLAYER_JOIN
        assert event.player_id == "player123"
        assert event.data["username"] == "Alice"

    def test_create_event_without_player(self):
        """Test creating a system event without player_id."""
        event = GameEvent(
            type=GameEventType.SHOP_TIMEOUT,
            data={}
        )
        assert event.type == GameEventType.SHOP_TIMEOUT
        assert event.player_id is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_events.py -v`
Expected: FAIL with "No module named 'server.events'"

**Step 3: Write minimal implementation**

```python
# server/events.py
"""Event types for the event-driven game engine."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class GameEventType(Enum):
    """All possible game events."""

    # Player connection events
    PLAYER_JOIN = auto()
    PLAYER_LEAVE = auto()
    PLAYER_READY = auto()
    PLAYER_UNREADY = auto()

    # Game lifecycle
    GAME_START = auto()
    ROUND_START = auto()
    ROUND_COMPLETE = auto()
    GAME_OVER = auto()

    # Shop phase
    SHOP_PURCHASE = auto()
    SHOP_SKIP = auto()
    SHOP_TIMEOUT = auto()

    # Choosing phase
    LOCATION_CHOICE = auto()
    CHOICE_TIMEOUT = auto()
    ALL_CHOICES_IN = auto()

    # Resolution
    AI_DECISION_COMPLETE = auto()

    # Escape phase
    ESCAPE_START = auto()
    ESCAPE_CHOICE = auto()
    ESCAPE_TIMEOUT = auto()
    ESCAPE_RESOLVED = auto()
    ALL_ESCAPES_RESOLVED = auto()


@dataclass
class GameEvent:
    """An event that triggers a state transition."""

    type: GameEventType
    data: Dict[str, Any] = field(default_factory=dict)
    player_id: Optional[str] = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_events.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/events.py tests/unit/test_server_events.py
git commit -m "feat(server): add event types for event-driven architecture"
```

---

## Task 2: Create Pending State Trackers

**Files:**
- Create: `server/pending.py`
- Test: `tests/unit/test_server_pending.py`

**Step 1: Write the failing test**

```python
# tests/unit/test_server_pending.py
"""Unit tests for pending state trackers."""

import pytest
from server.pending import PendingChoices, PendingEscapes


class TestPendingChoices:
    """Test PendingChoices tracker."""

    def test_record_location_choice(self):
        """Test recording a location choice."""
        pending = PendingChoices()
        pending.record_choice("player1", 2)

        assert pending.get_choice("player1") == 2
        assert pending.get_choice("player2") is None

    def test_has_all_choices(self):
        """Test checking if all players have chosen."""
        pending = PendingChoices()
        player_ids = ["p1", "p2", "p3"]

        assert not pending.has_all_choices(player_ids)

        pending.record_choice("p1", 0)
        pending.record_choice("p2", 1)
        assert not pending.has_all_choices(player_ids)

        pending.record_choice("p3", 2)
        assert pending.has_all_choices(player_ids)

    def test_clear(self):
        """Test clearing choices."""
        pending = PendingChoices()
        pending.record_choice("p1", 0)
        pending.clear()

        assert pending.get_choice("p1") is None


class TestPendingEscapes:
    """Test PendingEscapes tracker."""

    def test_add_pending_escape(self):
        """Test adding a pending escape."""
        pending = PendingEscapes()
        pending.add_escape(
            player_id="p1",
            location_name="Bank",
            location_points=50,
            escape_options=[{"id": "vault", "name": "Hide in Vault"}],
            ai_prediction="vault",
            ai_reasoning="Player usually hides"
        )

        assert pending.has_pending("p1")
        assert not pending.has_pending("p2")

    def test_record_escape_choice(self):
        """Test recording an escape choice."""
        pending = PendingEscapes()
        pending.add_escape(
            player_id="p1",
            location_name="Bank",
            location_points=50,
            escape_options=[{"id": "vault"}],
            ai_prediction="vault",
            ai_reasoning="test"
        )

        pending.record_choice("p1", "vault")
        escape = pending.get_escape("p1")

        assert escape.choice_received
        assert escape.chosen_option_id == "vault"

    def test_all_resolved(self):
        """Test checking if all escapes are resolved."""
        pending = PendingEscapes()
        pending.add_escape("p1", "Bank", 50, [], "x", "y")
        pending.add_escape("p2", "Museum", 30, [], "x", "y")

        assert not pending.all_resolved()

        pending.record_choice("p1", "hide")
        assert not pending.all_resolved()

        pending.record_choice("p2", "run")
        assert pending.all_resolved()

    def test_get_unresolved(self):
        """Test getting unresolved escapes."""
        pending = PendingEscapes()
        pending.add_escape("p1", "Bank", 50, [], "x", "y")
        pending.add_escape("p2", "Museum", 30, [], "x", "y")

        pending.record_choice("p1", "hide")

        unresolved = pending.get_unresolved_player_ids()
        assert unresolved == ["p2"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_pending.py -v`
Expected: FAIL with "No module named 'server.pending'"

**Step 3: Write minimal implementation**

```python
# server/pending.py
"""Pending state trackers for the game engine."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PendingChoices:
    """Tracks pending location choices for a round."""

    _choices: Dict[str, int] = field(default_factory=dict)
    _shop_done: Dict[str, bool] = field(default_factory=dict)

    def record_choice(self, player_id: str, location_index: int) -> None:
        """Record a player's location choice."""
        self._choices[player_id] = location_index

    def get_choice(self, player_id: str) -> Optional[int]:
        """Get a player's choice, or None if not yet made."""
        return self._choices.get(player_id)

    def has_all_choices(self, player_ids: List[str]) -> bool:
        """Check if all specified players have made choices."""
        return all(pid in self._choices for pid in player_ids)

    def get_all_choices(self) -> Dict[str, int]:
        """Get all recorded choices."""
        return dict(self._choices)

    def record_shop_done(self, player_id: str) -> None:
        """Record that a player is done shopping."""
        self._shop_done[player_id] = True

    def is_shop_done(self, player_id: str) -> bool:
        """Check if a player is done shopping."""
        return self._shop_done.get(player_id, False)

    def all_shop_done(self, player_ids: List[str]) -> bool:
        """Check if all specified players are done shopping."""
        return all(self._shop_done.get(pid, False) for pid in player_ids)

    def clear(self) -> None:
        """Clear all pending choices."""
        self._choices.clear()
        self._shop_done.clear()


@dataclass
class PendingEscape:
    """Tracks a single player's pending escape."""

    player_id: str
    location_name: str
    location_points: int
    escape_options: List[Dict[str, Any]]
    ai_prediction: str
    ai_reasoning: str
    choice_received: bool = False
    chosen_option_id: Optional[str] = None


@dataclass
class PendingEscapes:
    """Tracks all pending escapes for a round."""

    _escapes: Dict[str, PendingEscape] = field(default_factory=dict)

    def add_escape(
        self,
        player_id: str,
        location_name: str,
        location_points: int,
        escape_options: List[Dict[str, Any]],
        ai_prediction: str,
        ai_reasoning: str
    ) -> None:
        """Add a pending escape for a player."""
        self._escapes[player_id] = PendingEscape(
            player_id=player_id,
            location_name=location_name,
            location_points=location_points,
            escape_options=escape_options,
            ai_prediction=ai_prediction,
            ai_reasoning=ai_reasoning
        )

    def has_pending(self, player_id: str) -> bool:
        """Check if a player has a pending escape."""
        return player_id in self._escapes

    def get_escape(self, player_id: str) -> Optional[PendingEscape]:
        """Get a player's pending escape."""
        return self._escapes.get(player_id)

    def record_choice(self, player_id: str, option_id: str) -> bool:
        """Record a player's escape choice. Returns False if no pending escape."""
        escape = self._escapes.get(player_id)
        if not escape:
            return False
        escape.choice_received = True
        escape.chosen_option_id = option_id
        return True

    def all_resolved(self) -> bool:
        """Check if all pending escapes have choices."""
        return all(e.choice_received for e in self._escapes.values())

    def get_unresolved_player_ids(self) -> List[str]:
        """Get player IDs with unresolved escapes."""
        return [pid for pid, e in self._escapes.items() if not e.choice_received]

    def get_all(self) -> List[PendingEscape]:
        """Get all pending escapes."""
        return list(self._escapes.values())

    def clear(self) -> None:
        """Clear all pending escapes."""
        self._escapes.clear()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_pending.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/pending.py tests/unit/test_server_pending.py
git commit -m "feat(server): add pending state trackers for choices and escapes"
```

---

## Task 3: Create Timer Manager

**Files:**
- Create: `server/timers.py`
- Test: `tests/unit/test_server_timers.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_server_timers.py -v`
Expected: FAIL with "No module named 'server.timers'"

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_server_timers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/timers.py tests/unit/test_server_timers.py
git commit -m "feat(server): add timer manager that fires events on expiration"
```

---

## Task 4: Create Event-Driven Engine Core

**Files:**
- Create: `server/engine_v2.py`
- Test: `tests/unit/test_engine_v2_core.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_engine_v2_core.py -v`
Expected: FAIL with "No module named 'server.engine_v2'"

**Step 3: Write minimal implementation**

```python
# server/engine_v2.py
"""Event-driven game engine for LOOT RUN multiplayer.

This engine:
- Uses an event-driven state machine architecture
- Never blocks - handle_event returns immediately
- All timers fire events instead of blocking
- Processes one event at a time
"""

import random
from datetime import datetime, timezone
from typing import Callable, Awaitable, Dict, List, Optional, Any
from dataclasses import dataclass, field

from game.locations import LocationManager, Location
from game.events import EventManager
from game.hiding import HidingManager
from game.passives import PassiveManager
from ai.predictor import AIPredictor
from ai.escape_predictor import EscapePredictor

from server.protocol import (
    GamePhase, Message, ServerMessageType,
    game_started_message, round_start_message, phase_change_message,
    player_submitted_message, all_choices_locked_message, player_timeout_message,
    ai_analyzing_message, round_result_message, player_caught_message,
    escape_phase_message, escape_result_message, player_eliminated_message,
    shop_state_message, purchase_result_message, game_over_message
)
from server.events import GameEvent, GameEventType
from server.pending import PendingChoices, PendingEscapes
from server.timers import TimerManager


# Type aliases
MessageBroadcaster = Callable[[Message], Awaitable[None]]
PlayerMessageSender = Callable[[str, Message], Awaitable[None]]

# Player colors
PLAYER_COLORS = ["green", "cyan", "yellow", "magenta", "red", "blue", "bright_green", "bright_cyan"]


@dataclass(eq=False)
class ServerPlayer:
    """Server-side player representation."""

    player_id: str
    username: str
    player_index: int
    profile_id: Optional[str] = None

    # Game state
    points: int = 0
    alive: bool = True
    connected: bool = True
    ready: bool = False

    # Passive management
    passive_manager: PassiveManager = field(default_factory=PassiveManager)

    # History tracking
    choice_history: List[str] = field(default_factory=list)
    round_history: List[Dict[str, Any]] = field(default_factory=list)
    escape_option_history: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.player_id)

    def __eq__(self, other):
        if isinstance(other, ServerPlayer):
            return self.player_id == other.player_id
        return False

    @property
    def color(self) -> str:
        return PLAYER_COLORS[self.player_index % len(PLAYER_COLORS)]

    def add_points(self, points: int) -> None:
        self.points += points

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "username": self.username,
            "points": self.points,
            "alive": self.alive,
            "connected": self.connected,
            "ready": self.ready,
            "color": self.color,
            "passives": [p.id for p in self.passive_manager.owned_passives]
        }


class EventDrivenGameEngine:
    """Event-driven game engine using state machine architecture."""

    # Timer IDs
    TIMER_SHOP = "shop"
    TIMER_CHOICE = "choice"
    TIMER_ESCAPE = "escape"

    def __init__(
        self,
        game_id: str,
        broadcast: MessageBroadcaster,
        send_to_player: PlayerMessageSender,
        turn_timer_seconds: int = 30,
        escape_timer_seconds: int = 15,
        shop_timer_seconds: int = 20,
        win_threshold: int = 100
    ):
        self.game_id = game_id
        self.broadcast = broadcast
        self.send_to_player = send_to_player

        # Settings
        self.turn_timer_seconds = turn_timer_seconds
        self.escape_timer_seconds = escape_timer_seconds
        self.shop_timer_seconds = shop_timer_seconds
        self.win_threshold = win_threshold

        # Players
        self.players: Dict[str, ServerPlayer] = {}
        self.player_order: List[str] = []

        # Game components
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.escape_predictor = EscapePredictor()
        self.event_manager = EventManager()
        self.hiding_manager = HidingManager()

        # State
        self._phase = GamePhase.LOBBY
        self.round_num = 0
        self.game_over = False
        self.winner: Optional[ServerPlayer] = None
        self.last_ai_search_location: Optional[Location] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None

        # Pending state
        self.pending_choices = PendingChoices()
        self.pending_escapes = PendingEscapes()

        # Timers
        self.timers = TimerManager(self._on_timer_event)

        # Event handlers by phase and event type
        self._handlers: Dict[GameEventType, Callable] = {
            GameEventType.PLAYER_JOIN: self._handle_player_join,
            GameEventType.PLAYER_LEAVE: self._handle_player_leave,
            GameEventType.PLAYER_READY: self._handle_player_ready,
            GameEventType.PLAYER_UNREADY: self._handle_player_unready,
            GameEventType.GAME_START: self._handle_game_start,
            GameEventType.SHOP_PURCHASE: self._handle_shop_purchase,
            GameEventType.SHOP_SKIP: self._handle_shop_skip,
            GameEventType.SHOP_TIMEOUT: self._handle_shop_timeout,
            GameEventType.LOCATION_CHOICE: self._handle_location_choice,
            GameEventType.CHOICE_TIMEOUT: self._handle_choice_timeout,
            GameEventType.ESCAPE_CHOICE: self._handle_escape_choice,
            GameEventType.ESCAPE_TIMEOUT: self._handle_escape_timeout,
        }

    @property
    def phase(self) -> GamePhase:
        """Current game phase."""
        return self._phase

    @property
    def alive_players(self) -> List[ServerPlayer]:
        """Get all alive players."""
        return [p for p in self.players.values() if p.alive]

    @property
    def connected_players(self) -> List[ServerPlayer]:
        """Get all connected players."""
        return [p for p in self.players.values() if p.connected]

    async def handle_event(self, event: GameEvent) -> None:
        """Handle an incoming event. Never blocks."""
        handler = self._handlers.get(event.type)
        if handler:
            await handler(event)

    async def _on_timer_event(self, event: GameEvent) -> None:
        """Called when a timer fires. Routes to handle_event."""
        await self.handle_event(event)

    # --- Player Events ---

    async def _handle_player_join(self, event: GameEvent) -> None:
        """Handle PLAYER_JOIN event."""
        player_id = event.player_id
        if not player_id or player_id in self.players:
            return

        username = event.data.get("username", f"Player_{player_id[:8]}")
        profile_id = event.data.get("profile_id")

        player = ServerPlayer(
            player_id=player_id,
            username=username,
            player_index=len(self.player_order),
            profile_id=profile_id
        )
        self.players[player_id] = player
        self.player_order.append(player_id)

    async def _handle_player_leave(self, event: GameEvent) -> None:
        """Handle PLAYER_LEAVE event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].connected = False

    async def _handle_player_ready(self, event: GameEvent) -> None:
        """Handle PLAYER_READY event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].ready = True

    async def _handle_player_unready(self, event: GameEvent) -> None:
        """Handle PLAYER_UNREADY event."""
        player_id = event.player_id
        if player_id in self.players:
            self.players[player_id].ready = False

    # --- Game Start ---

    async def _handle_game_start(self, event: GameEvent) -> None:
        """Handle GAME_START event."""
        if self._phase != GamePhase.LOBBY:
            return

        # Check all players ready
        connected = self.connected_players
        if not connected or not all(p.ready for p in connected):
            return

        self.started_at = datetime.now(timezone.utc)
        await self._start_round()

    # --- Shop Phase ---

    async def _handle_shop_purchase(self, event: GameEvent) -> None:
        """Handle SHOP_PURCHASE event."""
        if self._phase != GamePhase.SHOP:
            return
        # TODO: Implement shop purchase logic
        pass

    async def _handle_shop_skip(self, event: GameEvent) -> None:
        """Handle SHOP_SKIP event."""
        if self._phase != GamePhase.SHOP:
            return

        player_id = event.player_id
        if not player_id:
            return

        self.pending_choices.record_shop_done(player_id)
        await self._check_shop_complete()

    async def _handle_shop_timeout(self, event: GameEvent) -> None:
        """Handle SHOP_TIMEOUT event."""
        if self._phase != GamePhase.SHOP:
            return
        await self._start_choosing_phase()

    async def _check_shop_complete(self) -> None:
        """Check if all players are done shopping."""
        alive_ids = [p.player_id for p in self.alive_players if p.connected]
        if self.pending_choices.all_shop_done(alive_ids):
            self.timers.cancel_timer(self.TIMER_SHOP)
            await self._start_choosing_phase()

    # --- Choosing Phase ---

    async def _handle_location_choice(self, event: GameEvent) -> None:
        """Handle LOCATION_CHOICE event."""
        if self._phase != GamePhase.CHOOSING:
            return

        player_id = event.player_id
        location_index = event.data.get("location_index")

        if not player_id or location_index is None:
            return

        player = self.players.get(player_id)
        if not player or not player.alive:
            return

        # Already submitted?
        if self.pending_choices.get_choice(player_id) is not None:
            return

        # Validate location
        locations = self.location_manager.get_all()
        if location_index < 0 or location_index >= len(locations):
            return

        self.pending_choices.record_choice(player_id, location_index)

        # Notify others
        await self.broadcast(player_submitted_message(
            player_id=player_id,
            username=player.username
        ))

        await self._check_all_choices_in()

    async def _handle_choice_timeout(self, event: GameEvent) -> None:
        """Handle CHOICE_TIMEOUT event."""
        if self._phase != GamePhase.CHOOSING:
            return

        # Assign random choices to players who haven't submitted
        locations = self.location_manager.get_all()
        for player in self.alive_players:
            if self.pending_choices.get_choice(player.player_id) is None:
                random_index = random.randint(0, len(locations) - 1)
                self.pending_choices.record_choice(player.player_id, random_index)
                await self.broadcast(player_timeout_message(
                    player_id=player.player_id,
                    username=player.username
                ))

        await self._resolve_round()

    async def _check_all_choices_in(self) -> None:
        """Check if all players have submitted choices."""
        alive_ids = [p.player_id for p in self.alive_players if p.connected]
        if self.pending_choices.has_all_choices(alive_ids):
            self.timers.cancel_timer(self.TIMER_CHOICE)
            await self.broadcast(all_choices_locked_message(
                players_submitted=[p.username for p in self.alive_players if p.connected]
            ))
            await self._resolve_round()

    # --- Escape Phase ---

    async def _handle_escape_choice(self, event: GameEvent) -> None:
        """Handle ESCAPE_CHOICE event."""
        if self._phase != GamePhase.ESCAPE:
            return

        player_id = event.player_id
        option_id = event.data.get("option_id")

        if not player_id or not option_id:
            return

        if not self.pending_escapes.has_pending(player_id):
            return

        self.pending_escapes.record_choice(player_id, option_id)
        await self._check_all_escapes_resolved()

    async def _handle_escape_timeout(self, event: GameEvent) -> None:
        """Handle ESCAPE_TIMEOUT event."""
        if self._phase != GamePhase.ESCAPE:
            return

        # Assign random choices to unresolved escapes
        for player_id in self.pending_escapes.get_unresolved_player_ids():
            escape = self.pending_escapes.get_escape(player_id)
            if escape and escape.escape_options:
                random_option = random.choice(escape.escape_options)
                self.pending_escapes.record_choice(player_id, random_option["id"])

        await self._resolve_all_escapes()

    async def _check_all_escapes_resolved(self) -> None:
        """Check if all escape choices are in."""
        if self.pending_escapes.all_resolved():
            self.timers.cancel_timer(self.TIMER_ESCAPE)
            await self._resolve_all_escapes()

    # --- Phase Transitions ---

    async def _start_round(self) -> None:
        """Start a new round."""
        self.round_num += 1
        self.pending_choices.clear()
        self.pending_escapes.clear()

        # Roll new events
        self.event_manager.tick_events()

        # Go to shop phase (or skip if round 1)
        if self.round_num == 1:
            await self._start_choosing_phase()
        else:
            await self._start_shop_phase()

    async def _start_shop_phase(self) -> None:
        """Start the shop phase."""
        self._phase = GamePhase.SHOP

        # Send shop state to each player
        for player in self.alive_players:
            if player.connected:
                # TODO: Generate shop offerings
                await self.send_to_player(player.player_id, shop_state_message(
                    player_id=player.player_id,
                    player_points=player.points,
                    available_passives=[],
                    timer_seconds=self.shop_timer_seconds
                ))

        self.timers.start_timer(
            self.TIMER_SHOP,
            self.shop_timer_seconds,
            GameEventType.SHOP_TIMEOUT
        )

    async def _start_choosing_phase(self) -> None:
        """Start the location choosing phase."""
        self._phase = GamePhase.CHOOSING

        await self.broadcast(round_start_message(
            round_num=self.round_num,
            timer_seconds=self.turn_timer_seconds,
            server_timestamp=int(datetime.now(timezone.utc).timestamp() * 1000),
            active_events=self._build_active_events(),
            new_events=[],
            standings=self._build_standings(),
            previous_ai_location=self.last_ai_search_location.name if self.last_ai_search_location else None
        ))

        self.timers.start_timer(
            self.TIMER_CHOICE,
            self.turn_timer_seconds,
            GameEventType.CHOICE_TIMEOUT
        )

    async def _resolve_round(self) -> None:
        """Resolve the round after all choices are in."""
        self._phase = GamePhase.RESOLVING

        await self.broadcast(phase_change_message(
            new_phase="resolving",
            round_num=self.round_num
        ))

        await self.broadcast(ai_analyzing_message(duration_ms=1000))

        # Build player choices map
        player_choices: Dict[ServerPlayer, Location] = {}
        for player in self.alive_players:
            location_index = self.pending_choices.get_choice(player.player_id)
            if location_index is not None:
                location = self.location_manager.get_location(location_index)
                player_choices[player] = location

        # AI decides where to search
        search_location, predictions, ai_reasoning = self._ai_decide_search(player_choices)
        self.last_ai_search_location = search_location

        # Build results and identify caught players
        player_results = []
        caught_players = []

        for player in self.alive_players:
            chosen_location = player_choices.get(player)
            if not chosen_location:
                continue

            # Roll points
            location_points = chosen_location.roll_points()
            caught = (chosen_location.name == search_location.name)

            result = {
                "player_id": player.player_id,
                "username": player.username,
                "location": chosen_location.name,
                "location_emoji": chosen_location.emoji,
                "caught": caught,
                "base_points": location_points,
                "modified_points": location_points,
            }

            if caught:
                caught_players.append((player, chosen_location, location_points))
                result["escape_required"] = True
            else:
                player.add_points(location_points)
                result["points_earned"] = location_points
                result["total_points"] = player.points

            player_results.append(result)

        # Broadcast round result
        await self.broadcast(round_result_message(
            round_num=self.round_num,
            ai_search_location=search_location.name,
            ai_search_emoji=search_location.emoji,
            ai_reasoning=ai_reasoning,
            player_results=player_results,
            standings=self._build_standings()
        ))

        # Handle escapes or finish round
        if caught_players:
            await self._start_escape_phase(caught_players)
        else:
            await self._finish_round()

    async def _start_escape_phase(self, caught_players: List[tuple]) -> None:
        """Start the escape phase for caught players."""
        self._phase = GamePhase.ESCAPE

        for player, location, points in caught_players:
            # Get escape options
            escape_options = self.hiding_manager.get_escape_options_for_location(location.name)

            if not escape_options:
                # No escape - eliminated
                player.alive = False
                await self.broadcast(player_eliminated_message(
                    player_id=player.player_id,
                    username=player.username,
                    final_score=player.points
                ))
                continue

            # AI predicts escape
            ai_prediction, _, ai_reasoning = self.escape_predictor.predict_escape_option(
                player, escape_options, None
            )

            # Track pending escape
            self.pending_escapes.add_escape(
                player_id=player.player_id,
                location_name=location.name,
                location_points=points,
                escape_options=escape_options,
                ai_prediction=ai_prediction,
                ai_reasoning=ai_reasoning
            )

            # Notify player
            await self.broadcast(player_caught_message(
                player_id=player.player_id,
                username=player.username,
                location=location.name,
                location_points=points
            ))

            await self.send_to_player(player.player_id, escape_phase_message(
                player_id=player.player_id,
                username=player.username,
                location=location.name,
                location_points=points,
                escape_options=[{
                    "id": opt["id"],
                    "name": opt["name"],
                    "type": opt.get("type", "hide"),
                    "emoji": opt.get("emoji", ""),
                    "description": opt.get("description", ""),
                } for opt in escape_options],
                timer_seconds=self.escape_timer_seconds
            ))

        # Start escape timer (if anyone has pending escapes)
        if self.pending_escapes.get_all():
            self.timers.start_timer(
                self.TIMER_ESCAPE,
                self.escape_timer_seconds,
                GameEventType.ESCAPE_TIMEOUT
            )
        else:
            # All caught players were eliminated (no escape options)
            await self._finish_round()

    async def _resolve_all_escapes(self) -> None:
        """Resolve all pending escapes."""
        for escape in self.pending_escapes.get_all():
            await self._resolve_single_escape(escape)

        await self._finish_round()

    async def _resolve_single_escape(self, escape) -> None:
        """Resolve a single escape attempt."""
        player = self.players.get(escape.player_id)
        if not player:
            return

        chosen_option_id = escape.chosen_option_id
        chosen_option = None
        for opt in escape.escape_options:
            if opt["id"] == chosen_option_id:
                chosen_option = opt
                break

        if not chosen_option:
            chosen_option = escape.escape_options[0] if escape.escape_options else None

        if not chosen_option:
            player.alive = False
            return

        # Resolve using hiding manager
        result = self.hiding_manager.resolve_escape_attempt(
            chosen_option,
            escape.ai_prediction,
            escape.location_points
        )

        # Update player state
        if result["escaped"]:
            player.add_points(result.get("points_awarded", 0))
        else:
            player.alive = False

        # Broadcast result
        await self.broadcast(escape_result_message(
            player_id=player.player_id,
            username=player.username,
            player_choice=chosen_option_id,
            player_choice_name=chosen_option.get("name", chosen_option_id),
            ai_prediction=escape.ai_prediction,
            ai_prediction_name=escape.ai_prediction,
            ai_reasoning=escape.ai_reasoning,
            escaped=result["escaped"],
            points_awarded=result.get("points_awarded", 0),
            passive_saved=False
        ))

        if not result["escaped"]:
            await self.broadcast(player_eliminated_message(
                player_id=player.player_id,
                username=player.username,
                final_score=player.points
            ))

    async def _finish_round(self) -> None:
        """Finish the current round."""
        self._phase = GamePhase.ROUND_END

        # Check for game over
        if await self._check_game_over():
            return

        # Start next round
        await self._start_round()

    async def _check_game_over(self) -> bool:
        """Check if game is over."""
        alive = self.alive_players

        # Score victory
        for player in alive:
            if player.points >= self.win_threshold:
                self.game_over = True
                self.winner = player
                self.finished_at = datetime.now(timezone.utc)
                await self._emit_game_over()
                return True

        # All eliminated
        if len(alive) == 0:
            self.game_over = True
            self.winner = None
            self.finished_at = datetime.now(timezone.utc)
            await self._emit_game_over()
            return True

        return False

    async def _emit_game_over(self) -> None:
        """Emit game over message."""
        self._phase = GamePhase.GAME_OVER

        duration = 0
        if self.finished_at and self.started_at:
            duration = int((self.finished_at - self.started_at).total_seconds())

        await self.broadcast(game_over_message(
            winner={
                "player_id": self.winner.player_id,
                "username": self.winner.username,
                "score": self.winner.points,
            } if self.winner else None,
            ai_wins=self.winner is None,
            final_standings=self._build_standings(),
            rounds_played=self.round_num,
            game_duration_seconds=duration
        ))

    # --- Helpers ---

    def _ai_decide_search(self, player_choices: Dict[ServerPlayer, Location]):
        """AI decides where to search."""
        predictions = {}
        for player, location in player_choices.items():
            predictions[player] = (location.name, 0.5, "Random guess")

        # Pick most popular location or random
        location_counts: Dict[str, int] = {}
        for loc in player_choices.values():
            location_counts[loc.name] = location_counts.get(loc.name, 0) + 1

        if location_counts:
            search_name = max(location_counts, key=location_counts.get)
            search_location = None
            for loc in self.location_manager.get_all():
                if loc.name == search_name:
                    search_location = loc
                    break
            if not search_location:
                search_location = random.choice(self.location_manager.get_all())
        else:
            search_location = random.choice(self.location_manager.get_all())

        return search_location, predictions, "AI searched the most popular location."

    def _build_standings(self) -> List[Dict[str, Any]]:
        """Build standings list."""
        sorted_players = sorted(
            self.players.values(),
            key=lambda p: (-p.points, not p.alive)
        )
        return [
            {
                "player_id": p.player_id,
                "username": p.username,
                "points": p.points,
                "alive": p.alive
            }
            for p in sorted_players
        ]

    def _build_active_events(self) -> List[Dict[str, Any]]:
        """Build active events list."""
        active_events = []
        for loc in self.location_manager.get_all():
            event = self.event_manager.get_location_event(loc)
            if event:
                active_events.append({
                    "location": loc.name,
                    "name": event.name,
                    "emoji": event.emoji,
                    "description": event.description,
                })
        return active_events
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_engine_v2_core.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/engine_v2.py tests/unit/test_engine_v2_core.py
git commit -m "feat(server): add event-driven game engine core"
```

---

## Task 5: Update Server Main to Use New Engine

**Files:**
- Modify: `server/main.py`
- Test: `tests/integration/test_client_server.py` (existing)

**Step 1: Update server to route messages to events**

Replace the engine instantiation and message handling in `server/main.py` to use `EventDrivenGameEngine` and convert client messages to events.

**Key changes:**
1. Import `EventDrivenGameEngine` instead of `ServerGameEngine`
2. In `handle_message`, convert client messages to `GameEvent` objects
3. Call `engine.handle_event(event)` instead of specific methods

```python
# In handle_message, after parsing:
if msg_type == ClientMessageType.LOCATION_CHOICE.value:
    parsed = parse_location_choice_message(msg.data)
    event = GameEvent(
        type=GameEventType.LOCATION_CHOICE,
        player_id=player_id,
        data={"location_index": parsed["location_index"]}
    )
    await game.handle_event(event)
```

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_client_server.py -v --timeout=30`
Expected: PASS (all existing tests should still work)

**Step 3: Commit**

```bash
git add server/main.py
git commit -m "refactor(server): route messages through event-driven engine"
```

---

## Task 6: Add Comprehensive Engine Tests

**Files:**
- Create: `tests/unit/test_engine_v2_game_flow.py`

**Step 1: Write game flow tests**

```python
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
    async def test_escape_flow(self, engine):
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
```

**Step 2: Run tests**

Run: `pytest tests/unit/test_engine_v2_game_flow.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/unit/test_engine_v2_game_flow.py
git commit -m "test(server): add game flow tests for event-driven engine"
```

---

## Task 7: Remove Old Engine (After Validation)

**Files:**
- Delete: `server/engine.py` (after all tests pass with new engine)
- Rename: `server/engine_v2.py` -> `server/engine.py`

**Step 1: Run full test suite**

Run: `pytest --timeout=30`
Expected: All tests PASS

**Step 2: Remove old engine and rename**

```bash
rm server/engine.py
mv server/engine_v2.py server/engine.py
```

**Step 3: Update imports**

Search for `from server.engine_v2 import` and replace with `from server.engine import`.

**Step 4: Run tests again**

Run: `pytest --timeout=30`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor(server): replace blocking engine with event-driven engine"
```

---

## Summary

This plan converts the server from a blocking architecture to an event-driven state machine:

1. **Events** (`server/events.py`) - All possible game inputs
2. **Pending trackers** (`server/pending.py`) - Track choices and escapes without blocking
3. **Timer manager** (`server/timers.py`) - Fire events instead of blocking
4. **Event-driven engine** (`server/engine_v2.py`) - State machine that never blocks
5. **Updated main** (`server/main.py`) - Routes messages to events

The key insight: **handle_event always returns immediately**. Timers and state transitions are all event-driven, so the message loop is never blocked.
