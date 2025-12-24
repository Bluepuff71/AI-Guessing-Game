"""Main game engine and loop."""
import json
import os
from typing import List, Dict, Optional
from game.player import Player
from game.locations import LocationManager, Location
from game.items import ItemShop, ItemType, Item
from game import ui
from game.config_loader import config
from ai.predictor import AIPredictor
from ai.features import generate_insights


class GameEngine:
    """Main game engine that runs LOOT RUN."""

    def __init__(self, num_players: int):
        self.num_players = num_players
        self.players: List[Player] = []
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.round_num = 0
        self.game_over = False
        self.winner: Optional[Player] = None
        self.win_threshold = config.get('game', 'win_threshold', default=100)

    def setup_game(self):
        """Initialize the game and get player names."""
        ui.clear()
        ui.print_header("LOOT RUN")

        ui.console.print("[bold]Welcome to LOOT RUN![/bold]")
        ui.console.print(f"Compete against other players to reach {self.win_threshold} points first.")
        ui.console.print("But watch out - the AI is learning your patterns...")
        ui.console.print()

        # Show AI status
        if self.ai.use_ml:
            info = self.ai.ml_trainer.get_model_info()
            ui.console.print(f"[cyan]🤖 AI Status: ML Model Active (trained on {info['num_games']} games, {info['training_samples']} samples)[/cyan]")
        else:
            ui.console.print("[yellow]🤖 AI Status: Baseline AI (No ML model yet - will train after 2+ games)[/yellow]")
        ui.console.print()

        # Get player names
        for i in range(self.num_players):
            name = ui.console.input(f"[bold green]Enter name for Player {i+1}:[/bold green] ").strip()
            if not name:
                name = f"Player {i+1}"
            self.players.append(Player(i, name))

        ui.console.print()
        ui.console.input("[dim]Press Enter to start the game...[/dim]")

    def play_game(self):
        """Main game loop."""
        while not self.game_over:
            self.round_num += 1
            self.play_round()

        # Game over - show final results
        self.show_final_results()

    def play_round(self):
        """Play a single round."""
        # Track player choices for this round
        player_choices: Dict[Player, Location] = {}
        scanner_used_by = []

        # Each player's turn to shop and choose location
        alive_players = [p for p in self.players if p.alive]

        for player in alive_players:
            # Clear console and show fresh context for this player
            ui.clear()
            ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")

            # Show current standings
            ui.print_standings(self.players)

            # Show locations (same for all players this round)
            ui.print_locations(self.location_manager)

            # Shop phase
            self.shop_phase(player)

            # If player has Scout, let them preview rolls
            if any(item.type == ItemType.SCOUT and not item.consumed for item in player.items):
                use_scout = ui.get_player_input("Use Scout to preview loot rolls? (y/n): ", None)
                if use_scout.lower() == 'y':
                    self.show_scout_preview(player)
                    player.use_item(ItemType.SCOUT)
                    ui.console.print()

            # Location choice
            location = self.choose_location_phase(player)
            player_choices[player] = location

            # If player used Scanner, show predictions
            if any(item.type == ItemType.SCANNER and not item.consumed for item in player.items):
                # Ask if they want to use it
                use_scanner = ui.get_player_input("Use Scanner? (y/n): ", None)
                if use_scanner.lower() == 'y':
                    scanner_used_by.append(player)
                    predictions = self.ai.get_scanner_predictions(self.players)
                    ui.show_scanner_results(predictions)
                    player.use_item(ItemType.SCANNER)

                    # Let them change their choice
                    change = ui.get_player_input("Change location choice? (y/n): ", None)
                    if change.lower() == 'y':
                        location = self.choose_location_phase(player)
                        player_choices[player] = location

            ui.console.print(f"[green]✓ {player.name} is ready![/green]")
            ui.console.input("[dim]Press Enter to continue...[/dim]")

        # All players have chosen - AI analysis
        ui.clear()
        ui.show_ai_thinking()

        # AI decides where to search
        search_location, predictions = self.ai.decide_search_location(self.players)

        # Reveal and resolution
        self.reveal_and_resolve_phase(player_choices, search_location, predictions)

        # Check for game over
        self.check_game_over()

    def shop_phase(self, player: Player):
        """Handle shopping for a player."""
        # Skip shop if player has no points
        if player.points == 0:
            ui.console.print(f"Your points: [yellow]{player.points}[/yellow]")
            ui.console.print("[dim]You have no points to spend. Skipping shop.[/dim]\n")
            return

        # Loop to allow multiple purchases
        while True:
            # Display current state
            ui.console.print(f"Your points: [yellow]{player.points}[/yellow]")

            active_items = player.get_active_items()
            if active_items:
                items_str = ", ".join(item.name for item in active_items)
                ui.console.print(f"Your items: [magenta]{items_str}[/magenta]")
            else:
                ui.console.print("Your items: [dim]None[/dim]")

            ui.console.print()
            ui.print_shop()

            # Ask if player wants to buy
            num_items = len(list(ItemType))
            choice = ui.get_player_input(f"Buy item? (1-{num_items} or Enter to skip): ", None)

            # Skip if empty or "skip"
            if choice.strip() == "" or choice.lower() == "skip":
                ui.console.print()
                return

            # Try to purchase item
            try:
                item_num = int(choice)
                if 1 <= item_num <= num_items:
                    item_types = list(ItemType)
                    item_type = item_types[item_num - 1]
                    item = ItemShop.get_item(item_type)

                    if player.buy_item(item):
                        ui.console.print(f"[green]✓ Bought {item.name} for {item.cost} pts[/green]")

                        # If Intel Report, show it immediately
                        if item_type == ItemType.INTEL_REPORT:
                            self.show_intel_report(player)
                            item.consumed = True  # Intel Report is consumed immediately

                        ui.console.print()
                        # Continue loop to allow more purchases
                    else:
                        ui.console.print(f"[red]Not enough points! Need {item.cost}, have {player.points}[/red]")
                        ui.console.print()
                        # Continue loop, don't exit
                else:
                    ui.console.print(f"[red]Invalid choice - please enter 1-{num_items}[/red]")
                    ui.console.print()
            except (ValueError, IndexError):
                ui.console.print("[red]Invalid choice[/red]")
                ui.console.print()

    def show_scout_preview(self, player: Player):
        """Show Scout preview of loot rolls for all locations."""
        ui.console.print("\n[bold cyan]📡 SCOUT PREVIEW - YOUR POTENTIAL ROLLS:[/bold cyan]\n")

        # Generate preview rolls for all locations
        locations = self.location_manager.get_all()
        for i, loc in enumerate(locations, 1):
            preview_roll = loc.roll_points()
            ui.console.print(f"  [{i}] {loc.emoji} {loc.name:<22} [yellow]{preview_roll:>2} pts[/yellow] [dim](range: {loc.get_range_str()})[/dim]")

        ui.console.print("\n[dim]Note: These are YOUR potential rolls. Other players will get different amounts.[/dim]")
        ui.console.input("\n[dim]Press Enter to continue...[/dim]")

    def show_intel_report(self, player: Player):
        """Show Intel Report to a player."""
        from ai.features import calculate_predictability
        from ai.predictor import AIPredictor

        predictability = calculate_predictability(player)
        threat_level = self.ai._calculate_win_threat(player)

        insights = []
        behavior = player.get_behavior_summary()

        if behavior['avg_location_value'] > 18:
            insights.append(f"You favor high-value locations ({behavior['avg_location_value']:.1f} avg points)")
        elif behavior['avg_location_value'] < 10:
            insights.append(f"You prefer low-value locations ({behavior['avg_location_value']:.1f} avg points)")

        if behavior['choice_variety'] < 0.5:
            num_locations = len(self.location_manager)
            locations_visited = int(behavior['choice_variety'] * num_locations)
            insights.append(f"Limited variety (only {locations_visited} of {num_locations} locations visited)")

        if player.choice_history:
            from collections import Counter
            location_counts = Counter(player.choice_history)
            most_common = location_counts.most_common(1)[0]
            if most_common[1] >= 3:
                insights.append(f"Frequent choice: {most_common[0]} ({most_common[1]} times)")

        if not insights:
            insights.append("No strong patterns detected yet")

        ui.show_intel_report(player, threat_level, predictability, insights)
        ui.console.input("[dim]Press Enter to continue...[/dim]")

    def choose_location_phase(self, player: Player) -> Location:
        """Handle location choice for a player."""
        ui.console.print("[bold]Choose your looting location:[/bold]")
        num_locations = len(self.location_manager)
        choice = ui.get_player_input(f"Location (1-{num_locations}): ", range(1, num_locations + 1))

        location_index = int(choice) - 1
        location = self.location_manager.get_location(location_index)

        ui.console.print(f"[green]You chose: {location.emoji} {location.name} ({location.get_range_str()} pts)[/green]")

        return location

    def reveal_and_resolve_phase(self, player_choices: Dict[Player, Location],
                                 search_location: Location,
                                 predictions: Dict[Player, tuple]):
        """Reveal choices and resolve the round."""
        ui.clear()
        ui.print_reveal_header()

        # Show each player's choice and AI prediction
        for player in [p for p in self.players if p.alive]:
            chosen_location = player_choices[player]
            predicted_loc, confidence, reasoning = predictions[player]

            ui.print_player_choice(player, chosen_location, predicted_loc, confidence, reasoning)

        # Show AI's search decision
        ui.print_search_result(search_location)

        # Resolve catches and looting
        for player in [p for p in self.players if p.alive]:
            chosen_location = player_choices[player]

            if chosen_location.name == search_location.name:
                # Player is eliminated
                ui.print_player_caught(player, shield_saved=False)
                player.alive = False
                player.record_choice(chosen_location, self.round_num, caught=True, points_earned=0)

                # Show post-game report
                insights = generate_insights(player, len(self.location_manager))
                ui.print_post_game_report(player, insights)
            else:
                # Player successfully looted
                has_lucky_charm = player.has_item(ItemType.LUCKY_CHARM)

                # Ask if they want to use Lucky Charm
                use_lucky_charm = False
                if has_lucky_charm:
                    ui.console.print(f"\n[yellow]{player.name} has Lucky Charm![/yellow]")
                    use = ui.get_player_input("Use Lucky Charm to double points? (y/n): ", None)
                    if use.lower() == 'y':
                        use_lucky_charm = True
                        player.use_item(ItemType.LUCKY_CHARM)

                # Roll individual points for this player
                base_roll = chosen_location.roll_points()
                points_earned = base_roll
                if use_lucky_charm:
                    points_earned *= 2

                player.add_points(points_earned, has_lucky_charm=False)  # Already handled doubling above
                ui.print_player_looted(player, chosen_location, points_earned)

                # Record with base roll value for AI learning (not Lucky Charm doubled value)
                player.record_choice(chosen_location, self.round_num, caught=False,
                                   points_earned=points_earned, location_value=base_roll)

        ui.console.print()
        ui.print_standings(self.players)

        ui.console.input("\n[dim]Press Enter to continue to next round...[/dim]")

    def check_game_over(self):
        """Check if game is over and set winner."""
        alive_players = [p for p in self.players if p.alive]

        # Check for score victory
        for player in alive_players:
            if player.points >= self.win_threshold:
                self.game_over = True
                self.winner = player
                return

        # Check for elimination victory (AI wins)
        if len(alive_players) == 0:
            self.game_over = True
            self.winner = None  # AI wins
            return

        # Check for last player standing
        if len(alive_players) == 1:
            self.game_over = True
            self.winner = alive_players[0]
            return

    def show_final_results(self):
        """Show final game results."""
        ui.clear()

        if self.winner:
            ui.print_game_over(self.winner)
        else:
            ui.print_ai_victory()

        # Show post-game reports for all players who haven't seen it yet
        for player in self.players:
            if player.alive:  # Didn't get eliminated (won or AI won)
                insights = generate_insights(player, len(self.location_manager))
                ui.print_post_game_report(player, insights)

        # Save game data
        self.save_game_data()

        ui.console.print("\n[bold]Thanks for playing LOOT RUN![/bold]\n")
        ui.console.input("[dim]Press Enter to return to main menu...[/dim]")

    def save_game_data(self):
        """Save game data for ML training."""
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)

        game_data = {
            'num_players': self.num_players,
            'num_rounds': self.round_num,
            'winner': self.winner.name if self.winner else 'AI',
            'players': []
        }

        for player in self.players:
            player_data = {
                'name': player.name,
                'final_points': player.points,
                'alive': player.alive,
                'rounds_survived': len(player.choice_history),
                'round_history': player.round_history,
                'choice_history': player.choice_history,
            }
            game_data['players'].append(player_data)

        # Append to game history file
        history_file = os.path.join(data_dir, 'game_history.json')

        try:
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            else:
                history = {'games': []}

            history['games'].append(game_data)

            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)

            ui.console.print(f"[dim]Game data saved ({len(history['games'])} total games played)[/dim]")

            # Try to retrain ML model if enough games have been played
            self._try_retrain_model(len(history['games']))

        except Exception as e:
            ui.console.print(f"[dim red]Failed to save game data: {e}[/dim red]")

    def _try_retrain_model(self, num_games: int):
        """Try to retrain the ML model after game ends."""
        try:
            from ai.trainer import auto_retrain_if_needed
            auto_retrain_if_needed(min_new_games=5)
        except Exception as e:
            # Silent fail if ML not available
            pass
