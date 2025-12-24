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

from game.engine import GameEngine
from game import ui


def main():
    """Main entry point for LOOT RUN."""
    ui.console.print("\n[bold cyan]╔═══════════════════════════════════════╗[/bold cyan]")
    ui.console.print("[bold cyan]║          LOOT RUN - v1.0              ║[/bold cyan]")
    ui.console.print("[bold cyan]╚═══════════════════════════════════════╝[/bold cyan]\n")

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
