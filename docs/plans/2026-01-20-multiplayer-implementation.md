# Multiplayer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a terminal client that connects to the existing server, enabling single-player, local hot-seat multiplayer, and online multiplayer.

**Architecture:** Terminal client using `rich` for UI, `websockets` for server communication. Client spawns server subprocess for local play, connects via WebSocket for all modes. Hot-seat mode handles multiple local players on one terminal.

**Tech Stack:** Python 3.9+, rich (terminal UI), websockets (networking), asyncio (async I/O)

---

## Phase 1: Unified Server ✅ COMPLETE

The server already exists and is complete:
- `server/engine.py` - Game engine (1158 lines)
- `server/protocol.py` - Message protocol (500 lines)
- `server/main.py` - WebSocket server (379 lines)
- `tests/integration/test_server_engine.py` - Server tests

---

## Phase 2: Terminal Client Foundation

### Task 1: Create Client Directory Structure

**Files:**
- Create: `client/__init__.py`
- Create: `client/connection.py`

**Step 1: Create client package**

```python
# client/__init__.py
"""Terminal client for LOOT RUN multiplayer."""
```

**Step 2: Create WebSocket connection manager**

```python
# client/connection.py
"""WebSocket connection manager for LOOT RUN client."""

import asyncio
import json
from typing import Optional, Callable, Awaitable, Dict, Any

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketClientProtocol = None

from server.protocol import Message, ClientMessageType


class ConnectionManager:
    """Manages WebSocket connection to game server."""

    def __init__(self):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.player_id: Optional[str] = None
        self.game_id: Optional[str] = None
        self.connected = False
        self._message_handler: Optional[Callable[[Message], Awaitable[None]]] = None
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self, uri: str) -> bool:
        """Connect to server at given URI."""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not installed")

        try:
            self.websocket = await websockets.connect(uri)
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self):
        """Disconnect from server."""
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    def set_message_handler(self, handler: Callable[[Message], Awaitable[None]]):
        """Set handler for incoming messages."""
        self._message_handler = handler

    async def start_receiving(self):
        """Start receiving messages in background."""
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        """Receive messages from server."""
        if not self.websocket:
            return

        try:
            async for raw_message in self.websocket:
                msg = Message.from_json(raw_message)
                if self._message_handler:
                    await self._message_handler(msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            self.connected = False

    async def send(self, message: Message):
        """Send message to server."""
        if not self.websocket or not self.connected:
            raise RuntimeError("Not connected")
        await self.websocket.send(message.to_json())

    async def send_join(self, username: str, profile_id: Optional[str] = None):
        """Send JOIN message."""
        await self.send(Message(
            type=ClientMessageType.JOIN.value,
            data={"username": username, "profile_id": profile_id}
        ))

    async def send_ready(self):
        """Send READY message."""
        await self.send(Message(type=ClientMessageType.READY.value, data={}))

    async def send_unready(self):
        """Send UNREADY message."""
        await self.send(Message(type=ClientMessageType.UNREADY.value, data={}))

    async def send_location_choice(self, location_index: int):
        """Send LOCATION_CHOICE message."""
        await self.send(Message(
            type=ClientMessageType.LOCATION_CHOICE.value,
            data={"location_index": location_index}
        ))

    async def send_escape_choice(self, option_id: str):
        """Send ESCAPE_CHOICE message."""
        await self.send(Message(
            type=ClientMessageType.ESCAPE_CHOICE.value,
            data={"option_id": option_id}
        ))

    async def send_shop_purchase(self, passive_id: str):
        """Send SHOP_PURCHASE message."""
        await self.send(Message(
            type=ClientMessageType.SHOP_PURCHASE.value,
            data={"passive_id": passive_id}
        ))

    async def send_skip_shop(self):
        """Send SKIP_SHOP message."""
        await self.send(Message(type=ClientMessageType.SKIP_SHOP.value, data={}))
```

