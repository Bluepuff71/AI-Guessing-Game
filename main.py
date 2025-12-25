"""
LOOT RUN - A strategic looting game with adaptive AI

Players compete to reach 100 points by looting locations,
while an AI learns their patterns and hunts them down.
"""
import sys
import io

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import shutil
from game.engine import GameEngine
from game import ui
from game.profile_manager import ProfileManager, PlayerProfile
from game.animations import play_elimination_animation, play_victory_animation, play_escape_animation
from typing import List, Optional

# Global state for selected profiles
selected_profiles: List[Optional[PlayerProfile]] = []


def show_main_menu():
    """Show main menu and get user choice."""
    ui.clear()
    ui.console.print("\n[bold cyan]╔═══════════════════════════════════════╗[/bold cyan]")
    ui.console.print("[bold cyan]║          LOOT RUN - v1.0              ║[/bold cyan]")
    ui.console.print("[bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n")

    # Check if AI data exists
    data_dir = "data"
    has_data = os.path.exists(os.path.join(data_dir, "game_history.json"))
    has_model = os.path.exists(os.path.join(data_dir, "model.pkl"))

    if has_data or has_model:
        try:
            import json
            with open(os.path.join(data_dir, "game_history.json"), 'r') as f:
                history = json.load(f)
                num_games = len(history.get('games', []))
                ui.console.print(f"[dim]AI has learned from {num_games} previous games[/dim]")
        except:
            pass

    # Show selected profiles if any
    if selected_profiles:
        ui.console.print("\n[bold cyan]SELECTED PROFILES:[/bold cyan]")
        for i, profile in enumerate(selected_profiles, 1):
            if profile:
                pm = ProfileManager()
                play_style = pm.get_play_style(profile)
                ui.console.print(
                    f"[dim]Player {i}: {profile.name} | "
                    f"{profile.stats.wins}W-{profile.stats.losses}L | "
                    f"Style: {play_style}[/dim]"
                )
        ui.console.print()

    # Use arrow-key selection for main menu
    return ui.select_main_menu()


