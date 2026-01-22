# client/ui.py
"""Terminal UI components for LOOT RUN client using rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from typing import List, Optional, Dict, Any
import questionary

from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase
from version import VERSION


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
    """Print main menu and get choice using arrow key selection."""
    clear_screen()
    print_header(f"LOOT RUN          [{VERSION}]", "Multiplayer Edition")
    console.print()

    choices = [
        {"name": "Single Player", "value": "1"},
        {"name": "Local Multiplayer (Hot-Seat)", "value": "2"},
        {"name": "Host Online Game", "value": "3"},
        {"name": "Join Online Game", "value": "4"},
        {"name": "Quit", "value": "5"},
    ]

    result = questionary.select(
        "Choose an option:",
        choices=[c["name"] for c in choices],
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    # Map selection back to value
    for c in choices:
        if c["name"] == result:
            return c["value"]
    return "5"  # Default to quit if something goes wrong


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
    """Print escape options header."""
    clear_screen()
    print_header("CAUGHT!", f"{player.username} must escape!")

    console.print(f"\n[yellow]You were caught at {state.caught_location}![/yellow]")
    console.print(f"[dim]Points at stake: {state.caught_points}[/dim]\n")


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
        winner = state.winner or {}
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
    """Print shop header."""
    clear_screen()
    print_header("SHOP", f"{player.username}'s Turn - Points: {player.points}")


def get_shop_choice(state: GameState, player: PlayerInfo) -> Optional[int]:
    """Get shop choice from user using arrow key selection. Returns None to skip."""
    owned = set(player.passives)

    choices = []
    for passive in state.available_passives:
        pid = passive.get("id", "")
        name = f"{passive.get('emoji', '')} {passive.get('name', '')}"
        cost = passive.get("cost", 0)

        if pid in owned:
            status = "(Owned)"
        elif player.points >= cost:
            status = f"({cost} pts)"
        else:
            status = f"({cost} pts - Too expensive)"

        choices.append(f"{name} {status}")

    choices.append("Skip - Continue to game")

    result = questionary.select(
        "Buy a passive or skip:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    # Check if skip was selected
    if result == "Skip - Continue to game":
        return None

    # Return index of selected passive
    for i, choice in enumerate(choices[:-1]):  # Exclude "Skip" option
        if choice == result:
            return i
    return None


def get_input(prompt: str = "") -> str:
    """Get input from user."""
    return console.input(prompt).strip()


def get_lobby_action(is_host: bool, is_ready: bool) -> Optional[str]:
    """Get lobby action from user using questionary menu.

    Args:
        is_host: Whether the current player is the host
        is_ready: Whether the current player is ready

    Returns:
        Action string: "ready", "unready", "start", or None if cancelled
    """
    choices = []

    if is_ready:
        choices.append({"name": "Not Ready", "value": "unready"})
    else:
        choices.append({"name": "Ready", "value": "ready"})

    if is_host:
        choices.append({"name": "Start Game", "value": "start"})

    choices.append({"name": "Refresh", "value": "refresh"})

    result = questionary.select(
        "What would you like to do?",
        choices=[c["name"] for c in choices],
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    if result is None:
        return None

    for c in choices:
        if c["name"] == result:
            return c["value"]
    return None


def get_location_choice(state: GameState) -> int:
    """Get location choice from user using arrow key selection."""
    # Defensive check: if no locations available, return 0 and log error
    if not state.locations:
        print_error("No locations available. This may be a sync issue.")
        return 0

    choices = []
    for loc in state.locations:
        event_str = ""
        if loc.event:
            event_str = f" [{loc.event.get('name', '')}]"
        choices.append(f"{loc.emoji} {loc.name} ({loc.min_points}-{loc.max_points} pts){event_str}")

    result = questionary.select(
        "Choose a location to loot:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    # Return index of selected location
    for i, choice in enumerate(choices):
        if choice == result:
            return i
    return 0


def get_escape_choice(state: GameState) -> int:
    """Get escape choice from user using arrow key selection."""
    choices = []
    for opt in state.escape_options:
        opt_type = "[Hide]" if opt.get("type") == "hide" else "[Run]"
        choices.append(f"{opt.get('emoji', '')} {opt.get('name', '')} {opt_type}")

    result = questionary.select(
        "Choose your escape:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    # Return index of selected option
    for i, choice in enumerate(choices):
        if choice == result:
            return i
    return 0


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


def get_player_count() -> int:
    """Get number of players for local multiplayer using arrow key selection."""
    choices = ["2 Players", "3 Players", "4 Players", "5 Players", "6 Players"]

    result = questionary.select(
        "How many players?",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    # Extract number from selection
    for i, choice in enumerate(choices):
        if choice == result:
            return i + 2  # 2-6 players
    return 2


def get_player_name(player_num: int) -> str:
    """Get player name using text input."""
    name = questionary.text(
        f"Player {player_num} name:",
        default=f"Player {player_num}"
    ).ask()
    return name or f"Player {player_num}"


def get_host_name() -> str:
    """Get host player name."""
    name = questionary.text(
        "Enter your name:",
        default="Host"
    ).ask()
    return name or "Host"


def get_game_name() -> str:
    """Get game name for hosting."""
    name = questionary.text(
        "Game name:",
        default="LOOT RUN"
    ).ask()
    return name or "LOOT RUN"


def get_server_address() -> str:
    """Get server address to join."""
    choices = ["Scan for LAN games", "Enter IP address manually"]

    result = questionary.select(
        "How to find game?",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    if result == "Scan for LAN games":
        return "scan"
    else:
        addr = questionary.text(
            "Server IP address:",
            default="localhost"
        ).ask()
        return addr or "localhost"


def select_lan_game(games: list) -> Optional[int]:
    """Select a game from LAN discovery results. Returns index or None to cancel.

    Shows version information for each game and marks incompatible games with
    a warning indicator when the server version doesn't match the client version.
    """
    if not games:
        return None

    choices = []
    for game in games:
        # Check version compatibility
        is_compatible = game.version == VERSION
        version_display = f"[{game.version}]"

        if is_compatible:
            version_indicator = ""
        else:
            version_indicator = " [!]"

        choice_text = (
            f"{game.game_name} - {game.host_name} "
            f"({game.player_count}/{game.max_players}) "
            f"{version_display}{version_indicator}"
        )
        choices.append(choice_text)
    choices.append("Cancel - Return to menu")

    result = questionary.select(
        "Select a game to join:",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
    ).ask()

    if result == "Cancel - Return to menu":
        return None

    for i, choice in enumerate(choices[:-1]):
        if choice == result:
            return i
    return None