**Step 3: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --ignore=tests/integration/test_server_engine.py -x -q`
Expected: All tests pass

**Step 4: Commit**

```bash
git add client/
git commit -m "feat: add client connection manager"
```

---

### Task 2: Create Client Game State

**Files:**
- Create: `client/state.py`

**Step 1: Create game state class**

```python
# client/state.py
"""Client-side game state management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class ClientPhase(Enum):
    """Client UI phases."""
    MAIN_MENU = "main_menu"
    CONNECTING = "connecting"
    LOBBY = "lobby"
    SHOP = "shop"
    CHOOSING = "choosing"
    WAITING = "waiting"
    RESULTS = "results"
    ESCAPE = "escape"
    GAME_OVER = "game_over"


@dataclass
class PlayerInfo:
    """Information about a player."""
    player_id: str
    username: str
    points: int = 0
    alive: bool = True
    connected: bool = True
    ready: bool = False
    passives: List[str] = field(default_factory=list)
    color: str = "white"
    is_local: bool = False  # True if this is a local player on this client


@dataclass
class LocationInfo:
    """Information about a location."""
    name: str
    emoji: str
    min_points: int
    max_points: int
    event: Optional[Dict[str, Any]] = None


@dataclass
class GameState:
    """Client-side game state."""

    # Connection state
    connected: bool = False
    player_id: Optional[str] = None
    game_id: Optional[str] = None

    # UI phase
    phase: ClientPhase = ClientPhase.MAIN_MENU

    # Game data
    round_num: int = 0
    players: Dict[str, PlayerInfo] = field(default_factory=dict)
    locations: List[LocationInfo] = field(default_factory=list)
    active_events: List[Dict[str, Any]] = field(default_factory=list)

    # Local player tracking (for hot-seat)
    local_player_ids: List[str] = field(default_factory=list)
    current_local_player_index: int = 0

    # Current round state
    timer_seconds: int = 0
    previous_ai_location: Optional[str] = None
    last_round_results: Optional[Dict[str, Any]] = None
    last_escape_result: Optional[Dict[str, Any]] = None

    # Shop state
    available_passives: List[Dict[str, Any]] = field(default_factory=list)

    # Escape state
    escape_options: List[Dict[str, Any]] = field(default_factory=list)
    caught_location: Optional[str] = None
    caught_points: int = 0

    # Game over state
    winner: Optional[Dict[str, Any]] = None
    ai_wins: bool = False
    final_standings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def current_local_player(self) -> Optional[PlayerInfo]:
        """Get the current local player for input."""
        if not self.local_player_ids:
            return None
        if self.current_local_player_index >= len(self.local_player_ids):
            return None
        pid = self.local_player_ids[self.current_local_player_index]
        return self.players.get(pid)

    def get_player(self, player_id: str) -> Optional[PlayerInfo]:
        """Get player by ID."""
        return self.players.get(player_id)

    def get_standings(self) -> List[PlayerInfo]:
        """Get players sorted by score."""
        return sorted(
            self.players.values(),
            key=lambda p: (-p.points, not p.alive)
        )

    def reset_for_new_game(self):
        """Reset state for a new game."""
        self.round_num = 0
        self.players.clear()
        self.locations.clear()
        self.active_events.clear()
        self.local_player_ids.clear()
        self.current_local_player_index = 0
        self.last_round_results = None
        self.last_escape_result = None
        self.winner = None
        self.ai_wins = False
        self.final_standings.clear()
```

**Step 2: Commit**

```bash
git add client/state.py
git commit -m "feat: add client game state management"
```

---

### Task 3: Create Client UI Components

**Files:**
- Create: `client/ui.py`

**Step 1: Create UI rendering module**

```python
# client/ui.py
"""Terminal UI components for LOOT RUN client using rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box
from typing import List, Optional, Dict, Any

from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase


console = Console()


def clear_screen():
    """Clear the terminal screen."""
    console.clear()


def print_header(title: str, subtitle: str = ""):
    """Print a styled header."""
    header_text = Text(title, style="bold cyan")
    if subtitle:
        header_text.append(f"\n{subtitle}", style="dim")
    console.print(Panel(header_text, box=box.DOUBLE))


def print_main_menu() -> str:
    """Print main menu and get choice."""
    clear_screen()
    print_header("LOOT RUN", "Multiplayer Edition")

    console.print("\n[bold]Choose an option:[/bold]\n")
    console.print("  [cyan]1.[/cyan] Single Player")
    console.print("  [cyan]2.[/cyan] Local Multiplayer (Hot-Seat)")
    console.print("  [cyan]3.[/cyan] Host Online Game")
    console.print("  [cyan]4.[/cyan] Join Online Game")
    console.print("  [cyan]5.[/cyan] Quit")
    console.print()

    while True:
        choice = console.input("[bold]Enter choice (1-5): [/bold]").strip()
        if choice in ["1", "2", "3", "4", "5"]:
            return choice
        console.print("[red]Invalid choice. Please enter 1-5.[/red]")


def print_lobby(state: GameState, is_host: bool = False):
    """Print lobby screen."""
    clear_screen()
    print_header(f"Game Lobby: {state.game_id}", "Waiting for players...")

    # Player table
    table = Table(title="Players", box=box.ROUNDED)
    table.add_column("Player", style="cyan")
    table.add_column("Status", justify="center")

    for player in state.players.values():
        status = "[green]Ready[/green]" if player.ready else "[yellow]Not Ready[/yellow]"
        if not player.connected:
            status = "[red]Disconnected[/red]"
        name = player.username
        if player.is_local:
            name += " [dim](you)[/dim]"
        table.add_row(name, status)

    console.print(table)
    console.print()

    if is_host:
        console.print("[dim]Press [bold]R[/bold] when ready, [bold]S[/bold] to start game[/dim]")
    else:
        console.print("[dim]Press [bold]R[/bold] to toggle ready[/dim]")


def print_standings(state: GameState):
    """Print current standings."""
    table = Table(title=f"Round {state.round_num} - Standings", box=box.ROUNDED)
    table.add_column("Player", style="cyan")
    table.add_column("Points", justify="right")
    table.add_column("Status", justify="center")

    for player in state.get_standings():
        status = "[green]Alive[/green]" if player.alive else "[red]Eliminated[/red]"
        name = player.username
        if player.player_id in state.local_player_ids:
            name += " [dim](you)[/dim]"
        table.add_row(name, str(player.points), status)

    console.print(table)


def print_locations(state: GameState, show_events: bool = True):
    """Print available locations."""
    table = Table(title="Locations", box=box.ROUNDED)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Location", style="cyan")
    table.add_column("Points", justify="center")
    table.add_column("Event", justify="left")

    for i, loc in enumerate(state.locations):
        event_str = ""
        if show_events and loc.event:
            event_str = f"{loc.event.get('emoji', '')} {loc.event.get('name', '')}"

        table.add_row(
            str(i + 1),
            f"{loc.emoji} {loc.name}",
            f"{loc.min_points}-{loc.max_points}",
            event_str
        )

    console.print(table)