def reset_ai_data():
    """Reset AI training data."""
    global selected_profiles
    import stat

    def handle_remove_readonly(func, path, excinfo):
        """Error handler for shutil.rmtree to handle read-only and locked files on Windows."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    data_dir = "data"

    if not os.path.exists(data_dir):
        ui.console.print("[yellow]No AI data found to reset.[/yellow]")
        ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    ui.console.print("\n[bold red]⚠️  WARNING: This will delete all AI training data![/bold red]")
    ui.console.print("[bold red]This includes all player profiles and AI models![/bold red]")
    ui.console.print("The AI will start learning from scratch.\n")

    confirm = ui.console.input("[yellow]Are you sure? (yes/no):[/yellow] ").strip().lower()

    if confirm == 'yes':
        try:
            # Clear selected profiles first (they reference data being deleted)
            selected_profiles = []

            # Reset the ProfileManager singleton so it reinitializes after reset
            ProfileManager._instance = None

            # Delete the data directory with error handler for Windows permission issues
            shutil.rmtree(data_dir, onerror=handle_remove_readonly)
            ui.console.print("[green]✓ AI training data has been reset![/green]")
            ui.console.print("[dim]All profiles and AI models have been deleted.[/dim]")
        except Exception as e:
            ui.console.print(f"[red]Error resetting data: {e}[/red]")
            ui.console.print("[yellow]Tip: Close the game and try again, or manually delete the 'data' folder.[/yellow]")
    else:
        ui.console.print("[dim]Reset cancelled.[/dim]")

    ui.console.input("\n[dim]Press Enter to continue...[/dim]")


def manage_profiles():
    """Profile management menu."""
    global selected_profiles

    pm = ProfileManager()

    while True:
        profiles = pm.list_all_profiles()
        ui.clear()
        ui.print_header("MANAGE PROFILES")

        if not profiles:
            # No profiles exist, prompt to create one
            ui.console.print("[yellow]No profiles found. Create your first profile![/yellow]\n")
            choice = 'N'
        else:
            # Show profile table for context
            from rich.table import Table
            table = Table(title="Your Profiles")
            table.add_column("Name", style="green")
            table.add_column("Record", style="yellow")
            for profile in profiles:
                table.add_row(profile.name, f"{profile.wins}W-{profile.losses}L")
            ui.console.print(table)
            ui.console.print()

            # Use arrow-key selection
            choice = ui.get_profile_selection(profiles)

        if choice == 'Q':
            return
        elif choice == 'N':
            # Create new profile
            ui.console.print()
            name = ui.console.input("[bold green]Enter profile name:[/bold green] ").strip()
            if name:
                profile = pm.create_profile(name)
                ui.console.print(f"[green]✓ Profile '{name}' created![/green]")
                ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        elif choice == 'D':
            # Delete profile - use arrow selection to pick which one
            if profiles:
                ui.console.print()
                delete_choices = [{'text': p.name, 'value': i} for i, p in enumerate(profiles)]
                delete_choices.append({'text': "Cancel", 'value': -1})
                idx = ui.select_option(delete_choices, "Select profile to delete:")

                if idx >= 0:
                    profile = profiles[idx]
                    confirm = ui.console.input(f"[red]Delete '{profile.name}'? (yes/no):[/red] ").strip().lower()
                    if confirm == 'yes':
                        pm.delete_profile(profile.profile_id)
                        ui.console.print("[green]✓ Profile deleted![/green]")
                    else:
                        ui.console.print("[dim]Deletion cancelled.[/dim]")
                ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        else:
            # View profile details
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(profiles):
                    profile = pm.load_profile(profiles[idx].profile_id)
                    if profile:
                        ui.print_profile_stats_summary(profile)
            except ValueError:
                pass


def select_profiles_for_game(num_players: int) -> List[Optional[PlayerProfile]]:
    """Select profiles for each player in the game."""
    global selected_profiles
    selected_profiles = []

    pm = ProfileManager()

    for i in range(num_players):
        ui.clear()
        ui.console.print(f"\n[bold cyan]PLAYER {i+1} - SELECT PROFILE[/bold cyan]\n")

        profiles = pm.list_all_profiles()

        # Use arrow-key selection
        choice = ui.select_profile_for_player(profiles, i + 1)

        if choice == 'N':
            # Create new profile
            name = ui.console.input("\n[bold green]Enter name for new profile:[/bold green] ").strip()
            if name:
                profile = pm.create_profile(name)
                selected_profiles.append(profile)
                ui.console.print(f"[green]✓ Profile '{name}' created![/green]")
                ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        elif choice == 'G':
            # Play as guest
            name = ui.console.input("\n[bold green]Enter name for guest player:[/bold green] ").strip()
            if not name:
                name = f"Player {i+1}"
            selected_profiles.append(None)  # None = guest
        else:
            # Select existing profile
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(profiles):
                    profile = pm.load_profile(profiles[idx].profile_id)
                    if profile:
                        selected_profiles.append(profile)
                        ui.console.print(f"[green]✓ Selected {profile.name}[/green]")
                        ui.console.input("\n[dim]Press Enter to continue...[/dim]")
            except ValueError:
                pass

    return selected_profiles


def start_game():
    """Start a new game."""
    global selected_profiles

    ui.clear()
    ui.console.print("\n[bold cyan]Starting New Game[/bold cyan]\n")

    # Get number of players using arrow-key selection
    num_players = ui.select_player_count()

    # Select profiles for each player
    selected_profiles = select_profiles_for_game(num_players)

    # Create and run game with profiles
    game = GameEngine(num_players, selected_profiles)
    game.setup_game()
    game.play_game()


def test_animations():
    """Test animation sequences."""
    while True:
        ui.clear()
        ui.console.print("\n[bold cyan]ANIMATION TEST[/bold cyan]\n")

        # Use arrow-key selection
        choice = ui.select_animation_test()

        if choice == 'Q':
            return
        elif choice == '1':
            ui.console.print("\nPlaying elimination animation...")
            play_elimination_animation()
        elif choice == '2':
            ui.console.print("\nPlaying victory animation...")
            play_victory_animation()
        elif choice == '3':
            ui.console.print("\nPlaying escape animation...")
            play_escape_animation()
        elif choice == '4':
            ui.console.print("\nPlaying all animations...")
            play_elimination_animation()
            play_victory_animation()
            play_escape_animation()


def main():
    """Main entry point for LOOT RUN."""
    while True:
        choice = show_main_menu()

        if choice == '1':
            start_game()
            # After game ends, return to menu
        elif choice == 'P':
            manage_profiles()
        elif choice == 'A':
            test_animations()
        elif choice == '2':
            reset_ai_data()
        elif choice == '3':
            ui.console.print("\n[bold]Thanks for playing LOOT RUN![/bold]\n")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ui.console.print("\n\n[yellow]Game interrupted. Thanks for playing![/yellow]\n")
        sys.exit(0)
    except Exception as e:
        ui.console.print(f"\n[bold red]An error occurred: {e}[/bold red]\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
