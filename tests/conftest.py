"""Shared test fixtures for LOOT RUN game tests."""
import json
import random
import tempfile
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock

import pytest
import numpy as np

from game.player import Player
from game.locations import LocationManager, Location
from game.config_loader import ConfigLoader
from game import config_loader


@pytest.fixture(autouse=True)
def deterministic_random():
    """Seed random for reproducible tests."""
    random.seed(42)
    np.random.seed(42)
    yield
    # Reset after test (optional, but good practice)
    random.seed()


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create temporary config directory with test JSON files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create test locations.json
    locations = {
        "locations": [
            {
                "name": "Test Store",
                "emoji": "🏪",
                "min_points": 5,
                "max_points": 10
            },
            {
                "name": "Test Vault",
                "emoji": "💰",
                "min_points": 10,
                "max_points": 20
            },
            {
                "name": "Test Bank",
                "emoji": "🏦",
                "min_points": 1,
                "max_points": 30
            }
        ]
    }

    # Create test game_settings.json
    game_settings = {
        "game": {
            "win_threshold": 100,
            "min_players": 2,
            "max_players": 6
        },
        "ai": {
            "early_game_rounds": 3,
            "mid_game_rounds": 6
        }
    }

    # Write files
    (config_dir / "locations.json").write_text(json.dumps(locations, indent=2))
    (config_dir / "game_settings.json").write_text(json.dumps(game_settings, indent=2))

    # Reset the singleton instance FIRST
    ConfigLoader._instance = None

    # Patch _get_base_path to return tmp_path (parent of config_dir)
    monkeypatch.setattr(config_loader, '_get_base_path', lambda: str(tmp_path))

    # Force reload by creating new instance
    from game import locations as locations_module
    new_config = ConfigLoader()
    monkeypatch.setattr(config_loader, 'config', new_config)

    # Also patch config in modules that import it
    monkeypatch.setattr(locations_module, 'config', new_config)

    yield config_dir

    # Cleanup: reset singleton
    ConfigLoader._instance = None


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Create temporary data directory for game history and ML models."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create empty game_history.json
    (data_dir / "game_history.json").write_text(json.dumps({"games": []}, indent=2))

    # Monkey-patch data directory paths
    import ai.trainer as trainer_module
    monkeypatch.setattr(trainer_module, 'ModelTrainer',
                       lambda: trainer_module.ModelTrainer(str(data_dir)))

    yield data_dir


@pytest.fixture
def sample_player_factory(temp_config_dir):
    """Factory fixture to create players with configurable history."""
    def _create_player(
        player_id: int = 1,
        name: str = "Test Player",
        points: int = 0,
        items: List = None,
        choice_history: List[str] = None
    ) -> Player:
        player = Player(player_id, name)
        player.points = points

        if items:
            player.items = items

        if choice_history:
            loc_manager = LocationManager()
            for i, loc_name in enumerate(choice_history):
                try:
                    loc = loc_manager.get_location_by_name(loc_name)
                except ValueError:
                    # Fallback to first location if name not found
                    loc = loc_manager.get_location(0)
                player.record_choice(loc, i+1, caught=False, points_earned=10)

        return player

    return _create_player


@pytest.fixture
def sample_location_manager(temp_config_dir):
    """Pre-configured LocationManager using test config."""
    return LocationManager()


@pytest.fixture
def mock_ml_model(monkeypatch):
    """Mock LightGBM model for deterministic predictions."""
    class MockBooster:
        """Mock LightGBM Booster for testing."""

        def __init__(self):
            self.num_classes = 5  # 5 locations in production

        def predict(self, X):
            """Return uniform probabilities for simplicity."""
            if len(X.shape) == 1:
                num_samples = 1
            else:
                num_samples = X.shape[0]
            # Return uniform probabilities
            return np.ones((num_samples, self.num_classes)) / self.num_classes

        def feature_importance(self, importance_type='gain'):
            """Return mock feature importance."""
            return np.array([100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 5, 2])

    def mock_train(*args, **kwargs):
        """Mock LightGBM training function."""
        return MockBooster()

    # Patch lightgbm.train
    try:
        import lightgbm as lgb
        monkeypatch.setattr(lgb, 'train', mock_train)
    except ImportError:
        # LightGBM not installed in test environment
        pass

    return MockBooster()