def print_location_choice_prompt(state: GameState, player: PlayerInfo):
    """Print location choice screen."""
    clear_screen()
    print_header(f"Round {state.round_num}", f"{player.username}'s Turn")

    print_standings(state)
    console.print()

    if state.previous_ai_location:
        console.print(f"[yellow]Last round: Seeker searched {state.previous_ai_location}[/yellow]\n")

    print_locations(state)
    console.print()
    console.print(f"[bold]{player.username}[/bold], choose a location to loot (1-{len(state.locations)}):")


def print_waiting_for_players(state: GameState, submitted: List[str]):
    """Print waiting screen while others choose."""
    clear_screen()
    print_header(f"Round {state.round_num}", "Waiting for other players...")

    console.print("[dim]Players submitted:[/dim]")
    for pid in submitted:
        player = state.get_player(pid)
        if player:
            console.print(f"  [green]✓[/green] {player.username}")

    for player in state.players.values():
        if player.player_id not in submitted and player.alive:
            console.print(f"  [yellow]...[/yellow] {player.username}")


def print_round_results(state: GameState, results: Dict[str, Any]):
    """Print round results."""
    clear_screen()
    print_header(f"Round {state.round_num} Results")

    ai_loc = results.get("ai_search_location", "Unknown")
    ai_emoji = results.get("ai_search_emoji", "")
    console.print(f"\n[bold red]Seeker searched: {ai_emoji} {ai_loc}[/bold red]\n")

    for pr in results.get("player_results", []):
        username = pr.get("username", "Unknown")
        loc = pr.get("location", "")
        loc_emoji = pr.get("location_emoji", "")
        caught = pr.get("caught", False)

        if caught:
            console.print(f"[red]✗[/red] {username} was at {loc_emoji} {loc} - [red]CAUGHT![/red]")
        else:
            points = pr.get("points_earned", 0)
            total = pr.get("total_points", 0)
            console.print(f"[green]✓[/green] {username} looted {loc_emoji} {loc} - +{points} pts (Total: {total})")

    console.print()
    console.print("[dim]Press Enter to continue...[/dim]")


def print_escape_prompt(state: GameState, player: PlayerInfo):
    """Print escape options."""
    clear_screen()
    print_header("CAUGHT!", f"{player.username} must escape!")

    console.print(f"\n[yellow]You were caught at {state.caught_location}![/yellow]")
    console.print(f"[dim]Points at stake: {state.caught_points}[/dim]\n")

    table = Table(title="Escape Options", box=box.ROUNDED)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Option", style="cyan")
    table.add_column("Type", justify="center")

    for i, opt in enumerate(state.escape_options):
        opt_type = "[blue]Hide[/blue]" if opt.get("type") == "hide" else "[yellow]Run[/yellow]"
        table.add_row(str(i + 1), f"{opt.get('emoji', '')} {opt.get('name', '')}", opt_type)

    console.print(table)
    console.print()
    console.print(f"Choose escape option (1-{len(state.escape_options)}):")


def print_escape_result(result: Dict[str, Any]):
    """Print escape result."""
    clear_screen()

    escaped = result.get("escaped", False)
    username = result.get("username", "Player")
    player_choice = result.get("player_choice_name", "")
    ai_prediction = result.get("ai_prediction_name", "")

    if escaped:
        print_header("ESCAPED!", f"{username} got away!")
        points = result.get("points_awarded", 0)
        console.print(f"\n[green]You chose: {player_choice}[/green]")
        console.print(f"[red]AI predicted: {ai_prediction}[/red]")
        console.print(f"\n[bold green]Points kept: {points}[/bold green]")
    else:
        print_header("ELIMINATED!", f"{username} was caught!")
        console.print(f"\n[green]You chose: {player_choice}[/green]")
        console.print(f"[red]AI predicted: {ai_prediction}[/red]")
        console.print(f"\n[bold red]The AI predicted correctly![/bold red]")

    console.print("\n[dim]Press Enter to continue...[/dim]")


def print_game_over(state: GameState):
    """Print game over screen."""
    clear_screen()

    if state.ai_wins:
        print_header("GAME OVER", "The Seeker wins!")
        console.print("\n[red]All players have been eliminated![/red]\n")
    else:
        winner = state.winner
        print_header("GAME OVER", f"{winner.get('username', 'Unknown')} wins!")
        console.print(f"\n[green]Final score: {winner.get('score', 0)} points[/green]\n")

    # Final standings table
    table = Table(title="Final Standings", box=box.ROUNDED)
    table.add_column("Rank", style="dim", justify="right")
    table.add_column("Player", style="cyan")
    table.add_column("Score", justify="right")

    for i, standing in enumerate(state.final_standings, 1):
        table.add_row(str(i), standing.get("username", ""), str(standing.get("points", 0)))

    console.print(table)
    console.print("\n[dim]Press Enter to return to menu...[/dim]")


def print_shop(state: GameState, player: PlayerInfo):
    """Print shop screen."""
    clear_screen()
    print_header("SHOP", f"{player.username}'s Turn - Points: {player.points}")

    owned = set(player.passives)

    table = Table(title="Available Passives", box=box.ROUNDED)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Passive", style="cyan")
    table.add_column("Cost", justify="right")
    table.add_column("Status", justify="center")

    for i, passive in enumerate(state.available_passives):
        pid = passive.get("id", "")
        name = f"{passive.get('emoji', '')} {passive.get('name', '')}"
        cost = passive.get("cost", 0)

        if pid in owned:
            status = "[green]Owned[/green]"
        elif player.points >= cost:
            status = "[yellow]Available[/yellow]"
        else:
            status = "[red]Too expensive[/red]"

        table.add_row(str(i + 1), name, str(cost), status)

    console.print(table)
    console.print()
    console.print("[dim]Enter number to buy, or 'skip' to continue:[/dim]")


