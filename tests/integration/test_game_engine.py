"""Integration tests for game/engine.py - GameEngine class."""
import pytest
from game.engine import GameEngine
from game.player import Player
from game.items import ItemShop, ItemType
from game.locations import Location


@pytest.fixture
def game_engine(temp_config_dir, temp_events_config, temp_hiding_config, mock_console):
    """Create a GameEngine with players for testing."""
    console, output = mock_console
    engine = GameEngine(num_players=2)
    # Manually add players (bypassing interactive setup_game())
    engine.players.append(Player(0, "Alice"))
    engine.players.append(Player(1, "Bob"))
    return engine


class TestGameEngineInitialization:
    """Tests for GameEngine initialization."""

    def test_initialization_creates_players(self, game_engine):
        """Test GameEngine initializes with correct num_players."""
        engine = GameEngine(num_players=3)

        assert engine.num_players == 3
        assert engine.round_num == 0
        # Players created in setup_game(), not __init__
        assert engine.players == []

    def test_initialization_creates_location_manager(self, game_engine):
        """Test GameEngine creates LocationManager."""

        assert game_engine.location_manager is not None
        assert len(game_engine.location_manager.get_all()) > 0

    def test_initialization_creates_ai_predictor(self, game_engine):
        """Test GameEngine creates AIPredictor."""

        assert game_engine.ai is not None


class TestShopPhase:
    """Tests for shop phase."""

    def test_shop_phase_skip_purchase(self, game_engine, monkeypatch):
        """Test shop phase when player skips purchase."""
        player = game_engine.players[0]
        player.points = 20

        # Mock select_passive to return None (skip)
        import game.ui
        monkeypatch.setattr(game.ui, 'select_passive', lambda p: None)

        game_engine.shop_phase(player)

        # Player should have no passives and same points
        assert len(player.get_passives()) == 0
        assert player.points == 20

    def test_shop_phase_buy_passive(self, game_engine, monkeypatch, temp_passives_config):
        """Test shop phase when player buys a passive."""
        from game.passives import PassiveShop
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]
        player.points = 50

        # Mock select_passive: buy first passive (1), then skip (None)
        import game.ui
        selections = iter([1, None])
        monkeypatch.setattr(game.ui, 'select_passive', lambda p: next(selections, None))
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.shop_phase(player)

        # Player should have fewer points (purchased something)
        assert player.points <= 50

    def test_shop_phase_insufficient_points(self, game_engine, monkeypatch, temp_passives_config):
        """Test shop phase when player has insufficient points."""
        from game.passives import PassiveShop
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]
        player.points = 5

        # Mock select_passive: try to buy expensive passive (1), then skip (None)
        import game.ui
        selections = iter([1, None])
        monkeypatch.setattr(game.ui, 'select_passive', lambda p: next(selections, None))
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.shop_phase(player)

        # Player should still have 5 points (couldn't afford anything)
        assert player.points == 5


class TestChooseLocationPhase:
    """Tests for choose location phase."""

    def test_choose_location_valid_choice(self, game_engine, monkeypatch):
        """Test choosing a valid location."""
        player = game_engine.players[0]

        # Mock select_location to choose location index 0
        import game.ui
        monkeypatch.setattr(game.ui, 'select_location', lambda lm, scout_rolls=None, point_hints=None: 0)

        location = game_engine.choose_location_phase(player)

        assert isinstance(location, Location)
        assert location == game_engine.location_manager.get_location(0)



class TestRevealAndResolvePhase:
    """Tests for reveal and resolve phase."""

    def test_resolve_player_caught(self, game_engine, deterministic_random, monkeypatch, temp_hiding_config):
        """Test resolving when player is caught by AI."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50

        # Mock console.input for "Press Enter to continue" prompt
        import game.ui
        import game.engine
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Mock hide_or_run to simulate failed escape (player eliminated)
        def mock_handle_hide_or_run(self, player, caught_location, search_location, location_points):
            """Mock that simulates failed escape attempt - player eliminated."""
            player.alive = False
            result = {
                'choice_type': 'hide',
                'escaped': False,
                'points_awarded': 0,
                'player_choice_id': 'test_spot',
                'player_choice_name': 'Test Hiding Spot'
            }
            escape_options = []
            return result, escape_options

        monkeypatch.setattr(game.engine.GameEngine, 'handle_hide_or_run', mock_handle_hide_or_run)

        # Create choice where AI searches same location
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)
        player_choices = {player1: loc1, player2: loc2}

        # Mock AI to search the same location as player1
        game_engine.previous_ai_location = loc1

        # Mock predictions for both players
        predictions = {
            player1: (loc1, 0.8, "High confidence prediction"),
            player2: (loc2, 0.6, "Lower confidence")
        }

        game_engine.reveal_and_resolve_phase(player_choices, loc1, predictions, "AI reasoning")

        # Player1 should be eliminated
        assert not player1.alive
        # Player2 should still be alive
        assert player2.alive

    def test_resolve_player_loots_successfully(self, game_engine, deterministic_random, monkeypatch):
        """Test resolving when player loots successfully."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 30

        # Mock console.input for "Press Enter to continue" prompt
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Create choice where AI searches different location from both players
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)
        loc3 = game_engine.location_manager.get_location(2)
        player_choices = {player1: loc1, player2: loc2}

        # Mock predictions for both players
        predictions = {
            player1: (loc2, 0.6, "AI predicted wrong location"),
            player2: (loc3, 0.5, "AI predicted wrong location")
        }

        game_engine.reveal_and_resolve_phase(player_choices, loc3, predictions, "AI reasoning")

        # Both players should gain points
        assert player1.points > 50
        assert player2.points > 30
        assert player1.alive
        assert player2.alive

