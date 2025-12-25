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
from game.events import EventManager
from game.hiding import HidingManager


class GameEngine:
    """Main game engine that runs LOOT RUN."""

    def __init__(self, num_players: int, profiles: Optional[List[Optional[PlayerProfile]]] = None):
        self.num_players = num_players
        self.profiles = profiles or []  # List of PlayerProfile objects (or None for guests)
        self.players: List[Player] = []
        self.location_manager = LocationManager()
        self.ai = AIPredictor(self.location_manager)
        self.event_manager = EventManager()
        self.hiding_manager = HidingManager()
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
                    # Get color for this player
                    from game.player import PLAYER_COLORS
                    player_color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
                    ui.console.print(f"[{player_color}]Player {i+1}: {profile.name}[/{player_color}] "
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

        # Generate events based on current game state
        game_state = {
            'round_num': self.round_num,
            'max_player_score': max((p.points for p in alive_players), default=0),
            'catches_last_3_rounds': self._count_recent_catches()
        }
        newly_spawned = self.event_manager.generate_events(
            game_state,
            self.location_manager.get_all()
        )

        # Show newly spawned events
        if newly_spawned:
            ui.clear()
            ui.print_header(f"ROUND {self.round_num}")
            ui.console.print("\n[bold cyan]🎲 NEW EVENT![/bold cyan]\n")
            for event in newly_spawned:
                ui.console.print(
                    f"  {event.emoji} [bold]{event.name}[/bold] at {event.affected_location.name}\n"
                    f"  [dim]{event.description} ({event.rounds_remaining} round{'s' if event.rounds_remaining > 1 else ''} remaining)[/dim]"
                )
            ui.console.print()
            ui.console.input("[dim]Press Enter to continue...[/dim]")

        for player in alive_players:
            # Clear console and show fresh context for this player
            ui.clear()
            ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")

            # Show current standings WITH choices made so far
            ui.print_standings(self.players, player_choices)

            # Show locations (same for all players this round)
            ui.print_locations(self.location_manager, self.last_ai_search_location, self.event_manager)

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

        # AI decides where to search (with event awareness)
        search_location, predictions, ai_reasoning = self.ai.decide_search_location(
            self.players,
            event_manager=self.event_manager
        )

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

                        # Track if item has its own prompt
                        auto_consumed_item = False

                        # Auto-activate items based on type
                        if item_type == ItemType.INTEL_REPORT:
                            self.show_intel_report(player)
                            item.consumed = True  # Intel Report is consumed immediately
                            auto_consumed_item = True
                        elif item_type == ItemType.SCOUT:
                            self.show_scout_preview(player)
                            player.use_item(ItemType.SCOUT)
                            auto_consumed_item = True

                        # Only show prompt for items without their own UI
                        if not auto_consumed_item:
                            ui.console.input("\n[dim]Press Enter to continue shopping...[/dim]")
                        ui.clear()
                        ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")

                        # Show locations so player has context
                        ui.print_locations(self.location_manager, self.last_ai_search_location, self.event_manager)

                        ui.console.print()
                        # Continue loop to allow more purchases
                    else:
                        ui.console.print(f"[red]Not enough points! Need {item.cost}, have {player.points}[/red]")
                        ui.console.input("\n[dim]Press Enter to continue...[/dim]")
                        ui.clear()
                        ui.print_header(f"ROUND {self.round_num} - {player.name.upper()}'S TURN")
                        ui.print_locations(self.location_manager, self.last_ai_search_location, self.event_manager)
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
            unique_locations = len(behavior['location_frequencies'])  # Direct count from dict
            insights.append(f"Limited variety (only {unique_locations} of {num_locations} locations visited)")

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
                    'total_games': profile.stats.total_games,
                    'hiding_stats': {
                        'total_caught': profile.hiding_stats.total_caught_instances,
                        'hide_attempts': profile.hiding_stats.hide_attempts,
                        'run_attempts': profile.hiding_stats.run_attempts,
                        'hide_success_rate': profile.hiding_stats.hide_success_rate,
                        'run_success_rate': profile.hiding_stats.run_success_rate,
                        'risk_profile_when_caught': profile.hiding_stats.risk_profile_when_caught
                    }
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

            # Roll individual points for this player FIRST (before catch check)
            # Check if this player used Scout and has a cached roll
            if player.id in self.scout_rolls and chosen_location.name in self.scout_rolls[player.id]:
                base_roll = self.scout_rolls[player.id][chosen_location.name]
            else:
                base_roll = chosen_location.roll_points()

            # Apply event point modifiers
            location_points = self.event_manager.apply_point_modifier(chosen_location, base_roll)

            # Check for event effects
            special_effect = self.event_manager.get_special_effect(chosen_location)

            # Determine if player is caught
            caught = (chosen_location.name == search_location.name)

            # Check for guaranteed catch event
            if special_effect == "guaranteed_catch" and not caught:
                # Small chance of being caught even if AI didn't search here
                import random
                if random.random() < 0.3:  # 30% chance
                    caught = True
                    ui.console.print(f"\n[red]⚠️ Silent Alarm! [{player.color}]{player.name}[/{player.color}] was caught![/red]")

            # Check for immunity event
            if special_effect == "immunity" and caught:
                # Immunity event - auto-escape with full points
                ui.console.print(f"\n[green]🛡️ Insurance Active! [{player.color}]{player.name}[/{player.color}] slips away undetected![/green]")
                caught = False  # Override caught status

            if caught:
                # Player caught - trigger hide/run mechanic (pass location_points)
                hide_run_result = self.handle_hide_or_run(player, chosen_location, search_location, location_points)

                if hide_run_result['escaped']:
                    # Player escaped! Still alive
                    player.alive = True
                    ui.print_escape_success(player, hide_run_result, search_location)
                    player.record_choice(chosen_location, self.round_num, caught=False,
                                       points_earned=hide_run_result.get('points_awarded', 0))
                else:
                    # Failed to escape - eliminated
                    player.alive = False
                    ui.print_escape_failure(player, hide_run_result, search_location)
                    player.record_choice(chosen_location, self.round_num, caught=True, points_earned=0)

                    # Show post-game report
                    insights = generate_insights(player, len(self.location_manager))
                    ui.print_post_game_report(player, insights)

                # Record hide/run attempt for AI learning
                player.record_hide_run_attempt(hide_run_result, self.round_num)
            else:
                # Player successfully looted - award points
                # Show event effect if points were modified
                if location_points != base_roll:
                    event = self.event_manager.get_location_event(chosen_location)
                    if event:
                        ui.console.print(
                            f"  {event.emoji} [cyan]{event.name}:[/cyan] "
                            f"{base_roll} → {location_points} points"
                        )

                player.add_points(location_points)
                ui.print_player_looted(player, chosen_location, location_points)

                # Record choice for AI learning
                player.record_choice(chosen_location, self.round_num, caught=False,
                                   points_earned=location_points, location_value=base_roll)

        ui.console.print()
        ui.print_standings(self.players)

        # Flush input buffer to prevent enter spam from skipping this prompt
        ui.flush_input()
        ui.console.input("\n[dim]Press Enter to continue to next round...[/dim]")

        # Tick events (decrease duration, remove expired)
        expired_events = self.event_manager.tick_events()
        if expired_events:
            ui.console.print("\n[dim]Events ended:[/dim]")
            for event in expired_events:
                ui.console.print(
                    f"  [dim]{event.emoji} {event.name} at {event.affected_location.name}[/dim]"
                )
            ui.console.print()

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

                # Collect hiding stats from this game
                hiding_data = {
                    'hide_attempts': player.hiding_stats['total_hide_attempts'],
                    'successful_hides': player.hiding_stats['successful_hides'],
                    'run_attempts': player.hiding_stats['total_run_attempts'],
                    'successful_runs': player.hiding_stats['successful_runs'],
                    'favorite_hiding_spots': player.hiding_stats['favorite_hide_spots'],
                    'total_caught_instances': len(player.hide_run_history)
                }

                # Calculate achievement-related stats
                escapes_in_game = sum(
                    1 for attempt in player.hide_run_history
                    if attempt.get('escaped', False)
                )
                high_threat_escape = any(
                    attempt.get('escaped', False) and attempt.get('ai_threat_level', 0) >= 0.9
                    for attempt in player.hide_run_history
                )

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
                        'items_used': items_used,
                        'hiding_data': hiding_data,
                        'escapes_in_game': escapes_in_game,
                        'high_threat_escape': high_threat_escape
                    }
                )

                ui.console.print(f"[dim]Updated profile for {player.name}[/dim]")

                # Display achievement notifications
                for achievement in newly_unlocked:
                    ui.print_achievement_notification(achievement.name, achievement.description)

            except Exception as e:
                ui.console.print(f"[dim red]Failed to update profile for {player.name}: {e}[/dim red]")

    def _count_recent_catches(self) -> int:
        """
        Count total catches in last 3 rounds across all players.

        Returns:
            Number of catches in the last 3 rounds
        """
        count = 0
        for player in self.players:
            if len(player.choice_history) >= 3:
                # choice_history contains tuples: (location, round, success, ...)
                recent = player.choice_history[-3:]
                for choice in recent:
                    if len(choice) >= 3 and not choice[2]:  # choice[2] is success (False = caught)
                        count += 1
        return count

    def handle_hide_or_run(self, player: Player, caught_location: Location,
                          search_location: Location, location_points: int) -> Dict[str, any]:
        """
        Handle the hide or run decision when player is caught.

        Args:
            player: Player who was caught
            caught_location: Location where player was caught
            search_location: Location AI searched
            location_points: Points rolled at this location

        Returns:
            Dict with choice, escaped, points_awarded, hide_spot_id, ai_threat_level, success_chance
        """
        # Calculate AI threat level for this player
        ai_threat = self.ai._calculate_win_threat(player)

        # Show caught message
        ui.print_caught_message(player, caught_location)

        # Present choice
        choice_type = ui.get_hide_or_run_choice(player, caught_location, ai_threat)

        if choice_type == 'hide':
            return self._handle_hide_attempt(player, caught_location, ai_threat)
        else:  # 'run'
            return self._handle_run_attempt(player, caught_location, ai_threat, location_points)

    def _handle_hide_attempt(self, player: Player, location: Location,
                            ai_threat: float) -> Dict[str, any]:
        """Handle hiding attempt with location-specific spots."""
        hiding_spots = self.hiding_manager.get_hiding_spots_for_location(location.name)

        # Show hiding spots to player
        chosen_spot = ui.select_hiding_spot(hiding_spots, player)

        # Calculate base success chance
        success_chance = self.hiding_manager.calculate_hide_success_chance(
            chosen_spot, player, ai_threat
        )

        # Track item effects for display
        item_effects = []

        # Check for smoke bomb item (+25% success)
        from game.items import ItemType
        if player.has_item(ItemType.SMOKE_BOMB):
            player.use_item(ItemType.SMOKE_BOMB)
            success_chance = min(0.95, success_chance + 0.25)
            item_effects.append("💨 Smoke Bomb: +25% escape chance")
            ui.console.print("[green]💨 You use a Smoke Bomb to obscure your hiding![/green]")

        # Check for guaranteed catch event (-20% success)
        special_effect = self.event_manager.get_special_effect(location)
        if special_effect == "guaranteed_catch":
            success_chance = max(0.1, success_chance - 0.2)
            item_effects.append("🚨 Silent Alarm: -20% escape chance")
            ui.console.print("[red]🚨 The alarm makes hiding more difficult![/red]")

        # Roll for success
        import random
        escaped = random.random() < success_chance

        return {
            'choice': 'hide',
            'escaped': escaped,
            'points_awarded': 0,  # Hiding gives no points
            'hide_spot_id': chosen_spot['id'],
            'hide_spot_name': chosen_spot['name'],
            'ai_threat_level': ai_threat,
            'success_chance': success_chance,
            'item_effects': item_effects
        }

    def _handle_run_attempt(self, player: Player, location: Location,
                           ai_threat: float, location_points: int) -> Dict[str, any]:
        """Handle running attempt with AI-adjusted escape chance."""
        # Calculate base escape chance
        escape_chance = self.hiding_manager.calculate_run_escape_chance(player, ai_threat)

        # Calculate 80% of LOCATION points only
        retention_rate = self.hiding_manager.get_run_point_retention()  # 0.8
        location_points_retained = int(location_points * retention_rate)
        points_after_escape = player.points + location_points_retained

        # Show run option with calculated chances
        confirmed = ui.confirm_run_attempt(player, escape_chance, points_after_escape, location_points)

        if not confirmed:
            # Player changed mind - go back to hide choice
            return self._handle_hide_attempt(player, location, ai_threat)

        # Track item effects for display
        item_effects = []

        # Check for smoke bomb (+25% escape chance)
        from game.items import ItemType
        if player.has_item(ItemType.SMOKE_BOMB):
            player.use_item(ItemType.SMOKE_BOMB)
            escape_chance = min(0.95, escape_chance + 0.25)
            item_effects.append("💨 Smoke Bomb: +25% escape chance")
            ui.console.print("[green]💨 You use a Smoke Bomb to cover your escape![/green]")

        # Roll for success
        import random
        escaped = random.random() < escape_chance

        # Calculate points - only keep if escaped
        if escaped:
            # Add 80% of location points to total
            player.points += location_points_retained
        else:
            # Failed to escape - don't add any location points (lose them all)
            pass

        return {
            'choice': 'run',
            'escaped': escaped,
            'points_awarded': 0,  # Points already adjusted via player.points
            'hide_spot_id': None,
            'hide_spot_name': None,
            'ai_threat_level': ai_threat,
            'success_chance': escape_chance,
            'points_retained': location_points_retained if escaped else 0,
            'item_effects': item_effects
        }
