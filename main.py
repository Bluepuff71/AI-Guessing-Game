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

    ui.console.print("\n[bold]MAIN MENU:[/bold]")
    ui.console.print("[1] Start New Game")
    ui.console.print("[2] Reset AI Training Data")
    ui.console.print("[3] Exit")
    ui.console.print()

    while True:
        choice = ui.console.input("[bold green]Select option (1-3):[/bold green] ").strip()
        if choice in ['1', '2', '3']:
            return choice
        ui.console.print("[red]Please enter 1, 2, or 3[/red]")


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


def start_game():
    """Start a new game."""
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

    # Create and run game
    game = GameEngine(num_players)
    game.setup_game()
    game.play_game()


def main():
    """Main entry point for LOOT RUN."""
    while True:
        choice = show_main_menu()

        if choice == '1':
            start_game()
            # After game ends, return to menu
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
