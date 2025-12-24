"""Terminal UI helpers using rich library."""
import sys
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from typing import List, Dict, Any
from game.player import Player
from game.locations import Location, LocationManager
from game.items import ItemShop, ItemType


console = Console()


def clear():
    """Clear the console."""
    # Use system command for proper clearing on Windows
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
    # Fallback to Rich's clear (though it doesn't work as well on Windows)
    console.clear()


def print_header(text: str):
    """Print a styled header."""
    console.print(f"\n[bold cyan]{'=' * 50}[/bold cyan]")
    console.print(f"[bold cyan]{text.center(50)}[/bold cyan]")
    console.print(f"[bold cyan]{'=' * 50}[/bold cyan]\n")


def print_standings(players: List[Player], player_choices: Dict[Player, Location] = None):
    """Print current standings with optional location choices."""
    alive_players = [p for p in players if p.alive]
    alive_players.sort(key=lambda p: p.points, reverse=True)

    table = Table(title="Current Standings", show_header=True)
    table.add_column("Rank", style="cyan", width=6)
    table.add_column("Player", style="green")
    table.add_column("Points", justify="right", style="yellow")
    table.add_column("Items", style="magenta")

    # Add choice column if choices are being tracked
    if player_choices is not None:
        table.add_column("Location Choice", style="cyan")

    for i, player in enumerate(alive_players, 1):
        items_str = ", ".join(item.name for item in player.get_active_items()) or "-"

        row = [
            f"{i}.",
            player.name,
            str(player.points),
            items_str
        ]

        # Add choice info if tracking
        if player_choices is not None:
            if player in player_choices:
                loc = player_choices[player]
                choice_str = f"{loc.emoji} {loc.name}"
            else:
                choice_str = "[dim]Pending...[/dim]"
            row.append(choice_str)

        table.add_row(*row)

    console.print(table)
    console.print()


def print_locations(location_manager: LocationManager, previous_ai_location: Location = None):
    """Print available loot locations."""
    console.print("[bold]AVAILABLE LOOT THIS ROUND:[/bold]")

    if previous_ai_location:
        console.print(f"[dim]Last round AI searched: {previous_ai_location.emoji} {previous_ai_location.name}[/dim]")

    console.print()

    # Clean single-column list
    locations = location_manager.get_all()
    for i, loc in enumerate(locations, 1):
        console.print(f"  [{i}] {loc.emoji} {loc.name:<22} [yellow]{loc.get_range_str():>6} pts[/yellow]")

    console.print()


def print_shop_boxed():
    """Print item shop in a bordered panel."""
    from game.items import ItemShop, ItemType

    ItemShop._load_items()

    # Build shop content
    lines = []
    for i, item_type in enumerate(ItemType, 1):
        item = ItemShop.ITEMS[item_type]
        lines.append(f"[bold cyan][{i}][/bold cyan] [yellow]{item.name}[/yellow] - [green]{item.cost} pts[/green]")
        lines.append(f"    [dim]{item.description}[/dim]")
        if i < len(ItemType):
            lines.append("")

    lines.append("")
    lines.append("[dim]Press Enter to skip purchase[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="🛒 ITEM SHOP",
        border_style="yellow",
        padding=(1, 2)
    )

    console.print(panel)


def print_shop():
    """Print item shop."""
    print_shop_boxed()
    console.print()


def get_player_input(prompt: str, valid_range: range = None) -> str:
    """Get input from player with optional validation."""
    while True:
        response = console.input(f"[bold green]{prompt}[/bold green] ")
        if valid_range and response.lower() != "skip":
            try:
                num = int(response)
                if num in valid_range:
                    return response
                console.print(f"[red]Please enter a number between {valid_range.start} and {valid_range.stop - 1}[/red]")
            except ValueError:
                console.print(f"[red]Invalid input. Please enter a number or 'skip'[/red]")
        else:
            return response


def show_scanner_results(predictions: List[tuple]):
    """Show Scanner item results (AI's top predictions)."""
    console.print("\n[bold cyan]🔍 SCANNER ACTIVATED:[/bold cyan]")
    console.print("AI's top search predictions:")
    for i, (location_name, confidence, reason) in enumerate(predictions[:2], 1):
        console.print(f"{i}. [yellow]{location_name}[/yellow] (confidence: {confidence:.0%}) - \"{reason}\"")
    console.print()


def show_intel_report(player: Player, threat_level: float, predictability: float, insights: List[str]):
    """Show Intel Report for a player."""
    console.print()
    panel_content = []

    # Threat level bar
    bar_length = 10
    filled = int(threat_level * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    threat_label = "HIGH" if threat_level > 0.7 else "MODERATE" if threat_level > 0.4 else "LOW"

    panel_content.append(f"⚠️  AI THREAT LEVEL: {bar} {threat_level:.0%} ({threat_label})")
    panel_content.append("")
    panel_content.append(f"Predictability Score: {predictability:.0%}")

    if predictability > 0.6:
        panel_content.append("The AI has identified patterns in your behavior.")
    else:
        panel_content.append("The AI is struggling to predict your moves.")

    panel_content.append("")
    panel_content.append("What the AI sees:")
    for insight in insights:
        panel_content.append(f"  • {insight}")

    console.print(Panel("\n".join(panel_content), title="📊 INTEL REPORT", border_style="cyan"))
    console.print()


def show_ai_thinking():
    """Show AI thinking animation."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]🤖 AI ANALYZING...", total=None)
        import time
        time.sleep(1.5)  # Dramatic pause


def create_progress_spinner(description: str):
    """Create a progress spinner for loading operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    )


