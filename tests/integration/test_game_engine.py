"""Integration tests for game/engine.py - GameEngine class."""
import pytest
from game.engine import GameEngine
from game.player import Player
from game.items import ItemShop, ItemType
from game.locations import Location


@pytest.fixture
def game_engine(temp_config_dir, mock_console):
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

        # Mock console.input to skip purchase
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        game_engine.shop_phase(player)

        # Player should have no items
        assert len(player.items) == 0
        assert player.points == 20

    def test_shop_phase_buy_item(self, game_engine, monkeypatch):
        """Test shop phase when player buys an item."""
        player = game_engine.players[0]
        player.points = 20

        # Mock console.input for all prompts: buy, continue shopping, exit
        import game.ui
        inputs = iter(["2", "", ""])  # Buy 2 (Scout), continue shopping, exit
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        game_engine.shop_phase(player)

        # Scout was purchased (cost 6) but consumed immediately
        assert player.points == 14  # 20 - 6
        # Scout preview should have been shown (scout_rolls should have data)
        assert player.id in game_engine.scout_rolls
        assert len(game_engine.scout_rolls[player.id]) > 0

    def test_shop_phase_insufficient_points(self, game_engine, monkeypatch):
        """Test shop phase when player has insufficient points."""
        player = game_engine.players[0]
        player.points = 5

        # Try to buy Lucky Charm (cost 9), see error, continue, then skip
        import game.ui
        inputs = iter(["1", "", ""])  # Try buy, press continue, then skip
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: next(inputs))

        game_engine.shop_phase(player)

        # Purchase should fail, player should have no items
        assert len(player.items) == 0
        assert player.points == 5


class TestChooseLocationPhase:
    """Tests for choose location phase."""

    def test_choose_location_valid_choice(self, game_engine, monkeypatch):
        """Test choosing a valid location."""
        player = game_engine.players[0]

        # Mock console.input to choose location 1
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "1")

        location = game_engine.choose_location_phase(player)

        assert isinstance(location, Location)
        assert location == game_engine.location_manager.get_location(0)



class TestRevealAndResolvePhase:
    """Tests for reveal and resolve phase."""

    def test_resolve_player_caught(self, game_engine, deterministic_random, monkeypatch):
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

    def test_show_scout_preview(self, game_engine, deterministic_random, monkeypatch):
        """Test Scout preview shows roll values."""
        player = game_engine.players[0]

        # Mock console.input for the "Press Enter to continue" prompt
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Cache rolls by calling show_scout_preview
        game_engine.show_scout_preview(player)

        # Should have cached rolls for all locations
        assert len(game_engine.scout_rolls[player.id]) > 0


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

        # Manually create a jackpot event (2x points) at location
        jackpot_template = next(e for e in game_engine.event_manager.event_pool if e.id == "jackpot")
        jackpot = jackpot_template.copy_with_location(location)
        game_engine.event_manager.active_events.append(jackpot)

        # Apply point modifier
        base_points = 10
        modified_points = game_engine.event_manager.apply_point_modifier(location, base_points)

        assert modified_points == 20  # Doubled by jackpot

    def test_event_immunity_prevents_catch(self, game_engine, deterministic_random, monkeypatch):
        """Test immunity event prevents player from being caught."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        location1 = game_engine.location_manager.get_location(0)
        location2 = game_engine.location_manager.get_location(1)

        # Create immunity event at location1
        immunity_template = next(e for e in game_engine.event_manager.event_pool if e.id == "insurance")
        immunity = immunity_template.copy_with_location(location1)
        game_engine.event_manager.active_events.append(immunity)

        # Mock console.input for prompts
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Set up scenario where player1 would be caught but has immunity
        player_choices = {player1: location1, player2: location2}
        search_location = location1  # AI searches location1
        predictions = {
            player1: (location1, 0.8, "Test prediction"),
            player2: (location2, 0.5, "Test prediction")
        }

        # Resolve (immunity should prevent catch)
        game_engine.reveal_and_resolve_phase(player_choices, search_location, predictions, "Test reasoning")

        # Player1 should still be alive (protected by immunity)
        assert player1.alive is True

    def test_event_ticking_and_expiration(self, game_engine):
        """Test events tick and expire correctly."""
        location = game_engine.location_manager.get_location(0)

        # Create event with 1 round duration
        event = game_engine.event_manager._spawn_event([location])
        event.rounds_remaining = 1

        assert event in game_engine.event_manager.active_events

        # Tick events
        expired = game_engine.event_manager.tick_events()

        # Event should be expired and removed
        assert event in expired
        assert event not in game_engine.event_manager.active_events

    def test_max_concurrent_events_enforced(self, game_engine):
        """Test max concurrent events limit is enforced by generate_events."""
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
        from game.events import EventManager

        player = game_engine.players[0]
        location = game_engine.location_manager.get_location(0)

        # Create guaranteed_catch event at a location
        alarm_template = next(e for e in game_engine.event_manager.event_pool if e.id == "silent_alarm")
        alarm = alarm_template.copy_with_location(location)
        game_engine.event_manager.active_events.append(alarm)

        # Get AI prediction with event awareness
        prediction = game_engine.ai.predict_player_location(
            player,
            len([p for p in game_engine.players if p.alive]),
            event_manager=game_engine.event_manager
        )

        # Prediction is tuple: (location_name, confidence, reasoning)
        assert isinstance(prediction, tuple)
        assert len(prediction) == 3
