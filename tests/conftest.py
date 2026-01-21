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
from game.items import ItemShop, ItemType
from game.config_loader import ConfigLoader


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

    # Create test items.json
    items = {
        "items": [
            {
                "id": "intel_report",
                "name": "Intel Report",
                "cost": 10,
                "description": "See your AI threat level and predictability"
            },
            {
                "id": "scout",
                "name": "Scout",
                "cost": 6,
                "description": "Preview loot rolls before choosing (single use)"
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
    (config_dir / "items.json").write_text(json.dumps(items, indent=2))
    (config_dir / "game_settings.json").write_text(json.dumps(game_settings, indent=2))

    # Reset the singleton instance FIRST
    ConfigLoader._instance = None
    ItemShop.ITEMS = None

    # Patch the class-level _config_dir attribute
    monkeypatch.setattr(ConfigLoader, '_config_dir', str(config_dir))

    # Force reload by creating new instance
    from game import config_loader, locations, items
    new_config = ConfigLoader()
    monkeypatch.setattr(config_loader, 'config', new_config)

    # Also patch config in modules that import it
    monkeypatch.setattr(locations, 'config', new_config)
    monkeypatch.setattr(items, 'config', new_config)

    yield config_dir

    # Cleanup: reset singleton
    ConfigLoader._instance = None
    ItemShop.ITEMS = None


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
def sample_items(temp_config_dir):
    """Get sample items for testing."""
    return {
        'intel_report': ItemShop.get_item(ItemType.INTEL_REPORT),
        'scout': ItemShop.get_item(ItemType.SCOUT)
    }


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
