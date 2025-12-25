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
from game.passives import PassiveShop, PassiveType
from game.animations import play_elimination_animation, play_victory_animation, play_escape_animation


console = Console()


def flush_input():
    """Flush any buffered keyboard input (prevents enter spam from skipping prompts)."""
    if sys.platform == 'win32':
        try:
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        except:
            pass
    else:
        try:
            import termios
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except:
            pass


def clear():
    """Clear the console."""
    # Use system command for proper clearing on Windows
    if sys.platform == 'win32':
        os.system('cls')
    else:
        os.system('clear')
    # Fallback to Rich's clear (though it doesn't work as well on Windows)
    console.clear()


def print_header(text: str, color: str = "cyan"):
    """Print a styled header."""
    console.print(f"\n[bold {color}]{'=' * 50}[/bold {color}]")
    console.print(f"[bold {color}]{text.center(50)}[/bold {color}]")
    console.print(f"[bold {color}]{'=' * 50}[/bold {color}]\n")


def print_standings(players: List[Player], player_choices: Dict[Player, Location] = None):
    """Print current standings with optional location choices."""
    alive_players = [p for p in players if p.alive]
    alive_players.sort(key=lambda p: p.points, reverse=True)

    table = Table(title="Current Standings", show_header=True)
    table.add_column("Rank", style="cyan", width=6)
    table.add_column("Player", style="green")
    table.add_column("Points", justify="right", style="yellow")
    table.add_column("Passives", style="magenta")

    # Add choice column if choices are being tracked
    if player_choices is not None:
        table.add_column("Location Choice", style="cyan")

    for i, player in enumerate(alive_players, 1):
        passives = player.get_passives()
        passives_str = ", ".join(p.emoji for p in passives) or "-"

        row = [
            f"{i}.",
            f"[{player.color}]{player.name}[/{player.color}]",
            str(player.points),
            passives_str
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


def print_locations(location_manager: LocationManager, previous_ai_location: Location = None, event_manager=None, scout_rolls: dict = None, point_hints: dict = None):
    """Print available loot locations with active events, optional Scout preview, and point hints."""
    console.print("[bold]AVAILABLE LOOT THIS ROUND:[/bold]")

    if previous_ai_location:
        console.print(f"[dim]Last round AI searched: {previous_ai_location.emoji} {previous_ai_location.name}[/dim]")

    console.print()

    # Clean single-column list
    locations = location_manager.get_all()
    for i, loc in enumerate(locations, 1):
        # Base location info
        if scout_rolls and loc.name in scout_rolls:
            # Show Scout preview roll instead of range
            scout_roll = scout_rolls[loc.name]
            console.print(f"  [{i}] {loc.emoji} {loc.name:<22} [bold yellow]📡 {scout_roll:>2} pts[/bold yellow] [dim](Scout preview!)[/dim]")
        elif point_hints and loc.name in point_hints:
            # Show Inside Knowledge hint
            hint = point_hints[loc.name]
            hint_color = "green" if hint == "Low" else "yellow" if hint == "Med" else "red"
            console.print(f"  [{i}] {loc.emoji} {loc.name:<22} [yellow]{loc.get_range_str():>6} pts[/yellow] [{hint_color}]📊 {hint}[/{hint_color}]")
        else:
            console.print(f"  [{i}] {loc.emoji} {loc.name:<22} [yellow]{loc.get_range_str():>6} pts[/yellow]")

        # Show active event for this location
        if event_manager:
            event = event_manager.get_location_event(loc)
            if event:
                rounds_text = f"{event.rounds_remaining} round{'s' if event.rounds_remaining > 1 else ''}"
                console.print(
                    f"      {event.emoji} [cyan]{event.name}:[/cyan] [dim]{event.description} ({rounds_text} left)[/dim]"
                )

    console.print()


def print_passive_shop(player: Player):
    """Print passive abilities shop in a bordered panel."""
    PassiveShop._load_passives()

    # Build shop content
    lines = []
    for i, passive_type in enumerate(PassiveType, 1):
        passive = PassiveShop.PASSIVES.get(passive_type)
        if not passive:
            continue

        owned = player.has_passive(passive_type)

        if owned:
            lines.append(f"[bold cyan][{i}][/bold cyan] {passive.emoji} [dim strikethrough]{passive.name}[/dim strikethrough] [green]OWNED[/green]")
        else:
            lines.append(f"[bold cyan][{i}][/bold cyan] {passive.emoji} [yellow]{passive.name}[/yellow] - [green]{passive.cost} pts[/green]")
            lines.append(f"    [dim]{passive.description}[/dim]")

        if i < len(PassiveType):
            lines.append("")

    lines.append("")
    lines.append("[dim]Press Enter to skip purchase[/dim]")

    panel = Panel(
        "\n".join(lines),
        title="✨ PASSIVE ABILITIES",
        border_style="cyan",
        padding=(1, 2)
    )

    console.print(panel)
    console.print()


def get_player_input(prompt: str, valid_range: range = None, color: str = "green") -> str:
    """Get input from player with optional validation."""
    while True:
        response = console.input(f"[bold {color}]{prompt}[/bold {color}] ")
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


def show_intel_report(player: Player, threat_level: float, predictability: float, insights: List[str], ai_memory=None, detail_level: str = "simple"):
    """Show Intel Report for a player with varying detail levels.

    Args:
        detail_level: "simple" shows basic labels only, "full" shows detailed percentages and analysis
    """
    console.print()
    panel_content = []

    threat_label = "HIGH" if threat_level > 0.7 else "MODERATE" if threat_level > 0.4 else "LOW"
    pred_label = "HIGH" if predictability > 0.6 else "MODERATE" if predictability > 0.3 else "LOW"

    if detail_level == "simple":
        # SIMPLIFIED VIEW (no AI Whisperer)
        panel_content.append(f"⚠️  AI THREAT LEVEL: [bold]{threat_label}[/bold]")
        panel_content.append("")
        panel_content.append(f"Predictability: [bold]{pred_label}[/bold]")
        panel_content.append("")
        panel_content.append("[dim]Purchase 'AI Whisperer' passive for detailed analysis[/dim]")
    else:
        # FULL VIEW (AI Whisperer active)
        bar_length = 10
        filled = int(threat_level * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

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

        # Add AI Memory section if available
        if ai_memory:
            panel_content.append("")
            panel_content.append("[bold cyan]🤖 AI MEMORY OF YOU:[/bold cyan]")
            panel_content.append(f"  • Favorite Location: [yellow]{ai_memory['favorite_location']}[/yellow]")
            panel_content.append(f"  • Risk Profile: [yellow]{ai_memory['risk_profile'].title()}[/yellow]")
            panel_content.append(f"  • AI's Catch Rate vs You: [yellow]{ai_memory['catch_rate']:.0%}[/yellow]")

            if ai_memory['has_personal_model']:
                panel_content.append(f"  • [red]⚠️  AI has built a PERSONAL MODEL of you![/red]")
                panel_content.append(f"    [dim](Based on {ai_memory['total_games']} games)[/dim]")
            elif ai_memory['total_games'] >= 5:
                panel_content.append(f"  • [yellow]AI is training a personal model...[/yellow]")
            else:
                panel_content.append(f"  • [dim]AI needs {5 - ai_memory['total_games']} more games to build a personal model[/dim]")

            # Add hiding stats if player has been caught
            hiding_stats = ai_memory.get('hiding_stats', {})
            if hiding_stats.get('total_caught', 0) > 0:
                panel_content.append("")
                panel_content.append("[bold yellow]🫣 ESCAPE PATTERNS:[/bold yellow]")
                panel_content.append(f"  • Times Caught: [yellow]{hiding_stats['total_caught']}[/yellow]")
                total_attempts = hiding_stats['hide_attempts'] + hiding_stats['run_attempts']
                if total_attempts > 0:
                    panel_content.append(f"  • Escape Attempts: [yellow]{total_attempts}[/yellow]")
                    panel_content.append(f"    - Hide: {hiding_stats['hide_attempts']} ({hiding_stats['hide_success_rate']:.0%} success)")
                    panel_content.append(f"    - Run: {hiding_stats['run_attempts']} ({hiding_stats['run_success_rate']:.0%} success)")
                    panel_content.append(f"  • Strategy: [yellow]{hiding_stats['risk_profile_when_caught'].replace('_', ' ').title()}[/yellow]")

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

    console.print(f"[bold {player.color}]{player.name}[/bold {player.color}] ({player.points} pts{f', {points_to_win} pts to win' if points_to_win <= 20 else ''}):")
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
        console.print(f"[yellow]💀 [{player.color}]{player.name}[/{player.color}] was caught![/yellow]")
        console.print(f"[green]   Shield activated! [{player.color}]{player.name}[/{player.color}] survives but gains 0 points.[/green]")
        console.print(f"[dim]   [{player.color}]{player.name}[/{player.color}]'s Shield is consumed.[/dim]")
    else:
        console.print(f"[bold red]💀 [{player.color}]{player.name}[/{player.color}] was caught! ELIMINATED[/bold red]")
        console.print(f"[dim]   Final score: {player.points} pts[/dim]")
    console.print()


def print_player_looted(player: Player, location: Location, points_earned: int):
    """Print that a player successfully looted."""
    console.print(f"[green]✅ [{player.color}]{player.name}[/{player.color}] looted {location.name}: +{points_earned} pts ({player.points} total)[/green]")


def print_game_over(winner: Player):
    """Print game over message."""
    play_victory_animation()
    console.print()
    console.print("[bold green]" + "=" * 50 + "[/bold green]")
    console.print(f"[bold green]🎉 [{winner.color}]{winner.name}[/{winner.color}] WINS with {winner.points} points! 🎉[/bold green]")
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
    console.print(f"[bold cyan]📊 [{player.color}]{player.name.upper()}[/{player.color}]'S POST-GAME REPORT[/bold cyan]")
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


def print_profile_selection_menu(profiles: List):
    """Print profile selection menu with stats."""
    from game.profile_manager import ProfileSummary
    from datetime import datetime, timezone

    clear()
    print_header("SELECT PROFILE")

    if not profiles:
        console.print("[yellow]No profiles found. Create your first profile![/yellow]\n")
        return

    table = Table(show_header=True, title="Available Profiles")
    table.add_column("#", style="cyan", width=4)
    table.add_column("Name", style="green", width=20)
    table.add_column("Record", style="yellow", justify="center", width=12)
    table.add_column("Win %", style="magenta", justify="right", width=8)
    table.add_column("Last Played", style="dim", width=20)

    for i, profile in enumerate(profiles, 1):
        # Format last played date
        try:
            last_played_dt = datetime.fromisoformat(profile.last_played.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - last_played_dt

            if delta.days == 0:
                last_played_str = "Today"
            elif delta.days == 1:
                last_played_str = "Yesterday"
            elif delta.days < 7:
                last_played_str = f"{delta.days} days ago"
            else:
                last_played_str = last_played_dt.strftime("%Y-%m-%d")
        except:
            last_played_str = "Unknown"

        record = f"{profile.wins}W-{profile.losses}L"
        win_pct = f"{profile.win_rate * 100:.1f}%" if profile.total_games > 0 else "N/A"

        table.add_row(
            str(i),
            profile.name,
            record,
            win_pct,
            last_played_str
        )

    console.print(table)
    console.print()
    console.print("[bold cyan]Options:[/bold cyan]")
    console.print("  [N] Create New Profile")
    console.print("  [D] Delete Profile")
    console.print("  [Q] Back to Main Menu")
    console.print()


def print_profile_stats_summary(profile):
    """Print detailed profile statistics."""
    from game.profile_manager import PlayerProfile

    clear()
    print_header(f"{profile.name}'S PROFILE")

    # Stats table
    stats_table = Table(title="Statistics", show_header=False, box=None)
    stats_table.add_column("Stat", style="cyan")
    stats_table.add_column("Value", style="yellow", justify="right")

    stats_table.add_row("Total Games", str(profile.stats.total_games))
    stats_table.add_row("Wins", str(profile.stats.wins))
    stats_table.add_row("Losses", str(profile.stats.losses))
    stats_table.add_row("Win Rate", f"{profile.stats.win_rate * 100:.1f}%")
    stats_table.add_row("Highest Score", str(profile.stats.highest_score))
    stats_table.add_row("Times Caught", str(profile.stats.times_caught))

    console.print(stats_table)
    console.print()

    # Behavioral stats
    if profile.stats.total_games > 0:
        console.print("[bold cyan]Behavioral Profile:[/bold cyan]")
        console.print(f"  Favorite Location: [yellow]{profile.behavioral_stats.favorite_location}[/yellow]")
        console.print(f"  Play Style: [yellow]{profile.behavioral_stats.risk_profile}[/yellow]")
        console.print(f"  Predictability: [yellow]{profile.behavioral_stats.predictability_score * 100:.0f}%[/yellow]")
        console.print()

    # AI Memory
    if profile.ai_memory.has_personal_model:
        console.print("[bold magenta]🤖 AI has a personal model trained on YOUR gameplay![/bold magenta]")
        console.print(f"  Model trained: {profile.ai_memory.model_trained_date}")
        console.print(f"  AI's catch rate vs you: {profile.ai_memory.catch_rate * 100:.1f}%")
        console.print()

    # Recent matches
    if profile.match_history:
        console.print("[bold cyan]Recent Matches:[/bold cyan]")
        for match in profile.match_history[-5:]:
            outcome_color = "green" if match.outcome == "win" else "red"
            outcome_symbol = "✓" if match.outcome == "win" else "✗"
            console.print(
                f"  [{outcome_color}]{outcome_symbol}[/{outcome_color}] "
                f"Score: {match.final_score} | Rounds: {match.rounds_played} | "
                f"{'Caught' if match.caught else 'Safe'}"
            )
        console.print()

    console.print("[dim]Press Enter to continue...[/dim]")
    console.input()


def get_profile_selection(max_number: int) -> str:
    """Get user input for profile selection."""
    while True:
        choice = console.input("[bold green]Enter your choice:[/bold green] ").strip().upper()

        if choice in ['N', 'D', 'Q']:
            return choice

        try:
            num = int(choice)
            if 1 <= num <= max_number:
                return choice
        except ValueError:
            pass

        console.print("[red]Invalid choice. Please try again.[/red]")


def print_current_profile(profile):
    """Print current profile status in main menu."""
    from game.profile_manager import ProfileManager

    if profile:
        pm = ProfileManager()
        play_style = pm.get_play_style(profile)

        console.print(f"[dim]Profile: {profile.name} | "
                     f"{profile.stats.wins}W-{profile.stats.losses}L | "
                     f"Style: {play_style}[/dim]")

        if profile.ai_memory.has_personal_model:
            console.print("[dim magenta]🤖 AI has learned your patterns[/dim magenta]")
    else:
        console.print("[dim yellow]No profile selected - you'll play as a guest[/dim yellow]")


# ====== HIDING/RUNNING UI FUNCTIONS ======

def print_caught_message(player, location):
    """Display dramatic caught message."""
    console.print()
    console.print("[bold red]" + "=" * 60 + "[/bold red]")
    console.print(f"[bold red]🚨 [{player.color}]{player.name}[/{player.color}] WAS CAUGHT at {location.emoji} {location.name}! 🚨[/bold red]")
    console.print("[bold red]" + "=" * 60 + "[/bold red]")
    console.print()
    console.print("[yellow]But all is not lost...[/yellow]")
    console.print()


def select_escape_option(escape_options: list, player, location_points: int) -> dict:
    """
    Present all escape options and let player choose.
    This is the prediction-based escape system where player tries to outsmart the AI.

    Args:
        escape_options: List of escape option dicts with id, name, description, emoji, type
        player: Player who was caught
        location_points: Points rolled at this location

    Returns:
        Selected escape option dict
    """
    console.print(f"[bold cyan]Choose your escape, [{player.color}]{player.name}[/{player.color}]![/bold cyan]\n")
    console.print("[yellow]The AI is trying to predict your choice...[/yellow]")
    console.print("[dim]Pick DIFFERENTLY from the AI to survive![/dim]\n")

    # Separate hiding spots and escape routes
    hiding_spots = [opt for opt in escape_options if opt.get('type', 'hide') == 'hide']
    escape_routes = [opt for opt in escape_options if opt.get('type') == 'run']

    # Calculate run points
    retention_points = int(location_points * 0.8)

    # Build ordered list for selection
    all_options = []

    # Show hiding spots
    console.print("[bold green]HIDING SPOTS[/bold green] [dim](Survive with 0 points)[/dim]")
    for i, spot in enumerate(hiding_spots, 1):
        console.print(f"  [{i}] {spot['emoji']} [bold]{spot['name']}[/bold]")
        console.print(f"      [dim]{spot['description']}[/dim]")
        all_options.append(spot)

    console.print()

    # Show escape routes
    console.print(f"[bold yellow]ESCAPE ROUTES[/bold yellow] [dim](Survive with {retention_points} points)[/dim]")
    offset = len(hiding_spots)
    for i, route in enumerate(escape_routes, offset + 1):
        console.print(f"  [{i}] {route['emoji']} [bold]{route['name']}[/bold]")
        console.print(f"      [dim]{route['description']}[/dim]")
        all_options.append(route)

    console.print()

    # Get player choice
    while True:
        choice = console.input(f"[bold]Select option (1-{len(all_options)}):[/bold] ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(all_options):
                return all_options[idx]
        except ValueError:
            pass
        console.print(f"[red]Invalid choice. Enter 1-{len(all_options)}.[/red]")


def print_escape_result(player, result: dict, escape_options: list = None):
    """
    Print escape attempt result with dramatic AI prediction reveal.

    Args:
        player: Player who attempted escape
        result: Dict with escaped, player_choice_id, ai_prediction_id, etc.
        escape_options: Optional list of escape options to get names
    """
    import time

    console.print()
    console.print("[bold cyan]" + "=" * 50 + "[/bold cyan]")
    console.print("[bold cyan]        THE AI'S PREDICTION...[/bold cyan]")
    console.print("[bold cyan]" + "=" * 50 + "[/bold cyan]")
    console.print()

    # Find option names
    player_choice_name = result.get('player_choice_name', result.get('player_choice_id', '???'))
    ai_prediction_name = result.get('ai_prediction_id', '???')

    # Try to get AI prediction name from escape options
    if escape_options:
        for opt in escape_options:
            if opt['id'] == result.get('ai_prediction_id'):
                ai_prediction_name = opt['name']
                break

    # Dramatic pause
    time.sleep(0.5)

    # Show AI prediction
    console.print(f"[yellow]AI predicted: [bold]{ai_prediction_name}[/bold][/yellow]")
    time.sleep(0.3)

    # Show player choice
    console.print(f"[cyan]You chose: [bold]{player_choice_name}[/bold][/cyan]")
    console.print()
    time.sleep(0.3)

    if result['escaped']:
        # SUCCESS - Player outsmarted the AI
        play_escape_animation()
        console.print("[bold green]" + "=" * 50 + "[/bold green]")
        console.print(f"[bold green]    OUTSMARTED! [{player.color}]{player.name}[/{player.color}] escapes![/bold green]")
        console.print("[bold green]" + "=" * 50 + "[/bold green]")
        console.print()

        if result.get('choice_type') == 'run':
            console.print(f"[green]You kept {result['points_awarded']} points (80% of {result.get('location_points', 0)})[/green]")
        else:
            console.print(f"[green]You survived by hiding! (0 points earned)[/green]")

        console.print()
        console.print(f"[dim]Current score: {player.points} pts[/dim]")
    else:
        # FAILURE - AI predicted correctly
        play_elimination_animation()

        console.print("[bold red]" + "=" * 50 + "[/bold red]")
        console.print(f"[bold red]    PREDICTED! The AI knew your move![/bold red]")
        console.print("[bold red]" + "=" * 50 + "[/bold red]")
        console.print()

        console.print(f"[red]{player.name} is [bold]ELIMINATED[/bold][/red]")
        console.print(f"[dim]Final score: {player.points} pts[/dim]")

    console.print()
    console.input("[dim]Press Enter to continue...[/dim]")


def print_escape_success(player, result: dict, search_location=None):
    """Print successful escape message (legacy - use print_escape_result instead)."""
    console.print()

    if result.get('choice') == 'hide' or result.get('choice_type') == 'hide':
        spot_name = result.get('hide_spot_name') or result.get('player_choice_name', 'hiding spot')
        console.print(f"[bold green]✅ [{player.color}]{player.name}[/{player.color}] successfully hid in {spot_name}![/bold green]")
        if 'success_chance' in result:
            console.print(f"[green]The AI didn't find you! (Success chance was {result['success_chance']:.0%})[/green]")
        console.print(f"[yellow]Points: {player.points} (no points earned from hiding)[/yellow]")
    else:  # run
        console.print(f"[bold green]✅ [{player.color}]{player.name}[/{player.color}] successfully escaped![/bold green]")
        if 'success_chance' in result:
            console.print(f"[green]You got away! (Escape chance was {result['success_chance']:.0%})[/green]")
        points_kept = result.get('points_retained') or result.get('points_awarded', 0)
        console.print(f"[yellow]Points retained: {points_kept} (lost 20%)[/yellow]")

    # Reveal where AI searched
    if search_location:
        console.print()
        console.print(f"[cyan]🔍 The AI searched {search_location.emoji} {search_location.name} looking for you![/cyan]")

    console.print()
    console.input("[dim]Press Enter to continue...[/dim]")


def print_escape_failure(player, result: dict, search_location=None):
    """Print failed escape message with elimination animation (legacy - use print_escape_result instead)."""
    # Play the dramatic elimination animation
    play_elimination_animation()

    console.print()

    if result.get('choice') == 'hide' or result.get('choice_type') == 'hide':
        spot_name = result.get('hide_spot_name') or result.get('player_choice_name', 'hiding spot')
        console.print(f"[bold red]❌ The AI found [{player.color}]{player.name}[/{player.color}] hiding in {spot_name}![/bold red]")
        if 'success_chance' in result:
            console.print(f"[red]Your hiding spot was discovered! (Success chance was {result['success_chance']:.0%})[/red]")
    else:  # run
        console.print(f"[bold red]❌ [{player.color}]{player.name}[/{player.color}] was caught while trying to escape![/bold red]")
        if 'success_chance' in result:
            console.print(f"[red]The AI tracked you down! (Escape chance was {result['success_chance']:.0%})[/red]")

    # Reveal where AI searched
    if search_location:
        console.print()
        console.print(f"[cyan]🔍 The AI was searching {search_location.emoji} {search_location.name}![/cyan]")

    console.print(f"[dim]Final score: {player.points} pts[/dim]")
    console.print("[bold red]ELIMINATED[/bold red]")
    console.print()
    console.input("[dim]Press Enter to continue...[/dim]")
