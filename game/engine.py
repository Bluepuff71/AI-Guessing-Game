"""Main game engine and loop."""
import json
import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional
from game.player import Player
from game.locations import LocationManager, Location
from game.items import ItemShop, ItemType, Item
from game import ui
from game.config_loader import config
from ai.predictor import AIPredictor
from ai.features import generate_insights
from game.profile_manager import ProfileManager, PlayerProfile


class GameEngine:
    """Main game engine that runs LOOT RUN."""

    def __init__(self, num_players: int, profiles: Optional[List[Optional[PlayerProfile]]] = None):
        self.num_players = num_players
        self.profiles = profiles or []  # List of PlayerProfile objects (or None for guests)
        self.players: List[Player] = []
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.round_num = 0
        self.game_over = False
        self.winner: Optional[Player] = None
        self.win_threshold = config.get('game', 'win_threshold', default=100)
        self.scout_rolls: Dict[int, Dict[str, int]] = {}  # player_id -> {location_name: roll_value}
        self.last_ai_search_location: Optional[Location] = None  # Track previous round's AI search

    def setup_game(self):
        """Initialize the game and create players from profiles."""
        ui.clear()
        ui.print_header("LOOT RUN")

        ui.console.print("[bold]Welcome to LOOT RUN![/bold]")
        ui.console.print(f"Compete against other players to reach {self.win_threshold} points first.")
        ui.console.print("But watch out - the AI is learning your patterns...")
        ui.console.print()

        # Show AI status with loading indicator
        ui.console.print()
        if self.ai.use_ml:
            with ui.create_progress_spinner("Loading AI model...") as progress:
                task = progress.add_task("", total=None)
                info = self.ai.ml_trainer.get_model_info()

            ui.console.print(f"[cyan]🤖 AI Status: ML Model Active (trained on {info['num_games']} games, {info['training_samples']} samples)[/cyan]")
        else:
            ui.console.print("[yellow]🤖 AI Status: Baseline AI (No ML model yet - will train after 2+ games)[/yellow]")
        ui.console.print()

        # Create players from profiles or prompt for names if no profiles
        if self.profiles and len(self.profiles) == self.num_players:
            # Use profiles
            for i in range(self.num_players):
                profile = self.profiles[i]
                if profile:
                    # Player with profile
                    self.players.append(Player(i, profile.name, profile.profile_id))
                    ui.console.print(f"[green]Player {i+1}: {profile.name}[/green] "
                                   f"[dim]({profile.stats.wins}W-{profile.stats.losses}L)[/dim]")
                else:
                    # Guest player - need to ask for name
                    name = ui.console.input(f"[bold green]Enter name for Guest Player {i+1}:[/bold green] ").strip()
                    if not name:
                        name = f"Player {i+1}"
                    self.players.append(Player(i, name, None))
        else:
            # No profiles provided - prompt for names (legacy mode)
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

        # Each player's turn to shop and choose location
        alive_players = [p for p in self.players if p.alive]

        for player in alive_players:
            # Clear console and show fresh context for this player
            ui.clear()
            ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")

            # Show current standings WITH choices made so far
            ui.print_standings(self.players, player_choices)

            # Show locations (same for all players this round)
            ui.print_locations(self.location_manager, self.last_ai_search_location)

            # Shop phase
            self.shop_phase(player)

            # Location choice
            location = self.choose_location_phase(player)
            player_choices[player] = location

            ui.console.print(f"[green]✓ {player.name} is ready![/green]")
            ui.console.input("[dim]Press Enter to continue...[/dim]")

        # All players have chosen - AI analysis
        ui.clear()
        ui.show_ai_thinking()

        # AI decides where to search
        search_location, predictions, ai_reasoning = self.ai.decide_search_location(self.players)

        # Reveal and resolution
        self.reveal_and_resolve_phase(player_choices, search_location, predictions, ai_reasoning)

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

                        # Auto-activate items based on type
                        if item_type == ItemType.INTEL_REPORT:
                            self.show_intel_report(player)
                            item.consumed = True  # Intel Report is consumed immediately
                        elif item_type == ItemType.SCOUT:
                            self.show_scout_preview(player)
                            player.use_item(ItemType.SCOUT)

                        # Clear screen before redrawing shop
                        ui.console.input("\n[dim]Press Enter to continue shopping...[/dim]")
                        ui.clear()
                        ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")

                        # Show locations so player has context
                        ui.print_locations(self.location_manager, self.last_ai_search_location)

                        ui.console.print()
                        # Continue loop to allow more purchases
                    else:
                        ui.console.print(f"[red]Not enough points! Need {item.cost}, have {player.points}[/red]")
                        ui.console.input("\n[dim]Press Enter to continue...[/dim]")
                        ui.clear()
                        ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")
                        ui.print_locations(self.location_manager, self.last_ai_search_location)
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

        # Clear and cache preview rolls for this player
        self.scout_rolls[player.id] = {}

        # Generate preview rolls for all locations
        locations = self.location_manager.get_all()
        for i, loc in enumerate(locations, 1):
            preview_roll = loc.roll_points()
            self.scout_rolls[player.id][loc.name] = preview_roll  # Cache it
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

        # Add AI Memory section if player has a profile
        ai_memory = None
        if hasattr(player, 'profile_id') and player.profile_id:
            from game.profile_manager import ProfileManager
            pm = ProfileManager()
            profile = pm.load_profile(player.profile_id)
            if profile:
                ai_memory = {
                    'favorite_location': profile.behavioral_stats.favorite_location,
                    'risk_profile': profile.behavioral_stats.risk_profile,
                    'catch_rate': profile.ai_memory.catch_rate,
                    'has_personal_model': profile.ai_memory.has_personal_model,
                    'total_games': profile.stats.total_games
                }

        ui.show_intel_report(player, threat_level, predictability, insights, ai_memory)
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
                                 predictions: Dict[Player, tuple],
                                 ai_reasoning: str = ""):
        """Reveal choices and resolve the round."""
        ui.clear()
        ui.print_reveal_header()

        # Show each player's choice and AI prediction
        for player in [p for p in self.players if p.alive]:
            chosen_location = player_choices[player]
            predicted_loc, confidence, reasoning = predictions[player]

            ui.print_player_choice(player, chosen_location, predicted_loc, confidence, reasoning)

        # Show AI's search decision
        ui.print_search_result(search_location, self.last_ai_search_location, ai_reasoning)

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

                # Auto-use Lucky Charm if player has it
                use_lucky_charm = False
                if has_lucky_charm:
                    use_lucky_charm = True
                    ui.console.print(f"\n[yellow]✨ {player.name}'s Lucky Charm activated automatically![/yellow]")
                    player.use_item(ItemType.LUCKY_CHARM)

                # Roll individual points for this player
                # Check if this player used Scout and has a cached roll
                if player.id in self.scout_rolls and chosen_location.name in self.scout_rolls[player.id]:
                    base_roll = self.scout_rolls[player.id][chosen_location.name]
                else:
                    base_roll = chosen_location.roll_points()

                points_earned = base_roll
                lucky_charm_multiplier = 1.0
                if use_lucky_charm:
                    # Get Lucky Charm item to access its multiplier
                    lucky_charm_item = player.get_item(ItemType.LUCKY_CHARM)
                    if lucky_charm_item:
                        lucky_charm_multiplier = lucky_charm_item.multiplier
                        points_earned = int(base_roll * lucky_charm_multiplier)

                player.add_points(points_earned, has_lucky_charm=False)  # Already handled multiplier above
                ui.print_player_looted(player, chosen_location, points_earned,
                                      base_roll=base_roll, used_lucky_charm=use_lucky_charm,
                                      lucky_charm_multiplier=lucky_charm_multiplier)

                # Record with base roll value for AI learning (not Lucky Charm doubled value)
                player.record_choice(chosen_location, self.round_num, caught=False,
                                   points_earned=points_earned, location_value=base_roll)

        ui.console.print()
        ui.print_standings(self.players)

        # Flush input buffer to prevent enter spam from skipping this prompt
        ui.flush_input()
        ui.console.input("\n[dim]Press Enter to continue to next round...[/dim]")

        # Clear scout rolls for next round
        self.scout_rolls.clear()

        # Store for next round display
        self.last_ai_search_location = search_location

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
            last_player = alive_players[0]
            ui.console.print(f"\n[yellow]🏆 {last_player.name} is the last player standing![/yellow]")
            ui.console.print(f"[yellow]Current score: {last_player.points}/{self.win_threshold} points[/yellow]\n")

            choice = ui.get_player_input("Continue playing to reach 100 points, or end game with victory? (continue/end): ", None)

            if choice.lower().startswith('e'):  # 'end' or 'e'
                self.game_over = True
                self.winner = last_player
                return
            else:
                # Continue solo play
                ui.console.print("[cyan]Playing solo against the AI...[/cyan]\n")
                ui.console.input("[dim]Press Enter to continue...[/dim]")
                # Don't set game_over, keep playing

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
        """Save game data for ML training and update player profiles."""
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)

        # Generate unique game ID
        game_id = str(uuid.uuid4())

        game_data = {
            'game_id': game_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'num_players': self.num_players,
            'num_rounds': self.round_num,
            'winner': self.winner.name if self.winner else 'AI',
            'winner_profile_id': self.winner.profile_id if self.winner and hasattr(self.winner, 'profile_id') else None,
            'players': []
        }

        for player in self.players:
            player_data = {
                'profile_id': player.profile_id if hasattr(player, 'profile_id') else None,
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

            # Update player profiles if they have profile_ids
            self._update_player_profiles(game_id)

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

    def _update_player_profiles(self, game_id: str):
        """Update player profiles after game completion."""
        pm = ProfileManager()

        for player in self.players:
            # Skip players without profiles (guests)
            if not hasattr(player, 'profile_id') or not player.profile_id:
                continue

            try:
                # Determine outcome
                if player == self.winner:
                    outcome = 'win'
                elif not player.alive:
                    outcome = 'loss'
                else:
                    outcome = 'ai_win'  # Game ended but player didn't win

                # Collect items used during game
                items_used = [item.name for item in player.items]

                # Update profile stats and check for achievements
                newly_unlocked = pm.update_stats_after_game(
                    player.profile_id,
                    {
                        'game_id': game_id,
                        'outcome': outcome,
                        'final_score': player.points,
                        'caught': not player.alive,
                        'rounds_played': self.round_num,
                        'num_opponents': self.num_players - 1,
                        'locations_chosen': player.choice_history,
                        'items_used': items_used
                    }
                )

                ui.console.print(f"[dim]Updated profile for {player.name}[/dim]")

                # Display achievement notifications
                for achievement in newly_unlocked:
                    ui.print_achievement_notification(achievement.name, achievement.description)

            except Exception as e:
                ui.console.print(f"[dim red]Failed to update profile for {player.name}: {e}[/dim red]")