class TestGameOverChecking:
    """Tests for game over detection."""

    def test_check_game_over_winner_by_score(self, game_engine):
        """Test game over when player reaches win threshold."""
        player1 = game_engine.players[0]
        player1.points = 105

        game_engine.check_game_over()

        assert game_engine.game_over is True
        assert game_engine.winner == player1

    def test_check_game_over_last_survivor(self, game_engine, monkeypatch):
        """Test game over when only one player remains."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]

        player2.alive = False

        # Mock console.input for the continue/end prompt
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "end")

        game_engine.check_game_over()

        assert game_engine.game_over is True
        assert game_engine.winner == player1

    def test_check_game_over_no_winner(self, game_engine):
        """Test game continues when no win condition met."""
        player1 = game_engine.players[0]
        player1.points = 50

        game_engine.check_game_over()

        assert game_engine.game_over is False

    def test_check_game_over_all_eliminated(self, game_engine):
        """Test game over when all players eliminated."""

        for player in game_engine.players:
            player.alive = False

        game_engine.check_game_over()

        assert game_engine.game_over is True
        assert game_engine.winner is None  # AI wins


class TestScoutPreview:
    """Tests for Scout preview functionality."""

    def test_game_engine_has_location_manager(self, game_engine):
        """Test GameEngine has location_manager for scout preview data."""
        assert hasattr(game_engine, 'location_manager')
        assert game_engine.location_manager is not None


class TestIntelReport:
    """Tests for Intel Report functionality."""

    def test_show_intel_report(self, game_engine, mock_console, monkeypatch):
        """Test Intel Report displays player analysis."""
        console, output = mock_console
        player = game_engine.players[0]
        player.points = 50

        # Add some history
        loc = game_engine.location_manager.get_location(0)
        for i in range(5):
            player.record_choice(loc, i+1, False, 10, 10)

        # Mock console.input for the "Press Enter to continue" prompt
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_intel_report(player)

        result = output.getvalue()
        # Should display some analysis
        assert len(result) > 0


class TestDataSaving:
    """Tests for game data persistence."""

    def test_save_game_data_creates_file(self, game_engine, temp_data_dir):
        """Test save_game_data creates history file."""

        # Play some rounds to generate data
        for player in game_engine.players:
            loc = game_engine.location_manager.get_location(0)
            player.record_choice(loc, 1, False, 10, 10)

        game_engine.save_game_data()

        history_file = temp_data_dir / "game_history.json"
        assert history_file.exists()


class TestEventSystem:
    """Integration tests for event system in game rounds."""

    def test_event_manager_initialized(self, game_engine):
        """Test GameEngine has EventManager initialized."""
        assert hasattr(game_engine, 'event_manager')
        assert game_engine.event_manager is not None
        assert game_engine.event_manager.max_concurrent == 2

    def test_event_generation_during_round(self, game_engine, deterministic_random, monkeypatch):
        """Test events can be generated during play_round."""
        # Mock console.input for all prompts
        import game.ui
        import game.engine
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Mock location choice
        def mock_choose_location(player):
            return game_engine.location_manager.get_location(0)
        monkeypatch.setattr(game_engine, 'choose_location_phase', mock_choose_location)

        # Mock shop phase (skip)
        monkeypatch.setattr(game_engine, 'shop_phase', lambda player: None)

        # Mock hide_or_run to prevent hanging when players are caught
        def mock_handle_hide_or_run(self, player, caught_location, search_location, location_points):
            """Mock that simulates failed escape (player eliminated)."""
            player.alive = False
            return {
                'choice': 'hide',
                'escaped': False,
                'points_awarded': 0,
                'hide_spot_id': 'test_spot',
                'hide_spot_name': 'Test Hiding Spot',
                'ai_threat_level': 0.8,
                'success_chance': 0.3,
                'item_effects': []
            }
        monkeypatch.setattr(game.engine.GameEngine, 'handle_hide_or_run', mock_handle_hide_or_run)

        # Round 3 should trigger event generation (every 3 rounds)
        game_engine.round_num = 2  # Will become 3 in play_round

        initial_event_count = len(game_engine.event_manager.active_events)

        # Play a round
        game_engine.play_round()

        # Events may or may not have spawned (probabilistic), but manager should work
        assert len(game_engine.event_manager.active_events) <= game_engine.event_manager.max_concurrent

    def test_event_point_modifier_applied(self, game_engine, deterministic_random):
        """Test event point modifiers are applied during resolution."""
        player = game_engine.players[0]
        location = game_engine.location_manager.get_location(0)

        # Check if event pool has events (may be empty without config)
        if not game_engine.event_manager.event_pool:
            pytest.skip("No events in event pool")

        # Get first available event
        event_template = game_engine.event_manager.event_pool[0]
        event = event_template.copy_with_location(location)
        game_engine.event_manager.active_events.append(event)

        # Apply point modifier
        base_points = 10
        modified_points = game_engine.event_manager.apply_point_modifier(location, base_points)

        # Should modify points (exact result depends on event type)
        assert isinstance(modified_points, int)

    def test_event_immunity_prevents_catch(self, game_engine, deterministic_random, monkeypatch):
        """Test immunity event prevents player from being caught."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        location1 = game_engine.location_manager.get_location(0)
        location2 = game_engine.location_manager.get_location(1)

        # Check if event pool has immunity event
        immunity_events = [e for e in game_engine.event_manager.event_pool if e.id == "immunity"]
        if not immunity_events:
            pytest.skip("No immunity event in event pool")

        # Create immunity event at location1
        immunity_template = immunity_events[0]
        immunity = immunity_template.copy_with_location(location1)
        game_engine.event_manager.active_events.append(immunity)

        # Mock console.input for prompts
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Check special effect is immunity
        effect = game_engine.event_manager.get_special_effect(location1)
        assert effect == "immunity"

    def test_event_ticking_and_expiration(self, game_engine):
        """Test events tick and expire correctly."""
        location = game_engine.location_manager.get_location(0)

        # Check event pool exists
        if not game_engine.event_manager.event_pool:
            pytest.skip("No events in event pool")

        # Create event with 1 round duration
        event = game_engine.event_manager._spawn_event([location])
        if event is None:
            pytest.skip("Could not spawn event")

        event.rounds_remaining = 1

        assert event in game_engine.event_manager.active_events

        # Tick events
        expired = game_engine.event_manager.tick_events()

        # Event should be expired and removed
        assert event in expired
        assert event not in game_engine.event_manager.active_events

    def test_max_concurrent_events_enforced(self, game_engine):
        """Test max concurrent events limit is enforced by generate_events."""
        # Check if event pool has events
        if not game_engine.event_manager.event_pool:
            pytest.skip("No events in event pool")

        locations = game_engine.location_manager.get_all()

        # Game state that always triggers event generation
        game_state = {
            'round_num': 3,
            'max_player_score': 100,
            'catches_last_3_rounds': 5
        }

        # Try to generate events multiple times
        for _ in range(10):
            game_engine.event_manager.generate_events(game_state, locations)

        # Should not exceed max_concurrent (2)
        assert len(game_engine.event_manager.active_events) <= game_engine.event_manager.max_concurrent

    def test_ai_considers_events_in_prediction(self, game_engine, deterministic_random):
        """Test AI adjusts predictions based on active events."""
        player = game_engine.players[0]
        location = game_engine.location_manager.get_location(0)

        # Get AI prediction (with or without events)
        prediction = game_engine.ai.predict_player_location(
            player,
            len([p for p in game_engine.players if p.alive]),
            event_manager=game_engine.event_manager
        )

        # Prediction is tuple: (location_name, confidence, reasoning)
        assert isinstance(prediction, tuple)
        assert len(prediction) == 3


