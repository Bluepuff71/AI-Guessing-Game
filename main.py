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

    ui.console.print("[bold]MAIN MENU:[/bold]")
    ui.console.print("[1] Start New Game")
    ui.console.print("[P] Manage Profiles")
    ui.console.print("[2] Reset AI Training Data")
    ui.console.print("[3] Exit")
    ui.console.print()

    while True:
        choice = ui.console.input("[bold green]Select option:[/bold green] ").strip().upper()
        if choice in ['1', '2', '3', 'P']:
            return choice
        ui.console.print("[red]Please enter 1, P, 2, or 3[/red]")


def reset_ai_data():
    """Reset AI training data."""
    data_dir = "data"

    if not os.path.exists(data_dir):
        ui.console.print("[yellow]No AI data found to reset.[/yellow]")
        ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    ui.console.print("\n[bold red]⚠️  WARNING: This will delete all AI training data![/bold red]")
    ui.console.print("The AI will start learning from scratch.\n")

    confirm = ui.console.input("[yellow]Are you sure? (yes/no):[/yellow] ").strip().lower()

    if confirm == 'yes':
        try:
            # Delete the data directory
            shutil.rmtree(data_dir)
            ui.console.print("[green]✓ AI training data has been reset![/green]")
        except Exception as e:
            ui.console.print(f"[red]Error resetting data: {e}[/red]")
    else:
        ui.console.print("[dim]Reset cancelled.[/dim]")

    ui.console.input("\n[dim]Press Enter to continue...[/dim]")


def manage_profiles():
    """Profile management menu."""
    global selected_profiles

    pm = ProfileManager()

    while True:
        profiles = pm.list_all_profiles()
        ui.print_profile_selection_menu(profiles)

        if not profiles:
            # No profiles exist, prompt to create one
            choice = 'N'
        else:
            choice = ui.get_profile_selection(len(profiles))

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
            # Delete profile
            if profiles:
                ui.console.print()
                profile_num = ui.console.input("[bold yellow]Enter profile number to delete:[/bold yellow] ").strip()
                try:
                    idx = int(profile_num) - 1
                    if 0 <= idx < len(profiles):
                        profile = profiles[idx]
                        confirm = ui.console.input(f"[red]Delete '{profile.name}'? (yes/no):[/red] ").strip().lower()
                        if confirm == 'yes':
                            pm.delete_profile(profile.profile_id)
                            ui.console.print("[green]✓ Profile deleted![/green]")
                        else:
                            ui.console.print("[dim]Deletion cancelled.[/dim]")
                    else:
                        ui.console.print("[red]Invalid profile number.[/red]")
                except ValueError:
                    ui.console.print("[red]Invalid input.[/red]")
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

        if profiles:
            ui.console.print("[bold]Available Profiles:[/bold]")
            for j, profile in enumerate(profiles[:10], 1):  # Show max 10
                ui.console.print(
                    f"  [{j}] {profile.name} - {profile.wins}W-{profile.losses}L "
                    f"({profile.win_rate * 100:.0f}% wins)"
                )
            ui.console.print()

        ui.console.print("[N] Create New Profile")
        ui.console.print("[G] Play as Guest (no profile)")
        ui.console.print()

        while True:
            choice = ui.console.input("[bold green]Select:[/bold green] ").strip().upper()

            if choice == 'N':
                # Create new profile
                name = ui.console.input("\n[bold green]Enter name for new profile:[/bold green] ").strip()
                if name:
                    profile = pm.create_profile(name)
                    selected_profiles.append(profile)
                    ui.console.print(f"[green]✓ Profile '{name}' created![/green]")
                    ui.console.input("\n[dim]Press Enter to continue...[/dim]")
                    break
            elif choice == 'G':
                # Play as guest
                name = ui.console.input("\n[bold green]Enter name for guest player:[/bold green] ").strip()
                if not name:
                    name = f"Player {i+1}"
                selected_profiles.append(None)  # None = guest
                break
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
                            break
                except ValueError:
                    pass

                ui.console.print("[red]Invalid choice. Try again.[/red]")

    return selected_profiles


