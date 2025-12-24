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

        # Mock console.input for all prompts: buy, preview, continue from preview, continue shopping, exit
        import game.ui
        inputs = iter(["3", "", "", "", ""])  # Buy 3, see preview, continue, continue shopping, exit
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
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

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

    def test_resolve_with_lucky_charm(self, game_engine, deterministic_random, monkeypatch):
        """Test resolving when player has Lucky Charm."""
        player1 = game_engine.players[0]
        player2 = game_engine.players[1]
        player1.points = 50
        player2.points = 30
        player1.items.append(ItemShop.get_item(ItemType.LUCKY_CHARM))

        # Mock console.input for "Press Enter to continue" prompt
        import game.ui
        monkeypatch.setattr(game.ui.console, 'input', lambda prompt: "")

        # Create choice where AI searches different location
        loc1 = game_engine.location_manager.get_location(0)
        loc2 = game_engine.location_manager.get_location(1)
        loc3 = game_engine.location_manager.get_location(2)
        player_choices = {player1: loc1, player2: loc2}

        # Mock predictions for both players
        predictions = {
            player1: (loc2, 0.6, "AI predicted wrong location"),
            player2: (loc3, 0.5, "AI predicted wrong location")
        }

        initial_points = player1.points
        game_engine.reveal_and_resolve_phase(player_choices, loc3, predictions, "AI reasoning")

        # Player should gain points with 1.15x multiplier
        points_gained = player1.points - initial_points
        assert points_gained > 0


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