def print_reveal_header():
    """Print reveal phase header."""
    print_header("REVEAL & RESOLUTION")


def print_player_choice(player: Player, location: Location, predicted_location: str,
                       confidence: float, reasoning: str):
    """Print a player's choice and AI's prediction."""
    points_to_win = max(0, 100 - player.points)

    console.print(f"[bold]{player.name}[/bold] ({player.points} pts{f', {points_to_win} pts to win' if points_to_win <= 20 else ''}):")
    console.print(f"  Chose: [green]{location.emoji} {location.name}[/green] ({location.get_range_str()} pts)")
    console.print(f"  AI Predicted: [yellow]{predicted_location}[/yellow] ({confidence:.0%} confidence)")
    console.print(f"  Reasoning: \"{reasoning}\"")
    console.print()


def print_search_result(location: Location, previous_location: Location = None, reasoning: str = ""):
    """Print which location the AI searched and why."""
    console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print(f"[bold red]🎯 AI SEARCHES: {location.emoji} {location.name.upper()}[/bold red]")

    if reasoning:
        console.print(f"[yellow]Reasoning: {reasoning}[/yellow]")

    if previous_location:
        console.print(f"[dim]Last round: {previous_location.emoji} {previous_location.name}[/dim]")

    console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold cyan]")
    console.print()


def print_player_caught(player: Player, shield_saved: bool = False):
    """Print that a player was caught."""
    if shield_saved:
        console.print(f"[yellow]💀 {player.name} was caught![/yellow]")
        console.print(f"[green]   Shield activated! {player.name} survives but gains 0 points.[/green]")
        console.print(f"[dim]   {player.name}'s Shield is consumed.[/dim]")
    else:
        console.print(f"[bold red]💀 {player.name} was caught! ELIMINATED[/bold red]")
        console.print(f"[dim]   Final score: {player.points} pts[/dim]")
    console.print()


def print_player_looted(player: Player, location: Location, points_earned: int,
                       base_roll: int = None, used_lucky_charm: bool = False):
    """Print that a player successfully looted."""
    if used_lucky_charm and base_roll is not None:
        # Show breakdown
        breakdown = f"[{base_roll} x 2 (Lucky Charm)]"
        console.print(f"[green]✅ {player.name} looted {location.name}: +{points_earned} pts {breakdown} ({player.points} total)[/green]")
    else:
        # Normal display
        console.print(f"[green]✅ {player.name} looted {location.name}: +{points_earned} pts ({player.points} total)[/green]")


def print_game_over(winner: Player):
    """Print game over message."""
    console.print()
    console.print("[bold green]" + "=" * 50 + "[/bold green]")
    console.print(f"[bold green]🎉 {winner.name} WINS with {winner.points} points! 🎉[/bold green]")
    console.print("[bold green]" + "=" * 50 + "[/bold green]")
    console.print()


def print_ai_victory():
    """Print AI victory message."""
    console.print()
    console.print("[bold red]" + "=" * 50 + "[/bold red]")
    console.print("[bold red]🤖 AI WINS! All players eliminated! 🤖[/bold red]")
    console.print("[bold red]" + "=" * 50 + "[/bold red]")
    console.print()


def print_post_game_report(player: Player, insights: Dict[str, Any]):
    """Print detailed post-game report for eliminated/finished player."""
    console.print()
    console.print(f"[bold cyan]📊 {player.name.upper()}'S POST-GAME REPORT[/bold cyan]")
    console.print()

    # Game performance
    console.print("[bold]Game Performance:[/bold]")
    console.print(f"  Rounds survived: {len(player.choice_history)}")
    console.print(f"  Total points: {player.points}")

    if player.choice_history:
        from collections import Counter
        location_counts = Counter(player.choice_history)
        top_locations = location_counts.most_common(3)
        locations_str = ", ".join(f"{loc}({cnt})" for loc, cnt in top_locations)
        console.print(f"  Top locations: {locations_str}")

    console.print()

    # AI's view
    behavior = player.get_behavior_summary()
    console.print("[bold]AI's View of You:[/bold]")

    risk_level = behavior['avg_location_value']
    risk_bar_length = int((risk_level / 35) * 10)  # 35 is max (Bank Vault)
    risk_bar = "█" * risk_bar_length + "░" * (10 - risk_bar_length)
    risk_label = "HIGH" if risk_level > 18 else "MODERATE" if risk_level > 12 else "LOW"
    console.print(f"  Risk Tolerance: {risk_bar} {risk_label} ({risk_level:.1f} avg points)")

    predictability = insights.get('predictability', 0)
    pred_bar_length = int(predictability * 10)
    pred_bar = "█" * pred_bar_length + "░" * (10 - pred_bar_length)
    pred_label = "HIGH" if predictability > 0.7 else "MODERATE" if predictability > 0.4 else "LOW"
    console.print(f"  Predictability: {pred_bar} {pred_label} ({predictability:.0%})")

    console.print()

    # What gave them away
    if 'patterns' in insights and insights['patterns']:
        console.print("[bold]What gave you away:[/bold]")
        for pattern in insights['patterns']:
            console.print(f"  • {pattern}")
        console.print()

    # Tips
    if 'tips' in insights and insights['tips']:
        console.print("[bold yellow]💡 Tips for next game:[/bold yellow]")
        for tip in insights['tips']:
            console.print(f"  • {tip}")
        console.print()