def start_game():
    """Start a new game."""
    global selected_profiles

    ui.clear()
    ui.console.print("\n[bold cyan]Starting New Game[/bold cyan]\n")

    # Get number of players
    while True:
        try:
            num_players = ui.console.input("[bold green]Enter number of players (2-6):[/bold green] ")
            num_players = int(num_players)

            if 2 <= num_players <= 6:
                break
            else:
                ui.console.print("[red]Please enter a number between 2 and 6[/red]")
        except ValueError:
            ui.console.print("[red]Please enter a valid number[/red]")

    # Select profiles for each player
    selected_profiles = select_profiles_for_game(num_players)

    # Create and run game with profiles
    game = GameEngine(num_players, selected_profiles)
    game.setup_game()
    game.play_game()


def check_and_migrate_legacy_games():
    """Check if legacy games need migration and offer to migrate."""
    pm = ProfileManager()

    # Check if profiles exist
    profiles = pm.list_all_profiles()

    # Check if game_history.json exists with games
    history_file = os.path.join("data", "game_history.json")
    if not os.path.exists(history_file):
        return  # No legacy games to migrate

    try:
        import json
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
            games = history_data.get('games', [])

        if not games:
            return  # No games to migrate

        # Check if any game is already migrated (has profile_id)
        already_migrated = any(
            'profile_id' in player
            for game in games
            for player in game.get('players', [])
        )

        if already_migrated:
            return  # Already migrated

        # Offer migration
        ui.clear()
        ui.console.print("\n[bold cyan]╔═══════════════════════════════════════╗[/bold cyan]")
        ui.console.print("[bold cyan]║      LEGACY GAME DATA DETECTED        ║[/bold cyan]")
        ui.console.print("[bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n")

        ui.console.print(f"[yellow]Found {len(games)} historical games in game_history.json[/yellow]")
        ui.console.print("\nWould you like to migrate this data to the new profile system?")
        ui.console.print("This will:")
        ui.console.print("  • Create profiles for all unique player names")
        ui.console.print("  • Link historical games to profiles")
        ui.console.print("  • Update player statistics")
        ui.console.print("  • Preserve all game data")
        ui.console.print()

        confirm = ui.console.input("[bold green]Migrate now? (yes/no):[/bold green] ").strip().lower()

        if confirm == 'yes':
            ui.console.print("\n[cyan]Migrating legacy games...[/cyan]")
            result = pm.migrate_legacy_games()

            if result.get('success'):
                ui.console.print(f"\n[green]✓ Migration completed successfully![/green]")
                ui.console.print(f"  • Profiles created: {result['profiles_created']}")
                ui.console.print(f"  • Total profiles: {result['total_profiles']}")
                ui.console.print(f"  • Games migrated: {result['games_migrated']}")
                ui.console.print(f"\n[dim]Players: {', '.join(result['player_names'])}[/dim]")
            else:
                ui.console.print(f"\n[red]✗ Migration failed: {result.get('error', 'Unknown error')}[/red]")

            ui.console.input("\n[dim]Press Enter to continue...[/dim]")
        else:
            ui.console.print("[dim]Migration cancelled. You can migrate later from the Profile menu.[/dim]")
            ui.console.input("\n[dim]Press Enter to continue...[/dim]")

    except Exception as e:
        ui.console.print(f"[red]Error checking for legacy games: {e}[/red]")


def main():
    """Main entry point for LOOT RUN."""
    # Check for legacy games on first run
    check_and_migrate_legacy_games()

    while True:
        choice = show_main_menu()

        if choice == '1':
            start_game()
            # After game ends, return to menu
        elif choice == 'P':
            manage_profiles()
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
