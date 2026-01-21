# client/ui.py
"""Terminal UI components for LOOT RUN client using rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
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