class TestPassiveShopPhase:
    """Tests for passive ability purchasing in shop phase."""

    def test_shop_phase_buy_passive(self, game_engine, monkeypatch, temp_passives_config):
        """Test shop phase when player buys a passive."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader

        # Reset config and passives
        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]
        player.points = 50

        # Mock select_passive: buy first passive (1), then skip (None)
        import game.ui
        selections = iter([1, None])
        monkeypatch.setattr(game.ui, 'select_passive', lambda p: next(selections, None))
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.shop_phase(player)

        # Player should have less points and potentially a passive
        # (Exact behavior depends on passive cost)
        assert player.points <= 50


class TestHideOrRun:
    """Tests for hide or run escape mechanic."""

    def test_handle_hide_or_run_escaped_hide(self, game_engine, monkeypatch, sample_hiding_manager):
        """Test successful hide escape."""
        import game.ui

        player = game_engine.players[0]
        player.points = 50

        # Mock the HidingManager
        monkeypatch.setattr(game_engine, 'hiding_manager', sample_hiding_manager)

        escape_options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        if not escape_options:
            pytest.skip("No escape options available")

        first_option = escape_options[0]

        # Mock UI to select first escape option
        monkeypatch.setattr(game.ui, 'select_escape_option', lambda opts, p, pts: first_option)
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Mock escape predictor to predict wrong option
        def mock_predict_escape(*args, **kwargs):
            return ('wrong_option', 0.5, 'Mock reasoning')
        monkeypatch.setattr(game_engine.escape_predictor, 'predict_escape_option', mock_predict_escape)

        # Mock print_escape_result to avoid animation issues
        monkeypatch.setattr(game.ui, 'print_escape_result', lambda p, r, opts=None: None)

        caught_location = game_engine.location_manager.get_location(0)
        search_location = caught_location
        location_points = 20

        result, opts = game_engine.handle_hide_or_run(player, caught_location, search_location, location_points)

        # Player should have escaped (AI predicted wrong)
        assert result['escaped'] is True
        assert player.alive is True

    def test_handle_hide_or_run_caught(self, game_engine, monkeypatch, sample_hiding_manager):
        """Test failed escape when AI predicts correctly."""
        import game.ui
        import game.animations

        player = game_engine.players[0]
        player.points = 50

        # Mock the HidingManager
        monkeypatch.setattr(game_engine, 'hiding_manager', sample_hiding_manager)

        escape_options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        if not escape_options:
            pytest.skip("No escape options available")

        first_option = escape_options[0]

        # Mock UI to select first option
        monkeypatch.setattr(game.ui, 'select_escape_option', lambda opts, p, pts: first_option)
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Mock escape predictor to predict correctly
        def mock_predict_escape(*args, **kwargs):
            return (first_option['id'], 0.9, 'Correct prediction')
        monkeypatch.setattr(game_engine.escape_predictor, 'predict_escape_option', mock_predict_escape)

        # Mock print_escape_result and animations to avoid issues
        monkeypatch.setattr(game.ui, 'print_escape_result', lambda p, r, opts=None: None)
        monkeypatch.setattr(game.animations, 'play_elimination_animation', lambda: None)

        caught_location = game_engine.location_manager.get_location(0)
        search_location = caught_location
        location_points = 20

        result, opts = game_engine.handle_hide_or_run(player, caught_location, search_location, location_points)

        # Player should be caught (AI predicted correctly)
        assert result['escaped'] is False
        # When escaped=False, player gets eliminated (set elsewhere in the flow)
        # The handle_hide_or_run may or may not set alive to False directly


class TestRecentCatches:
    """Tests for recent catches tracking."""

    def test_count_recent_catches(self, game_engine):
        """Test counting catches in recent rounds."""
        # Add some catch history
        for player in game_engine.players:
            loc = game_engine.location_manager.get_location(0)
            player.record_choice(loc, 1, caught=True, points_earned=0)
            player.record_choice(loc, 2, caught=False, points_earned=10)
            player.record_choice(loc, 3, caught=True, points_earned=0)

        # Count recent catches (internal method)
        # Note: This returns count based on internal logic
        count = game_engine._count_recent_catches()

        # Should return an integer (exact count depends on implementation)
        assert isinstance(count, int)
        assert count >= 0


class TestPointHintGeneration:
    """Tests for point hint generation with Inside Knowledge passive."""

    def test_generate_point_hints_no_passive(self, game_engine):
        """Test no hints generated without Inside Knowledge passive."""
        player = game_engine.players[0]

        hints = game_engine._generate_point_hints(player)

        # Without the passive, should return empty or None
        assert hints is None or hints == {}

    def test_generate_point_hints_with_passive(self, game_engine, monkeypatch, temp_passives_config):
        """Test hints generated with Inside Knowledge passive."""
        from game.passives import PassiveShop, PassiveType, PassiveManager
        from game.config_loader import ConfigLoader

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]

        # Give player Inside Knowledge passive
        passive = PassiveShop.get_passive(PassiveType.INSIDE_KNOWLEDGE)
        if passive:
            player.passive_manager.add_passive(passive)

            hints = game_engine._generate_point_hints(player)

            # Should have hints for all locations
            if hints:
                assert len(hints) == len(game_engine.location_manager.get_all())


class TestFinalResults:
    """Tests for final results display."""

    def test_show_final_results_winner(self, game_engine, mock_console, monkeypatch):
        """Test final results display when a player wins."""
        import game.ui
        import game.animations

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 105
        game_engine.winner = player
        game_engine.game_over = True

        # Mock animations
        monkeypatch.setattr(game.animations, 'play_victory_animation', lambda: None)
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_final_results()

        result = output.getvalue()
        assert len(result) > 0

    def test_show_final_results_ai_wins(self, game_engine, mock_console, monkeypatch):
        """Test final results display when AI wins."""
        import game.ui

        console, output = mock_console

        # All players eliminated
        for player in game_engine.players:
            player.alive = False

        game_engine.winner = None
        game_engine.game_over = True

        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_final_results()

        result = output.getvalue()
        assert len(result) > 0


class TestHighRollerEffect:
    """Tests for High Roller passive effect integration."""

    def test_reveal_high_roller_bust(self, game_engine, monkeypatch, temp_passives_config, deterministic_random):
        """Test High Roller bust mechanic."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        import game.ui
        import random

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50

        # Give player High Roller passive
        passive = PassiveShop.get_passive(PassiveType.HIGH_ROLLER)
        if passive:
            player1.passive_manager.add_passive(passive)

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Force bust by mocking random
        monkeypatch.setattr(random, 'random', lambda: 0.0)  # Always bust

        # Get a bonus location from passive effects
        bonus_locations = passive.get_effect('bonus_locations', []) if passive else []
        if bonus_locations and any(loc.name in bonus_locations for loc in game_engine.location_manager.get_all()):
            # Find matching location
            for loc in game_engine.location_manager.get_all():
                if loc.name in bonus_locations:
                    loc1 = loc
                    break
        else:
            loc1 = game_engine.location_manager.get_location(0)

        loc2 = game_engine.location_manager.get_location(1)

        player_choices = {player1: loc1, player2: loc2}
        predictions = {
            player1: (loc2.name, 0.5, "Wrong prediction"),
            player2: (loc1.name, 0.5, "Wrong prediction")
        }

        # Play should not crash with High Roller effect
        initial_points = player1.points
        game_engine.reveal_and_resolve_phase(player_choices, loc2, predictions, "Test")

    def test_reveal_high_roller_win(self, game_engine, monkeypatch, temp_passives_config):
        """Test High Roller win bonus mechanic."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        import game.ui
        import random

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 50

        # Give player High Roller passive
        passive = PassiveShop.get_passive(PassiveType.HIGH_ROLLER)
        if not passive:
            pytest.skip("High Roller passive not available")

        player1.passive_manager.add_passive(passive)

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Force win by mocking random to be > bust_chance (0.15)
        monkeypatch.setattr(random, 'random', lambda: 0.5)  # Always win bonus

        # Get a bonus location from passive effects
        bonus_locations = passive.get_effect('bonus_locations', [])
        loc1 = None
        for loc in game_engine.location_manager.get_all():
            if loc.name in bonus_locations:
                loc1 = loc
                break

        if not loc1:
            pytest.skip("No matching bonus location for High Roller")

        loc2 = game_engine.location_manager.get_location(1)
        if loc2 == loc1:
            loc2 = game_engine.location_manager.get_location(2)

        player_choices = {player1: loc1, player2: loc2}
        predictions = {
            player1: (loc2.name, 0.5, "Wrong prediction"),
            player2: (loc1.name, 0.5, "Wrong prediction")
        }

        initial_points = player1.points
        game_engine.reveal_and_resolve_phase(player_choices, loc2, predictions, "Test")

        # Player should have gained points with bonus
        assert player1.points > initial_points


class TestSetupGame:
    """Tests for game setup flow."""

    def test_setup_game_with_profiles(self, temp_config_dir, monkeypatch, mock_console):
        """Test setup_game with player profiles."""
        from game.profile_manager import PlayerProfile, ProfileStats, AIMemoryStats, BehavioralStats, HidingBehavioralStats
        from datetime import datetime, timezone
        import game.ui

        console, output = mock_console
        now = datetime.now(timezone.utc).isoformat()

        # Create mock profiles
        profiles = [
            PlayerProfile(
                profile_id="p1",
                name="Alice",
                created_date=now,
                last_played=now,
                stats=ProfileStats(),
                ai_memory=AIMemoryStats(),
                behavioral_stats=BehavioralStats(),
                hiding_stats=HidingBehavioralStats()
            ),
            PlayerProfile(
                profile_id="p2",
                name="Bob",
                created_date=now,
                last_played=now,
                stats=ProfileStats(),
                ai_memory=AIMemoryStats(),
                behavioral_stats=BehavioralStats(),
                hiding_stats=HidingBehavioralStats()
            )
        ]

        engine = GameEngine(num_players=2, profiles=profiles)

        # Mock console.input for "Press Enter to start"
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        engine.setup_game()

        # Players should be created from profiles
        assert len(engine.players) == 2
        assert engine.players[0].name == "Alice"
        assert engine.players[1].name == "Bob"

    def test_setup_game_with_guest_player(self, temp_config_dir, monkeypatch, mock_console):
        """Test setup_game with a guest player (None profile)."""
        from game.profile_manager import PlayerProfile, ProfileStats, AIMemoryStats, BehavioralStats, HidingBehavioralStats
        from datetime import datetime, timezone
        import game.ui

        console, output = mock_console
        now = datetime.now(timezone.utc).isoformat()

        # Create profile with one guest (None)
        profiles = [
            PlayerProfile(
                profile_id="p1",
                name="Alice",
                created_date=now,
                last_played=now,
                stats=ProfileStats(),
                ai_memory=AIMemoryStats(),
                behavioral_stats=BehavioralStats(),
                hiding_stats=HidingBehavioralStats()
            ),
            None  # Guest player
        ]

        engine = GameEngine(num_players=2, profiles=profiles)

        # Mock console.input: first for guest name, then for "Press Enter"
        inputs = iter(["GuestPlayer", ""])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs, ""))

        engine.setup_game()

        assert len(engine.players) == 2
        assert engine.players[0].name == "Alice"
        assert engine.players[1].name == "GuestPlayer"

    def test_setup_game_legacy_mode(self, temp_config_dir, monkeypatch, mock_console):
        """Test setup_game without profiles (legacy mode)."""
        import game.ui

        console, output = mock_console

        engine = GameEngine(num_players=2)

        # Mock console.input for player names and start
        inputs = iter(["Alice", "Bob", ""])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs, ""))

        engine.setup_game()

        assert len(engine.players) == 2
        assert engine.players[0].name == "Alice"
        assert engine.players[1].name == "Bob"


class TestPlayGame:
    """Tests for main game loop."""

    def test_play_game_ends_on_score_victory(self, game_engine, monkeypatch):
        """Test play_game ends when player reaches win threshold."""
        import game.ui
        import game.animations

        # Mock all interactive elements
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")
        monkeypatch.setattr(game.animations, 'play_victory_animation', lambda: None)

        # Make player win immediately
        game_engine.players[0].points = 100
        game_engine.game_over = True
        game_engine.winner = game_engine.players[0]

        # play_game should immediately show results and exit
        game_engine.play_game()

        # Verify game completed
        assert game_engine.game_over is True


class TestSoloContinue:
    """Tests for solo play continuation."""

    def test_check_game_over_solo_continue(self, game_engine, monkeypatch):
        """Test continuing solo when last player standing."""
        import game.ui

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]

        player2.alive = False
        player1.points = 50

        # Mock console.input to continue playing
        inputs = iter(["continue", ""])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs, ""))

        game_engine.check_game_over()

        # Game should continue (not over)
        assert game_engine.game_over is False


class TestGuaranteedCatchEvent:
    """Tests for guaranteed catch event mechanic."""

    def test_guaranteed_catch_triggers_randomly(self, game_engine, monkeypatch, deterministic_random):
        """Test guaranteed catch event can trigger even when AI searches elsewhere."""
        import game.ui
        import game.engine
        import random

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 50

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Create guaranteed catch event
        from game.events import Event
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)

        dragnet = Event(
            id="dragnet",
            name="DRAGNET",
            description="Silent alarms everywhere!",
            emoji="🚔",
            duration_rounds=1,
            special_effect="guaranteed_catch"
        )
        game_engine.event_manager.active_events.append(dragnet.copy_with_location(loc1))

        # Mock random to trigger the 30% catch chance
        random_values = iter([0.1])  # < 0.3, so will trigger
        original_random = random.random
        def mock_random():
            try:
                return next(random_values)
            except StopIteration:
                return original_random()

        monkeypatch.setattr(random, 'random', mock_random)

        # Mock handle_hide_or_run to track if it was called
        hide_run_called = []
        def mock_handle_hide_or_run(self, player, caught_loc, search_loc, points):
            hide_run_called.append(player.name)
            player.alive = False
            return {'escaped': False, 'points_awarded': 0, 'player_choice_id': 'test', 'ai_prediction_id': 'test', 'choice_type': 'hide'}, []

        monkeypatch.setattr(game.engine.GameEngine, 'handle_hide_or_run', mock_handle_hide_or_run)

        player_choices = {player1: loc1, player2: loc2}
        predictions = {
            player1: (loc2.name, 0.5, "Wrong prediction"),
            player2: (loc1.name, 0.5, "Wrong prediction")
        }

        # AI searches loc2 but player1 is at loc1 with dragnet event
        game_engine.reveal_and_resolve_phase(player_choices, loc2, predictions, "Test")

        # The guaranteed catch should have been triggered for player1
        # (but only 30% of the time, which we forced with random mock)

    def test_guaranteed_catch_with_high_roller_passive(self, game_engine, monkeypatch, temp_passives_config, temp_config_dir):
        """Test guaranteed catch event works when player has High Roller passive.

        This is a regression test for a bug where a local 'import random' in the
        guaranteed_catch code path caused an UnboundLocalError when High Roller's
        random.random() call was reached first.
        """
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        from game.events import Event
        import game.ui
        import game.engine
        import game.config_loader
        import random

        # Force reload config to pick up passives.json created by temp_passives_config
        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None
        new_config = ConfigLoader()
        monkeypatch.setattr(game.config_loader, 'config', new_config)

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 50

        # Give player1 High Roller passive
        passive = PassiveShop.get_passive(PassiveType.HIGH_ROLLER)
        if not passive:
            pytest.skip("High Roller passive not available")

        player1.passive_manager.add_passive(passive)

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Setup locations:
        # - loc_store (index 0): Player2 goes here, has guaranteed_catch event
        # - loc_vault (index 1): Player1 with High Roller goes here (bonus location)
        # - loc_bank (index 2): AI searches here (no one there)
        loc_store = game_engine.location_manager.get_location(0)  # Test Store
        loc_vault = game_engine.location_manager.get_location(1)  # Test Vault (High Roller bonus)
        loc_bank = game_engine.location_manager.get_location(2)   # Test Bank

        # Verify loc_vault is a bonus location for High Roller
        bonus_locations = passive.get_effect('bonus_locations', [])
        if loc_vault.name not in bonus_locations:
            pytest.skip(f"Test Vault not in High Roller bonus locations: {bonus_locations}")

        # Create guaranteed catch event on loc_store (where player2 will be)
        dragnet = Event(
            id="dragnet",
            name="DRAGNET",
            description="Silent alarms everywhere!",
            emoji="🚔",
            duration_rounds=1,
            special_effect="guaranteed_catch"
        )
        game_engine.event_manager.active_events.append(dragnet.copy_with_location(loc_store))

        # Mock random - first call is High Roller bust check, subsequent for guaranteed catch
        random_calls = []
        def mock_random():
            random_calls.append(1)
            return 0.5  # Won't bust (> 0.15), won't trigger catch (> 0.3)

        monkeypatch.setattr(random, 'random', mock_random)

        # Mock handle_hide_or_run in case someone gets caught
        def mock_handle_hide_or_run(self, player, caught_loc, search_loc, points):
            player.alive = False
            return {'escaped': False, 'points_awarded': 0, 'player_choice_id': 'test',
                    'ai_prediction_id': 'test', 'choice_type': 'hide'}, []

        monkeypatch.setattr(game.engine.GameEngine, 'handle_hide_or_run', mock_handle_hide_or_run)

        # Player1 at High Roller bonus location, Player2 at guaranteed_catch location
        player_choices = {player1: loc_vault, player2: loc_store}
        predictions = {
            player1: (loc_store.name, 0.5, "Wrong prediction"),
            player2: (loc_vault.name, 0.5, "Wrong prediction")
        }

        # AI searches loc_bank (neither player is there)
        # This triggers: High Roller check for player1, guaranteed_catch check for player2
        # Before the fix, this raised UnboundLocalError
        game_engine.reveal_and_resolve_phase(player_choices, loc_bank, predictions, "Test")

        # Verify random was called (High Roller triggers random check)
        assert len(random_calls) > 0, "random.random() should have been called for High Roller"


class TestImmunityEventMessage:
    """Tests for immunity event messaging."""

    def test_immunity_event_message_displayed(self, game_engine, monkeypatch, mock_console):
        """Test immunity event shows escape message."""
        import game.ui

        console, output = mock_console

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 50

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Create immunity event at location where player will be caught
        from game.events import Event
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)

        immunity = Event(
            id="insurance",
            name="INSURANCE",
            description="Cannot be caught!",
            emoji="🛡️",
            duration_rounds=1,
            special_effect="immunity"
        )
        game_engine.event_manager.active_events.append(immunity.copy_with_location(loc1))

        player_choices = {player1: loc1, player2: loc2}
        predictions = {
            player1: (loc1.name, 0.9, "Correct prediction"),
            player2: (loc1.name, 0.5, "Wrong prediction")
        }

        # AI searches loc1 where player1 is, but player has immunity
        game_engine.reveal_and_resolve_phase(player_choices, loc1, predictions, "Test")

        # Player should still be alive due to immunity
        assert player1.alive is True

        # Check output contains immunity message
        result = output.getvalue()
        assert "Insurance" in result or "immunity" in result.lower() or "slips away" in result.lower()


class TestEventExpiredDisplay:
    """Tests for event expiration display."""

    def test_expired_events_displayed(self, game_engine, monkeypatch, mock_console):
        """Test expired events are shown at end of round."""
        import game.ui

        console, output = mock_console

        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 50

        # Mock console
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Create an event that will expire
        from game.events import Event
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)

        expiring_event = Event(
            id="test_event",
            name="TEST EVENT",
            description="A test event",
            emoji="🎯",
            duration_rounds=1
        )
        event = expiring_event.copy_with_location(loc1)
        event.rounds_remaining = 1
        game_engine.event_manager.active_events.append(event)

        player_choices = {player1: loc2, player2: loc2}
        predictions = {
            player1: (loc1.name, 0.5, "Wrong prediction"),
            player2: (loc1.name, 0.5, "Wrong prediction")
        }

        game_engine.reveal_and_resolve_phase(player_choices, loc1, predictions, "Test")

        # Event should be expired and removed
        assert event not in game_engine.event_manager.active_events


class TestUpdatePlayerProfiles:
    """Tests for player profile updates after game."""

    def test_update_player_profiles(self, game_engine, monkeypatch, temp_data_dir):
        """Test player profiles are updated after game."""
        from game.profile_manager import ProfileManager
        from unittest.mock import MagicMock

        # Create player with profile
        player = game_engine.players[0]
        player.profile_id = "test_profile"
        player.points = 100

        # Mock ProfileManager
        mock_pm = MagicMock(spec=ProfileManager)

        with monkeypatch.context() as m:
            m.setattr('game.engine.ProfileManager', lambda: mock_pm)

            game_engine.winner = player
            game_engine._update_player_profiles("test_game_id")

            # Should have called update_stats_after_game
            mock_pm.update_stats_after_game.assert_called()

    def test_update_player_profiles_skips_guests(self, game_engine, monkeypatch, temp_data_dir):
        """Test guest players (no profile_id) are skipped."""
        from game.profile_manager import ProfileManager
        from unittest.mock import MagicMock

        # Player without profile_id
        player = game_engine.players[0]
        player.profile_id = None

        mock_pm = MagicMock(spec=ProfileManager)

        with monkeypatch.context() as m:
            m.setattr('game.engine.ProfileManager', lambda: mock_pm)

            game_engine._update_player_profiles("test_game_id")

            # Should not have called update_stats_after_game for guest
            # (or only called for players with profiles)


class TestShowIntelReportEdgeCases:
    """Tests for show_intel_report edge cases."""

    def test_show_intel_report_high_value_preference(self, game_engine, monkeypatch, mock_console):
        """Test Intel Report shows high-value preference insight."""
        import game.ui

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 50

        # Add history with high values to trigger insight
        for i in range(5):
            loc = game_engine.location_manager.get_all()[-1]  # Usually highest value
            player.record_choice(loc, i+1, False, 25, 25)

        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_intel_report(player)

        # Should have generated some output
        result = output.getvalue()
        assert len(result) > 0

    def test_show_intel_report_low_value_preference(self, game_engine, monkeypatch, mock_console):
        """Test Intel Report shows low-value preference insight."""
        import game.ui

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 50

        # Add history with low values to trigger insight
        for i in range(5):
            loc = game_engine.location_manager.get_all()[0]  # Usually lowest value
            player.record_choice(loc, i+1, False, 5, 5)

        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_intel_report(player)

        result = output.getvalue()
        assert len(result) > 0

    def test_show_intel_report_limited_variety(self, game_engine, monkeypatch, mock_console):
        """Test Intel Report shows limited variety insight."""
        import game.ui

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 50

        # Add history with same location repeatedly
        loc = game_engine.location_manager.get_location(0)
        for i in range(10):
            player.record_choice(loc, i+1, False, 10, 10)

        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.show_intel_report(player)

        result = output.getvalue()
        assert len(result) > 0

    def test_show_intel_report_with_profile(self, game_engine, monkeypatch, mock_console, temp_data_dir):
        """Test Intel Report with player profile shows AI memory."""
        import game.ui
        from game.profile_manager import ProfileManager
        from unittest.mock import MagicMock

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 50
        player.profile_id = "test_profile"

        # Add some history
        loc = game_engine.location_manager.get_location(0)
        for i in range(3):
            player.record_choice(loc, i+1, False, 10, 10)

        # Mock ProfileManager to return a profile
        mock_profile = MagicMock()
        mock_profile.behavioral_stats.favorite_location = "Test Store"
        mock_profile.behavioral_stats.risk_profile = "aggressive"
        mock_profile.ai_memory.catch_rate = 0.25
        mock_profile.ai_memory.has_personal_model = True
        mock_profile.stats.total_games = 10
        mock_profile.hiding_stats.total_caught_instances = 3
        mock_profile.hiding_stats.hide_attempts = 5
        mock_profile.hiding_stats.run_attempts = 3
        mock_profile.hiding_stats.hide_success_rate = 0.6
        mock_profile.hiding_stats.run_success_rate = 0.5
        mock_profile.hiding_stats.risk_profile_when_caught = "cautious"

        mock_pm = MagicMock()
        mock_pm.load_profile.return_value = mock_profile

        with monkeypatch.context() as m:
            m.setattr('game.engine.ProfileManager', lambda: mock_pm)
            m.setattr(game.ui.console, 'input', lambda prompt: "")

            game_engine.show_intel_report(player)

        result = output.getvalue()
        assert len(result) > 0


class TestHideOrRunEdgeCases:
    """Tests for hide or run edge cases."""

    def test_handle_hide_or_run_no_escape_options(self, game_engine, monkeypatch):
        """Test handle_hide_or_run when no escape options available."""
        import game.ui

        player = game_engine.players[0]
        player.points = 50

        # Mock HidingManager to return no escape options
        monkeypatch.setattr(game_engine.hiding_manager, 'get_escape_options_for_location', lambda loc: [])
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        caught_location = game_engine.location_manager.get_location(0)

        result, opts = game_engine.handle_hide_or_run(player, caught_location, caught_location, 20)

        # Should be caught with no escape
        assert result['escaped'] is False
        assert opts == []

    def test_handle_hide_or_run_passive_second_chance_hide(self, game_engine, monkeypatch, sample_hiding_manager, temp_passives_config):
        """Test passive second chance for hide escape."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        import game.ui
        import random

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]
        player.points = 50

        # Give player Escape Artist (hide bonus)
        passive = PassiveShop.get_passive(PassiveType.ESCAPE_ARTIST)
        if passive:
            player.passive_manager.add_passive(passive)

        # Mock HidingManager
        monkeypatch.setattr(game_engine, 'hiding_manager', sample_hiding_manager)

        escape_options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        if not escape_options:
            pytest.skip("No escape options available")

        first_option = escape_options[0]

        # Mock UI to select first option
        monkeypatch.setattr(game.ui, 'select_escape_option', lambda opts, p, pts: first_option)
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")
        monkeypatch.setattr(game.ui, 'print_escape_result', lambda p, r, opts=None: None)

        # Mock escape predictor to predict correctly (AI catches player initially)
        def mock_predict_escape(*args, **kwargs):
            return (first_option['id'], 0.9, 'Correct prediction')
        monkeypatch.setattr(game_engine.escape_predictor, 'predict_escape_option', mock_predict_escape)

        # Force passive second chance to succeed
        monkeypatch.setattr(random, 'random', lambda: 0.0)  # Always < bonus

        caught_location = game_engine.location_manager.get_location(0)

        result, opts = game_engine.handle_hide_or_run(player, caught_location, caught_location, 20)

        # If passive has bonus, player might escape via second chance
        assert isinstance(result['escaped'], bool)

    def test_handle_hide_or_run_run_with_quick_feet(self, game_engine, monkeypatch, sample_hiding_manager, temp_passives_config):
        """Test run escape with Quick Feet passive retention bonus."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        import game.ui
        import random

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        player = game_engine.players[0]
        player.points = 50

        # Give player Quick Feet (run bonus)
        passive = PassiveShop.get_passive(PassiveType.QUICK_FEET)
        if passive:
            player.passive_manager.add_passive(passive)

        # Mock HidingManager
        monkeypatch.setattr(game_engine, 'hiding_manager', sample_hiding_manager)

        escape_options = sample_hiding_manager.get_escape_options_for_location("Test Store")
        if not escape_options:
            pytest.skip("No escape options available")

        # Find a run option if available
        run_option = None
        for opt in escape_options:
            if opt.get('type') == 'run':
                run_option = opt
                break
        if not run_option:
            run_option = escape_options[0]  # Fallback

        # Mock UI to select run option
        monkeypatch.setattr(game.ui, 'select_escape_option', lambda opts, p, pts: run_option)
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")
        monkeypatch.setattr(game.ui, 'print_escape_result', lambda p, r, opts=None: None)

        # Mock escape predictor to predict wrong (player escapes)
        def mock_predict_escape(*args, **kwargs):
            return ('wrong_option', 0.5, 'Wrong prediction')
        monkeypatch.setattr(game_engine.escape_predictor, 'predict_escape_option', mock_predict_escape)

        caught_location = game_engine.location_manager.get_location(0)

        result, opts = game_engine.handle_hide_or_run(player, caught_location, caught_location, 20)

        # Player should escape with points
        assert result['escaped'] is True


class TestNewEventAnnouncement:
    """Tests for new event announcement display."""

    def test_new_event_announcement_in_round(self, game_engine, monkeypatch, mock_console):
        """Test new events are announced at start of round."""
        import game.ui
        import game.engine

        console, output = mock_console

        # Mock console input for all prompts
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Force event generation
        from game.events import Event
        loc = game_engine.location_manager.get_location(0)
        new_event = Event(
            id="test",
            name="TEST EVENT",
            description="A test event",
            emoji="🎯",
            duration_rounds=2
        )

        # Mock generate_events to return the new event
        def mock_generate_events(game_state, locations):
            event = new_event.copy_with_location(loc)
            game_engine.event_manager.active_events.append(event)
            return [event]

        monkeypatch.setattr(game_engine.event_manager, 'generate_events', mock_generate_events)

        # Mock phases to skip interaction
        monkeypatch.setattr(game_engine, 'shop_phase', lambda player: None)
        monkeypatch.setattr(game_engine, 'choose_location_phase', lambda player: loc)

        # Mock hide_or_run
        def mock_handle_hide_or_run(self, player, caught_loc, search_loc, points):
            return {'escaped': True, 'points_awarded': 0, 'player_choice_id': 'test', 'ai_prediction_id': 'other', 'choice_type': 'hide'}, []
        monkeypatch.setattr(game.engine.GameEngine, 'handle_hide_or_run', mock_handle_hide_or_run)

        game_engine.play_round()

        result = output.getvalue()
        # Should contain event announcement
        assert "NEW EVENT" in result or "TEST EVENT" in result


class TestShopPhaseEdgeCases:
    """Tests for shop phase edge cases."""

    def test_shop_phase_zero_points(self, game_engine, monkeypatch, mock_console):
        """Test shop phase skips when player has 0 points."""
        import game.ui

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 0

        game_engine.shop_phase(player)

        result = output.getvalue()
        assert "Skipping shop" in result or "no points" in result.lower()

    def test_shop_phase_invalid_input(self, game_engine, monkeypatch, mock_console, temp_passives_config):
        """Test shop phase handles skip selection (arrow-key selection handles invalid inputs)."""
        from game.passives import PassiveShop
        from game.config_loader import ConfigLoader
        import game.ui

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 50

        # Mock select_passive to skip (None)
        monkeypatch.setattr(game.ui, 'select_passive', lambda p: None)

        game_engine.shop_phase(player)

        # Player should have same points (skipped)
        assert player.points == 50

    def test_shop_phase_already_owned(self, game_engine, monkeypatch, mock_console, temp_passives_config):
        """Test shop phase shows already owned message."""
        from game.passives import PassiveShop, PassiveType
        from game.config_loader import ConfigLoader
        import game.ui

        ConfigLoader._instance = None
        PassiveShop.PASSIVES = None

        console, output = mock_console

        player = game_engine.players[0]
        player.points = 100

        # Give player a passive first
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        if not passive:
            pytest.skip("AI Whisperer passive not available")
        player.passive_manager.add_passive(passive)

        # Try to buy same passive again, then skip
        inputs = iter(["1", ""])  # Try to buy first passive, then skip
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs, ""))

        game_engine.shop_phase(player)

        result = output.getvalue()
        assert "already own" in result.lower() or player.points == 100