@pytest.fixture
def temp_events_config(temp_config_dir):
    """Create test events.json config file."""
    events = {
        "settings": {
            "min_spawn_interval": 2,
            "max_spawn_interval": 4,
            "base_spawn_chance": 0.3,
            "max_concurrent_events": 2
        },
        "events": [
            {
                "id": "jackpot",
                "name": "JACKPOT",
                "description": "Double points at this location!",
                "emoji": "💰",
                "duration_rounds": 1,
                "point_modifier": {"type": "multiply", "value": 2.0},
                "spawn_weight": 1.0
            },
            {
                "id": "clearance_sale",
                "name": "CLEARANCE",
                "description": "+50% points at this location!",
                "emoji": "🏷️",
                "duration_rounds": 2,
                "point_modifier": {"type": "multiply", "value": 1.5},
                "spawn_weight": 1.5
            },
            {
                "id": "lockdown",
                "name": "LOCKDOWN",
                "description": "-30% points, tighter security",
                "emoji": "🔒",
                "duration_rounds": 1,
                "point_modifier": {"type": "multiply", "value": 0.7},
                "spawn_weight": 1.0
            },
            {
                "id": "bonus_stash",
                "name": "BONUS STASH",
                "description": "+20 bonus points!",
                "emoji": "🎁",
                "duration_rounds": 1,
                "point_modifier": {"type": "add", "value": 20},
                "spawn_weight": 0.8
            },
            {
                "id": "immunity",
                "name": "IMMUNITY",
                "description": "Cannot be caught here!",
                "emoji": "🛡️",
                "duration_rounds": 1,
                "point_modifier": {"type": "multiply", "value": 1.0},
                "special_effect": "immunity",
                "spawn_weight": 0.5
            }
        ]
    }
    (temp_config_dir / "events.json").write_text(json.dumps(events, indent=2))
    return events


@pytest.fixture
def temp_passives_config(temp_config_dir):
    """Create test passives.json config file."""
    passives = {
        "passives": [
            {
                "id": "ai_whisperer",
                "name": "AI Whisperer",
                "cost": 15,
                "description": "See detailed AI threat analysis",
                "emoji": "🔮",
                "category": "intel",
                "effects": {"intel_detail_level": "full"}
            },
            {
                "id": "inside_knowledge",
                "name": "Inside Knowledge",
                "cost": 10,
                "description": "See point tier hints before choosing",
                "emoji": "📊",
                "category": "intel",
                "effects": {"show_point_hints": True}
            },
            {
                "id": "escape_artist",
                "name": "Escape Artist",
                "cost": 12,
                "description": "+15% to hide and run",
                "emoji": "🎭",
                "category": "escape",
                "effects": {"hide_bonus": 0.15, "run_bonus": 0.15}
            },
            {
                "id": "quick_feet",
                "name": "Quick Feet",
                "cost": 12,
                "description": "+25% run success, 95% point retention",
                "emoji": "👟",
                "category": "escape",
                "effects": {"run_bonus": 0.25, "run_retention": 0.95}
            },
            {
                "id": "high_roller",
                "name": "High Roller",
                "cost": 8,
                "description": "+15% points at Casino/Bank, 20% bust chance",
                "emoji": "🎲",
                "category": "risk",
                "effects": {
                    "bonus_locations": ["Test Vault", "Test Bank"],
                    "point_bonus": 0.15,
                    "bust_chance": 0.20
                }
            }
        ],
        "settings": {"default_intel_level": "simple"}
    }
    (temp_config_dir / "passives.json").write_text(json.dumps(passives, indent=2))

    # Reset PassiveShop singleton
    from game.passives import PassiveShop
    PassiveShop.PASSIVES = None

    return passives