def get_input(prompt: str = "") -> str:
    """Get input from user."""
    return console.input(prompt).strip()


def get_location_choice(num_locations: int) -> int:
    """Get location choice from user."""
    while True:
        try:
            choice = int(get_input())
            if 1 <= choice <= num_locations:
                return choice - 1  # Return 0-indexed
            console.print(f"[red]Please enter a number between 1 and {num_locations}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")


def get_escape_choice(num_options: int) -> int:
    """Get escape choice from user."""
    while True:
        try:
            choice = int(get_input())
            if 1 <= choice <= num_options:
                return choice - 1  # Return 0-indexed
            console.print(f"[red]Please enter a number between 1 and {num_options}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")


def print_connecting(host: str, port: int):
    """Print connecting message."""
    console.print(f"[yellow]Connecting to {host}:{port}...[/yellow]")


def print_error(message: str):
    """Print error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_info(message: str):
    """Print info message."""
    console.print(f"[cyan]ℹ[/cyan] {message}")


def wait_for_enter():
    """Wait for user to press Enter."""
    console.input()
```

**Step 2: Commit**

```bash
git add client/ui.py
git commit -m "feat: add terminal UI components"
```

---

### Task 4: Create Client Message Handler

**Files:**
- Create: `client/handler.py`

**Step 1: Create message handler**

```python
# client/handler.py
"""Message handler for processing server messages."""

from typing import Callable, Awaitable, Optional
from server.protocol import Message, ServerMessageType
from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase


class MessageHandler:
    """Handles incoming server messages and updates game state."""

    def __init__(self, state: GameState):
        self.state = state
        self._on_phase_change: Optional[Callable[[ClientPhase], Awaitable[None]]] = None
        self._on_round_result: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_escape_required: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_escape_result: Optional[Callable[[dict], Awaitable[None]]] = None
        self._on_game_over: Optional[Callable[[], Awaitable[None]]] = None
        self._on_player_update: Optional[Callable[[], Awaitable[None]]] = None

    def set_callbacks(
        self,
        on_phase_change: Optional[Callable[[ClientPhase], Awaitable[None]]] = None,
        on_round_result: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_escape_required: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_escape_result: Optional[Callable[[dict], Awaitable[None]]] = None,
        on_game_over: Optional[Callable[[], Awaitable[None]]] = None,
        on_player_update: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """Set callback functions for various events."""
        self._on_phase_change = on_phase_change
        self._on_round_result = on_round_result
        self._on_escape_required = on_escape_required
        self._on_escape_result = on_escape_result
        self._on_game_over = on_game_over
        self._on_player_update = on_player_update

    async def handle(self, msg: Message):
        """Handle an incoming message."""
        msg_type = msg.type
        data = msg.data

        if msg_type == ServerMessageType.WELCOME.value:
            await self._handle_welcome(data)

        elif msg_type == ServerMessageType.LOBBY_STATE.value:
            await self._handle_lobby_state(data)

        elif msg_type == ServerMessageType.PLAYER_JOINED.value:
            await self._handle_player_joined(data)

        elif msg_type == ServerMessageType.PLAYER_LEFT.value:
            await self._handle_player_left(data)

        elif msg_type == ServerMessageType.PLAYER_READY.value:
            await self._handle_player_ready(data)

        elif msg_type == ServerMessageType.GAME_STATE.value:
            await self._handle_game_state(data)

        elif msg_type == ServerMessageType.GAME_STARTED.value:
            await self._handle_game_started(data)

        elif msg_type == ServerMessageType.ROUND_START.value:
            await self._handle_round_start(data)

        elif msg_type == ServerMessageType.PHASE_CHANGE.value:
            await self._handle_phase_change(data)

        elif msg_type == ServerMessageType.SHOP_STATE.value:
            await self._handle_shop_state(data)

        elif msg_type == ServerMessageType.PURCHASE_RESULT.value:
            await self._handle_purchase_result(data)

        elif msg_type == ServerMessageType.PLAYER_SUBMITTED.value:
            pass  # Could update UI to show who submitted

        elif msg_type == ServerMessageType.ALL_CHOICES_LOCKED.value:
            pass  # All choices in, resolution coming

        elif msg_type == ServerMessageType.AI_ANALYZING.value:
            pass  # Could show animation

        elif msg_type == ServerMessageType.ROUND_RESULT.value:
            await self._handle_round_result(data)

        elif msg_type == ServerMessageType.PLAYER_CAUGHT.value:
            pass  # Handled via ESCAPE_PHASE

        elif msg_type == ServerMessageType.ESCAPE_PHASE.value:
            await self._handle_escape_phase(data)

        elif msg_type == ServerMessageType.ESCAPE_RESULT.value:
            await self._handle_escape_result(data)

        elif msg_type == ServerMessageType.PLAYER_ELIMINATED.value:
            await self._handle_player_eliminated(data)

        elif msg_type == ServerMessageType.GAME_OVER.value:
            await self._handle_game_over(data)

        elif msg_type == ServerMessageType.ERROR.value:
            await self._handle_error(data)

    async def _handle_welcome(self, data: dict):
        """Handle WELCOME message."""
        self.state.player_id = data.get("player_id")
        self.state.game_id = data.get("game_id")
        self.state.connected = True

    async def _handle_lobby_state(self, data: dict):
        """Handle LOBBY_STATE message."""
        self.state.game_id = data.get("game_id")
        self.state.phase = ClientPhase.LOBBY

        # Update players
        self.state.players.clear()
        for p in data.get("players", []):
            player = PlayerInfo(
                player_id=p.get("player_id"),
                username=p.get("username"),
                points=p.get("points", 0),
                alive=p.get("alive", True),
                connected=p.get("connected", True),
                ready=p.get("ready", False),
                passives=p.get("passives", []),
                color=p.get("color", "white"),
                is_local=(p.get("player_id") in self.state.local_player_ids)
            )
            self.state.players[player.player_id] = player

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_joined(self, data: dict):
        """Handle PLAYER_JOINED message."""
        p = data.get("player", {})
        player = PlayerInfo(
            player_id=p.get("player_id"),
            username=p.get("username"),
            points=p.get("points", 0),
            alive=p.get("alive", True),
            connected=p.get("connected", True),
            ready=p.get("ready", False),
            passives=p.get("passives", []),
            color=p.get("color", "white"),
        )
        self.state.players[player.player_id] = player

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_left(self, data: dict):
        """Handle PLAYER_LEFT message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].connected = False

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_player_ready(self, data: dict):
        """Handle PLAYER_READY message."""
        player_id = data.get("player_id")
        ready = data.get("ready", False)
        if player_id in self.state.players:
            self.state.players[player_id].ready = ready

        if self._on_player_update:
            await self._on_player_update()

    async def _handle_game_state(self, data: dict):
        """Handle full GAME_STATE sync."""
        self.state.round_num = data.get("round_num", 0)
        self.state.previous_ai_location = data.get("previous_ai_location")

        # Update locations
        self.state.locations.clear()
        for loc in data.get("locations", []):
            self.state.locations.append(LocationInfo(
                name=loc.get("name"),
                emoji=loc.get("emoji"),
                min_points=loc.get("min_points", 0),
                max_points=loc.get("max_points", 0),
            ))

        # Update events
        self.state.active_events = data.get("active_events", [])
        self._apply_events_to_locations()

        # Update players
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid in self.state.players:
                player = self.state.players[pid]
                player.points = p.get("points", 0)
                player.alive = p.get("alive", True)
                player.connected = p.get("connected", True)
                player.ready = p.get("ready", False)
                player.passives = p.get("passives", [])

    async def _handle_game_started(self, data: dict):
        """Handle GAME_STARTED message."""
        self.state.game_id = data.get("game_id")

        # Update locations
        self.state.locations.clear()
        for loc in data.get("locations", []):
            self.state.locations.append(LocationInfo(
                name=loc.get("name"),
                emoji=loc.get("emoji"),
                min_points=loc.get("min_points", 0),
                max_points=loc.get("max_points", 0),
            ))

        # Update players
        for p in data.get("players", []):
            pid = p.get("player_id")
            if pid in self.state.players:
                self.state.players[pid].points = p.get("points", 0)
                self.state.players[pid].alive = p.get("alive", True)

    async def _handle_round_start(self, data: dict):
        """Handle ROUND_START message."""
        self.state.round_num = data.get("round_num", 0)
        self.state.timer_seconds = data.get("timer_seconds", 30)
        self.state.previous_ai_location = data.get("previous_ai_location")
        self.state.active_events = data.get("active_events", [])
        self._apply_events_to_locations()

        self.state.phase = ClientPhase.CHOOSING
        self.state.current_local_player_index = 0

        if self._on_phase_change:
            await self._on_phase_change(ClientPhase.CHOOSING)

    async def _handle_phase_change(self, data: dict):
        """Handle PHASE_CHANGE message."""
        phase_str = data.get("phase", "")

        if phase_str == "shop":
            self.state.phase = ClientPhase.SHOP
        elif phase_str == "choosing":
            self.state.phase = ClientPhase.CHOOSING
        elif phase_str == "resolving":
            self.state.phase = ClientPhase.WAITING
        elif phase_str == "escape":
            self.state.phase = ClientPhase.ESCAPE

        if self._on_phase_change:
            await self._on_phase_change(self.state.phase)

    async def _handle_shop_state(self, data: dict):
        """Handle SHOP_STATE message."""
        self.state.available_passives = data.get("available_passives", [])

        # Update player points
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].points = data.get("player_points", 0)

        self.state.phase = ClientPhase.SHOP
        if self._on_phase_change:
            await self._on_phase_change(ClientPhase.SHOP)

    async def _handle_purchase_result(self, data: dict):
        """Handle PURCHASE_RESULT message."""
        if data.get("success"):
            player_id = data.get("player_id")
            if player_id in self.state.players:
                self.state.players[player_id].points = data.get("new_points", 0)
                passive_name = data.get("passive_name")
                if passive_name:
                    # Find passive ID by name and add to player
                    for p in self.state.available_passives:
                        if p.get("name") == passive_name:
                            self.state.players[player_id].passives.append(p.get("id"))
                            break

    async def _handle_round_result(self, data: dict):
        """Handle ROUND_RESULT message."""
        self.state.last_round_results = data
        self.state.phase = ClientPhase.RESULTS

        # Update player points from standings
        for standing in data.get("standings", []):
            pid = standing.get("player_id")
            if pid in self.state.players:
                self.state.players[pid].points = standing.get("points", 0)
                self.state.players[pid].alive = standing.get("alive", True)

        if self._on_round_result:
            await self._on_round_result(data)

    async def _handle_escape_phase(self, data: dict):
        """Handle ESCAPE_PHASE message."""
        player_id = data.get("player_id")

        # Only handle if this is for a local player
        if player_id in self.state.local_player_ids:
            self.state.escape_options = data.get("escape_options", [])
            self.state.caught_location = data.get("location")
            self.state.caught_points = data.get("location_points", 0)
            self.state.phase = ClientPhase.ESCAPE

            if self._on_escape_required:
                await self._on_escape_required(data)

    async def _handle_escape_result(self, data: dict):
        """Handle ESCAPE_RESULT message."""
        self.state.last_escape_result = data

        # Update player state
        player_id = data.get("player_id")
        if player_id in self.state.players:
            if data.get("escaped"):
                points = data.get("points_awarded", 0)
                # Points already added server-side, we get updated from standings
            else:
                self.state.players[player_id].alive = False

        if self._on_escape_result:
            await self._on_escape_result(data)

    async def _handle_player_eliminated(self, data: dict):
        """Handle PLAYER_ELIMINATED message."""
        player_id = data.get("player_id")
        if player_id in self.state.players:
            self.state.players[player_id].alive = False
            self.state.players[player_id].points = data.get("final_score", 0)

    async def _handle_game_over(self, data: dict):
        """Handle GAME_OVER message."""
        self.state.winner = data.get("winner")
        self.state.ai_wins = data.get("ai_wins", False)
        self.state.final_standings = data.get("final_standings", [])
        self.state.phase = ClientPhase.GAME_OVER

        if self._on_game_over:
            await self._on_game_over()

    async def _handle_error(self, data: dict):
        """Handle ERROR message."""
        # Could display error to user
        pass

    def _apply_events_to_locations(self):
        """Apply active events to location info."""
        for loc in self.state.locations:
            loc.event = None

        for event in self.state.active_events:
            loc_name = event.get("location")
            for loc in self.state.locations:
                if loc.name == loc_name:
                    loc.event = event
                    break