@pytest.fixture
def temp_hiding_config(temp_config_dir):
    """Create test hiding.json config file."""
    hiding = {
        "mechanics": {"run_point_retention": 0.8},
        "location_escape_options": {
            "Test Store": [
                {"id": "store_stockroom", "name": "Behind Boxes", "description": "Hide behind boxes", "emoji": "📦", "type": "hide"},
                {"id": "store_freezer", "name": "Walk-in Freezer", "description": "Cold storage", "emoji": "❄️", "type": "hide"},
                {"id": "store_backdoor", "name": "Back Exit", "description": "Sprint out", "emoji": "🚪", "type": "run"},
                {"id": "store_window", "name": "Window Dash", "description": "Dive through window", "emoji": "🪟", "type": "run"}
            ],
            "Test Vault": [
                {"id": "vault_safe", "name": "Safe Room", "description": "Hide in vault", "emoji": "🔒", "type": "hide"},
                {"id": "vault_exit", "name": "Emergency Exit", "description": "Run to exit", "emoji": "🏃", "type": "run"}
            ],
            "Test Bank": [
                {"id": "bank_vault", "name": "Main Vault", "description": "Hide in vault", "emoji": "🏦", "type": "hide"},
                {"id": "bank_lobby", "name": "Lobby Sprint", "description": "Run through lobby", "emoji": "🏛️", "type": "run"}
            ]
        }
    }
    (temp_config_dir / "hiding.json").write_text(json.dumps(hiding, indent=2))
    return hiding


@pytest.fixture
def sample_passive_manager(temp_config_dir, temp_passives_config, monkeypatch):
    """Pre-configured PassiveManager with test passives."""
    from game.passives import PassiveManager, PassiveShop
    from game.config_loader import ConfigLoader

    # Reload config to pick up passives
    ConfigLoader._instance = None
    new_config = ConfigLoader()

    from game import config_loader
    monkeypatch.setattr(config_loader, 'config', new_config)

    PassiveShop.PASSIVES = None

    manager = PassiveManager()
    return manager


@pytest.fixture
def sample_hiding_manager(temp_config_dir, temp_hiding_config, monkeypatch):
    """Pre-configured HidingManager with test escape options."""
    from game.config_loader import ConfigLoader
    import game.hiding as hiding_module

    # Reload config to pick up hiding
    ConfigLoader._instance = None
    new_config = ConfigLoader()

    from game import config_loader
    monkeypatch.setattr(config_loader, 'config', new_config)
    # Also patch the config in the hiding module since it imports at module level
    monkeypatch.setattr(hiding_module, 'config', new_config)

    from game.hiding import HidingManager
    return HidingManager()


@pytest.fixture
def sample_escape_predictor():
    """EscapePredictor for testing."""
    from ai.escape_predictor import EscapePredictor
    return EscapePredictor()


@pytest.fixture
def sample_event_manager(temp_config_dir, temp_events_config, monkeypatch):
    """Pre-configured EventManager with test events."""
    from game.config_loader import ConfigLoader

    # Reload config to pick up events (events imports config locally inside functions)
    ConfigLoader._instance = None
    new_config = ConfigLoader()

    from game import config_loader
    monkeypatch.setattr(config_loader, 'config', new_config)

    from game.events import EventManager
    return EventManager()


@pytest.fixture
def temp_profile_with_games(tmp_path, monkeypatch):
    """Create a temporary profile with game history for PlayerPredictor testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create profiles directory
    profiles_dir = data_dir / "profiles"
    profiles_dir.mkdir()

    # Create game history with test data
    game_history = {
        "games": [
            {
                "game_id": f"test_game_{i}",
                "timestamp": f"2024-01-0{i+1}T12:00:00Z",
                "players": [
                    {
                        "name": "Test Player",
                        "profile_id": "test_profile_123",
                        "final_score": 50 + i * 10,
                        "num_players_alive": 2,
                        "round_history": [
                            {"round": 1, "location": "Corner Store", "points_before": 0, "points_earned": 10, "caught": False, "location_value": 10, "items_held": []},
                            {"round": 2, "location": "Pawn Shop", "points_before": 10, "points_earned": 15, "caught": False, "location_value": 15, "items_held": []},
                            {"round": 3, "location": "Corner Store", "points_before": 25, "points_earned": 8, "caught": True, "location_value": 8, "items_held": []}
                        ]
                    }
                ]
            }
            for i in range(6)  # Create 6 games
        ]
    }

    (data_dir / "game_history.json").write_text(json.dumps(game_history, indent=2))

    return {
        "data_dir": str(data_dir),
        "profile_id": "test_profile_123",
        "games": game_history["games"]
    }


@pytest.fixture
def mock_questionary(monkeypatch):
    """Mock questionary.select for testing arrow-key selection functions.

    Returns a function that can be called to set the return value for the next select call.
    Usage:
        mock_questionary(return_value)  # Sets what select will return
    """
    return_values = []

    class MockQuestion:
        """Mock questionary Question object."""
        def __init__(self, value):
            self.value = value

        def ask(self):
            return self.value

    def mock_select(*args, **kwargs):
        """Return a MockQuestion that returns the configured value."""
        if return_values:
            return MockQuestion(return_values.pop(0))
        return MockQuestion(None)

    import questionary
    monkeypatch.setattr(questionary, 'select', mock_select)

    def set_return_value(value):
        """Set the return value for the next select call."""
        return_values.append(value)

    return set_return_value


# ============================================================================
# UI Testing Fixtures
# ============================================================================


@pytest.fixture
def mock_ui_inputs(monkeypatch):
    """Fixture to script questionary inputs for UI testing.

    Usage:
        def test_something(mock_ui_inputs):
            mock_ui_inputs(["option1", "option2", "text input"])
            # Now questionary.select() and questionary.text() will return
            # these values in sequence

    Returns:
        A function that accepts a list of responses to script.
    """
    responses = []
    call_index = [0]

    def scripted_select(*args, **kwargs):
        mock = MagicMock()
        if call_index[0] < len(responses):
            mock.ask.return_value = responses[call_index[0]]
            call_index[0] += 1
        else:
            mock.ask.return_value = None
        return mock

    monkeypatch.setattr("questionary.select", scripted_select)
    monkeypatch.setattr("questionary.text", scripted_select)

    def set_responses(resp_list):
        """Set the sequence of responses for questionary calls."""
        responses.clear()
        responses.extend(resp_list)
        call_index[0] = 0

    return set_responses


@pytest.fixture
def mock_network(monkeypatch):
    """Mock NetworkThread with scripted poll responses.

    Usage:
        def test_something(mock_network):
            net = mock_network([
                {"type": "CONNECTED"},
                {"type": "SERVER_MESSAGE", "message_type": "GAME_STATE", "data": {...}},
            ])
            # net.poll() will return these messages in sequence
            # net.start() and net.stop() are no-ops
            # net.send() records all sent messages in net.sent_messages

    Returns:
        A function that accepts a list of poll responses and returns a mock NetworkThread.
    """
    def create_mock_network(poll_responses=None):
        """Create a mock NetworkThread with the given poll responses."""
        if poll_responses is None:
            poll_responses = []

        mock_net = MagicMock()
        poll_index = [0]
        mock_net.sent_messages = []
        mock_net._is_running = False

        def mock_poll(timeout=0.1):
            if poll_index[0] < len(poll_responses):
                msg = poll_responses[poll_index[0]]
                poll_index[0] += 1
                return msg
            return None

        def mock_send(message_type, data):
            mock_net.sent_messages.append({
                "message_type": message_type,
                "data": data
            })

        def mock_start(url):
            mock_net._is_running = True
            return True

        def mock_stop():
            mock_net._is_running = False

        mock_net.poll = mock_poll
        mock_net.send = mock_send
        mock_net.start = mock_start
        mock_net.stop = mock_stop
        mock_net.is_running = property(lambda self: mock_net._is_running)

        # Add method to add more responses dynamically
        def add_responses(new_responses):
            poll_responses.extend(new_responses)

        mock_net.add_responses = add_responses

        return mock_net

    return create_mock_network


@pytest.fixture
def mock_game_state():
    """Factory to create GameState with configurable players, locations, and phases.

    Usage:
        def test_something(mock_game_state):
            state = mock_game_state(
                phase=ClientPhase.CHOOSING,
                players=[
                    {"username": "Alice", "points": 50},
                    {"username": "Bob", "points": 30},
                ],
                locations=[
                    {"name": "Store", "emoji": "🏪", "min_points": 5, "max_points": 10},
                ],
                round_num=3
            )

    Returns:
        A factory function that creates configured GameState instances.
    """
    from client.state import GameState, PlayerInfo, LocationInfo, ClientPhase

    def create_game_state(
        phase: ClientPhase = ClientPhase.MAIN_MENU,
        connected: bool = True,
        player_id: str = "player_1",
        game_id: str = "test_game",
        round_num: int = 1,
        players: List[Dict] = None,
        locations: List[Dict] = None,
        active_events: List[Dict] = None,
        local_player_ids: List[str] = None,
        timer_seconds: int = 30,
        previous_ai_location: str = None,
        available_passives: List[Dict] = None,
        escape_options: List[Dict] = None,
        caught_location: str = None,
        caught_points: int = 0,
    ) -> GameState:
        """Create a GameState with the specified configuration."""
        state = GameState()
        state.connected = connected
        state.player_id = player_id
        state.game_id = game_id
        state.phase = phase
        state.round_num = round_num
        state.timer_seconds = timer_seconds
        state.previous_ai_location = previous_ai_location
        state.caught_location = caught_location
        state.caught_points = caught_points

        # Add players
        if players:
            for i, p in enumerate(players):
                pid = p.get("player_id", f"player_{i + 1}")
                info = PlayerInfo(
                    player_id=pid,
                    username=p.get("username", f"Player {i + 1}"),
                    points=p.get("points", 0),
                    alive=p.get("alive", True),
                    connected=p.get("connected", True),
                    ready=p.get("ready", False),
                    passives=p.get("passives", []),
                    color=p.get("color", "white"),
                    is_local=p.get("is_local", False),
                )
                state.players[pid] = info

        # Add locations
        if locations:
            for loc in locations:
                info = LocationInfo(
                    name=loc.get("name", "Unknown"),
                    emoji=loc.get("emoji", "?"),
                    min_points=loc.get("min_points", 1),
                    max_points=loc.get("max_points", 10),
                    event=loc.get("event"),
                )
                state.locations.append(info)

        # Set local player IDs
        if local_player_ids:
            state.local_player_ids = local_player_ids
        elif players:
            # Default: first player is local
            state.local_player_ids = [list(state.players.keys())[0]]

        # Set active events
        if active_events:
            state.active_events = active_events

        # Set available passives
        if available_passives:
            state.available_passives = available_passives

        # Set escape options
        if escape_options:
            state.escape_options = escape_options

        return state

    return create_game_state


@pytest.fixture
def mock_console(monkeypatch):
    """Mock rich console for output verification.

    Usage:
        def test_something(mock_console):
            mock_console.install()
            # ... code that prints to console ...
            assert "expected text" in mock_console.output
            mock_console.clear()

    Returns:
        A mock console object with output capturing.
    """
    from io import StringIO

    class MockConsole:
        """Mock console that captures output for verification."""

        def __init__(self):
            self._output = StringIO()
            self._original_console = None
            self._installed = False
            self.print_calls = []
            self.clear_calls = 0
            self.input_responses = []
            self._input_index = 0

        @property
        def output(self) -> str:
            """Get all captured output as a string."""
            return self._output.getvalue()

        def install(self):
            """Install the mock console into client.ui module."""
            if self._installed:
                return

            import client.ui as ui_module

            # Save original console
            self._original_console = ui_module.console

            # Create mock methods
            mock = MagicMock()

            def mock_print(*args, **kwargs):
                # Convert args to string and store
                text = " ".join(str(a) for a in args)
                self._output.write(text + "\n")
                self.print_calls.append({"args": args, "kwargs": kwargs})

            def mock_clear():
                self.clear_calls += 1

            def mock_input(prompt=""):
                self._output.write(prompt)
                if self._input_index < len(self.input_responses):
                    response = self.input_responses[self._input_index]
                    self._input_index += 1
                    return response
                return ""

            mock.print = mock_print
            mock.clear = mock_clear
            mock.input = mock_input

            # Patch the console in ui module
            monkeypatch.setattr(ui_module, "console", mock)
            self._installed = True

        def clear(self):
            """Clear captured output."""
            self._output = StringIO()
            self.print_calls = []
            self.clear_calls = 0

        def set_input_responses(self, responses: List[str]):
            """Set responses for console.input() calls."""
            self.input_responses = responses
            self._input_index = 0

    return MockConsole()