```

**Step 2: Commit**

```bash
git add client/handler.py
git commit -m "feat: add client message handler"
```

---

### Task 5: Create Main Client Application

**Files:**
- Create: `client/main.py`

**Step 1: Create main client entry point**

```python
# client/main.py
"""Main entry point for LOOT RUN terminal client."""

import asyncio
import sys
from typing import Optional

from client.connection import ConnectionManager
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from client import ui


class GameClient:
    """Main game client application."""

    def __init__(self):
        self.connection = ConnectionManager()
        self.state = GameState()
        self.handler = MessageHandler(self.state)
        self._running = False
        self._server_process = None

        # Set up callbacks
        self.handler.set_callbacks(
            on_phase_change=self._on_phase_change,
            on_round_result=self._on_round_result,
            on_escape_required=self._on_escape_required,
            on_escape_result=self._on_escape_result,
            on_game_over=self._on_game_over,
            on_player_update=self._on_player_update,
        )

    async def run(self):
        """Run the main client loop."""
        self._running = True

        while self._running:
            choice = ui.print_main_menu()

            if choice == "1":
                await self._play_single_player()
            elif choice == "2":
                await self._play_local_multiplayer()
            elif choice == "3":
                await self._host_online_game()
            elif choice == "4":
                await self._join_online_game()
            elif choice == "5":
                self._running = False

        await self._cleanup()

    async def _play_single_player(self):
        """Start single player game."""
        # Get player name
        ui.clear_screen()
        ui.print_header("Single Player")
        name = ui.get_input("Enter your name: ") or "Player"

        # Start local server and connect
        await self._start_local_server()
        if not await self._connect_to_server("localhost", 8765, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Set ready and wait for game
        await self.connection.send_ready()
        await self._game_loop()

    async def _play_local_multiplayer(self):
        """Start local multiplayer (hot-seat)."""
        ui.clear_screen()
        ui.print_header("Local Multiplayer")

        # Get number of players
        while True:
            try:
                num = int(ui.get_input("Number of players (2-6): "))
                if 2 <= num <= 6:
                    break
                ui.print_error("Please enter a number between 2 and 6")
            except ValueError:
                ui.print_error("Please enter a valid number")

        # Get player names
        names = []
        for i in range(num):
            name = ui.get_input(f"Player {i+1} name: ") or f"Player {i+1}"
            names.append(name)

        # Start local server
        await self._start_local_server()

        # Connect first player
        if not await self._connect_to_server("localhost", 8765, names[0]):
            return

        self.state.local_player_ids = [self.state.player_id]

        # For hot-seat, we track all players but use one connection
        # The server treats each "join" as a new player
        # We need to modify this for proper hot-seat...

        # For now, single connection handles multiple local players
        # Server needs modification to support this properly
        # This is a placeholder implementation

        await self.connection.send_ready()
        await self._game_loop()

    async def _host_online_game(self):
        """Host an online game."""
        ui.clear_screen()
        ui.print_header("Host Online Game")
        name = ui.get_input("Enter your name: ") or "Host"

        # Start local server exposed to network
        await self._start_local_server(expose=True)
        if not await self._connect_to_server("localhost", 8765, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Show lobby and wait for ready
        await self._lobby_loop(is_host=True)

    async def _join_online_game(self):
        """Join an online game."""
        ui.clear_screen()
        ui.print_header("Join Online Game")

        # Get server address
        host = ui.get_input("Server IP (or 'scan' for LAN): ") or "localhost"
        if host == "scan":
            # TODO: LAN discovery
            ui.print_info("LAN discovery not yet implemented. Using localhost.")
            host = "localhost"

        port = 8765
        port_str = ui.get_input("Port (default 8765): ")
        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                pass

        name = ui.get_input("Enter your name: ") or "Player"

        if not await self._connect_to_server(host, port, name):
            return

        self.state.local_player_ids = [self.state.player_id]

        # Show lobby and wait for game start
        await self._lobby_loop(is_host=False)

    async def _start_local_server(self, expose: bool = False):
        """Start local server subprocess."""
        import subprocess

        host = "0.0.0.0" if expose else "127.0.0.1"
        self._server_process = subprocess.Popen(
            [sys.executable, "-m", "server.main", "--host", host, "--port", "8765"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Wait for server to start
        await asyncio.sleep(0.5)

    async def _connect_to_server(self, host: str, port: int, username: str) -> bool:
        """Connect to game server."""
        ui.print_connecting(host, port)

        try:
            await self.connection.connect(f"ws://{host}:{port}")
            self.connection.set_message_handler(self.handler.handle)
            await self.connection.start_receiving()

            await self.connection.send_join(username)

            # Wait for welcome
            for _ in range(50):  # 5 second timeout
                await asyncio.sleep(0.1)
                if self.state.connected and self.state.player_id:
                    ui.print_info(f"Connected! Game ID: {self.state.game_id}")
                    return True

            ui.print_error("Connection timeout")
            return False

        except Exception as e:
            ui.print_error(f"Failed to connect: {e}")
            return False

    async def _lobby_loop(self, is_host: bool):
        """Run lobby waiting loop."""
        self.state.phase = ClientPhase.LOBBY

        while self.state.phase == ClientPhase.LOBBY:
            ui.print_lobby(self.state, is_host)

            # Simple input handling
            inp = ui.get_input("> ").lower()

            if inp == "r":
                player = self.state.players.get(self.state.player_id)
                if player and player.ready:
                    await self.connection.send_unready()
                else:
                    await self.connection.send_ready()

            elif inp == "s" and is_host:
                # Start game (by setting ready, game auto-starts when all ready)
                await self.connection.send_ready()

            await asyncio.sleep(0.1)

        # Game started, enter game loop
        await self._game_loop()

    async def _game_loop(self):
        """Main game loop."""
        while self.state.phase not in [ClientPhase.GAME_OVER, ClientPhase.MAIN_MENU]:
            await asyncio.sleep(0.1)

        # Show game over and return
        if self.state.phase == ClientPhase.GAME_OVER:
            ui.print_game_over(self.state)
            ui.wait_for_enter()

    async def _on_phase_change(self, phase: ClientPhase):
        """Handle phase change."""
        if phase == ClientPhase.SHOP:
            await self._handle_shop_phase()
        elif phase == ClientPhase.CHOOSING:
            await self._handle_choosing_phase()

    async def _handle_shop_phase(self):
        """Handle shop phase."""
        player = self.state.current_local_player
        if not player or not player.alive:
            await self.connection.send_skip_shop()
            return

        ui.print_shop(self.state, player)

        while self.state.phase == ClientPhase.SHOP:
            inp = ui.get_input("> ").lower()

            if inp == "skip" or inp == "s":
                await self.connection.send_skip_shop()
                break

            try:
                idx = int(inp) - 1
                if 0 <= idx < len(self.state.available_passives):
                    passive = self.state.available_passives[idx]
                    await self.connection.send_shop_purchase(passive.get("id"))
                    await asyncio.sleep(0.2)  # Wait for result
                    ui.print_shop(self.state, player)
            except ValueError:
                pass

    async def _handle_choosing_phase(self):
        """Handle location choosing phase."""
        # For each local player
        for i, pid in enumerate(self.state.local_player_ids):
            player = self.state.players.get(pid)
            if not player or not player.alive:
                continue

            self.state.current_local_player_index = i
            ui.print_location_choice_prompt(self.state, player)

            choice = ui.get_location_choice(len(self.state.locations))
            await self.connection.send_location_choice(choice)

            # If more players, clear screen for next
            if i < len(self.state.local_player_ids) - 1:
                ui.clear_screen()
                ui.print_info("Pass to next player...")
                ui.wait_for_enter()

    async def _on_round_result(self, results: dict):
        """Handle round results."""
        ui.print_round_results(self.state, results)
        ui.wait_for_enter()

    async def _on_escape_required(self, data: dict):
        """Handle escape phase."""
        player_id = data.get("player_id")
        player = self.state.players.get(player_id)
        if not player:
            return

        ui.print_escape_prompt(self.state, player)
        choice_idx = ui.get_escape_choice(len(self.state.escape_options))
        option_id = self.state.escape_options[choice_idx].get("id")
        await self.connection.send_escape_choice(option_id)

    async def _on_escape_result(self, result: dict):
        """Handle escape result."""
        ui.print_escape_result(result)
        ui.wait_for_enter()

    async def _on_game_over(self):
        """Handle game over."""
        self.state.phase = ClientPhase.GAME_OVER

    async def _on_player_update(self):
        """Handle player list update."""
        # Could refresh lobby display
        pass

    async def _cleanup(self):
        """Clean up resources."""
        await self.connection.disconnect()

        if self._server_process:
            self._server_process.terminate()
            self._server_process = None


def main():
    """Main entry point."""
    client = GameClient()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
```

**Step 2: Commit**

```bash
git add client/main.py
git commit -m "feat: add main client application"
```

---

## Phase 3: Local Play Integration

### Task 6: Test Single Player End-to-End

**Files:**
- Modify: `client/main.py` (debugging only if needed)

**Step 1: Run single player test**

Run: `python -m client.main`
Expected: Menu appears, can start single player game, connect to server, play rounds

**Step 2: Fix any issues discovered during testing**

Debug and fix connection issues, UI problems, or message handling bugs.

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix: resolve single player integration issues"
```

---

### Task 7: Implement Hot-Seat Local Multiplayer

**Files:**
- Modify: `server/main.py` (add support for multiple players per connection)
- Modify: `client/main.py` (hot-seat flow)

**Step 1: Update server to handle multiple local players**

The server needs to support a single WebSocket connection representing multiple players. Add a `LOCAL_PLAYERS` message type.

**Step 2: Update client hot-seat flow**

Ensure each local player can submit their choice without seeing others' choices.

**Step 3: Test local multiplayer**

Run: `python -m client.main`
Select option 2, create 2 players, verify hot-seat works.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: implement hot-seat local multiplayer"
```

---

## Phase 4: Online Play

### Task 8: Add LAN Discovery

**Files:**
- Create: `client/lan.py`

**Step 1: Create LAN discovery module**

```python
# client/lan.py
"""LAN game discovery using UDP broadcast."""

import asyncio
import socket
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


DISCOVERY_PORT = 19132
BROADCAST_INTERVAL = 2.0


@dataclass
class DiscoveredGame:
    """Information about a discovered game."""
    host: str
    port: int
    game_name: str
    host_name: str
    player_count: int
    max_players: int


class LANDiscovery:
    """Handles LAN game discovery."""

    def __init__(self):
        self._broadcast_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._discovered_games: Dict[str, DiscoveredGame] = {}
        self._running = False

    async def start_broadcasting(self, port: int, game_name: str, host_name: str, player_count: int = 1, max_players: int = 6):
        """Start broadcasting game presence."""
        self._running = True

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        message = json.dumps({
            "type": "LOOT_RUN_GAME",
            "port": port,
            "game_name": game_name,
            "host_name": host_name,
            "player_count": player_count,
            "max_players": max_players,
        }).encode()

        async def broadcast_loop():
            while self._running:
                try:
                    sock.sendto(message, ('<broadcast>', DISCOVERY_PORT))
                except Exception:
                    pass
                await asyncio.sleep(BROADCAST_INTERVAL)

        self._broadcast_task = asyncio.create_task(broadcast_loop())

    async def stop_broadcasting(self):
        """Stop broadcasting."""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def scan_for_games(self, timeout: float = 3.0) -> List[DiscoveredGame]:
        """Scan for games on LAN."""
        self._discovered_games.clear()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', DISCOVERY_PORT))
        sock.setblocking(False)

        loop = asyncio.get_event_loop()
        end_time = loop.time() + timeout

        while loop.time() < end_time:
            try:
                data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 1024),
                    timeout=0.5
                )
                self._process_discovery(data, addr[0])
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

        sock.close()
        return list(self._discovered_games.values())

    def _process_discovery(self, data: bytes, host: str):
        """Process a discovery message."""
        try:
            msg = json.loads(data.decode())
            if msg.get("type") != "LOOT_RUN_GAME":
                return

            game = DiscoveredGame(
                host=host,
                port=msg.get("port", 8765),
                game_name=msg.get("game_name", "Unknown"),
                host_name=msg.get("host_name", "Unknown"),
                player_count=msg.get("player_count", 0),
                max_players=msg.get("max_players", 6),
            )

            key = f"{host}:{game.port}"
            self._discovered_games[key] = game

        except Exception:
            pass
```

**Step 2: Integrate LAN discovery into client**

Update `_join_online_game` in `client/main.py` to use LAN scanning.

**Step 3: Update server to broadcast when hosting**

**Step 4: Commit**

```bash
git add client/lan.py
git add -A
git commit -m "feat: add LAN game discovery"
```

---

### Task 9: Test Online Multiplayer

**Step 1: Test host/join flow**

1. Run server on one terminal: `python -m client.main` → Host Online Game
2. Run client on another terminal: `python -m client.main` → Join Online Game
3. Verify both can play together

**Step 2: Fix any issues**

**Step 3: Commit fixes**

```bash
git add -A
git commit -m "fix: resolve online multiplayer issues"
```

---

## Phase 5: Polish

### Task 10: Add Error Handling

**Files:**
- Modify: `client/main.py`
- Modify: `client/connection.py`

**Step 1: Add reconnection logic**

Handle connection drops gracefully with reconnection attempts.

**Step 2: Add user-friendly error messages**

**Step 3: Commit**

```bash
git add -A
git commit -m "feat: add error handling and reconnection"
```

---

### Task 11: Final Testing and Cleanup

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass

**Step 2: Test all game modes manually**

- Single player
- Local multiplayer (2+ players)
- Host online
- Join online

**Step 3: Clean up old/unused code**

Remove `server/core/` directory (old implementation).
Remove web client files if any remain.

**Step 4: Update requirements.txt**

Ensure `websockets` is in requirements.

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: cleanup and finalize multiplayer implementation"
```

---

## Summary

**Total Tasks:** 11
**Estimated commits:** 11+

**Key files created:**
- `client/__init__.py`
- `client/connection.py`
- `client/state.py`
- `client/ui.py`
- `client/handler.py`
- `client/main.py`
- `client/lan.py`

**Key files modified:**
- `server/main.py` (hot-seat support)
- `requirements.txt` (websockets)
