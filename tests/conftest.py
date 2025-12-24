"""Shared test fixtures for LOOT RUN game tests."""
import json
import random
import tempfile
from pathlib import Path
from typing import Dict, List
from io import StringIO

import pytest
import numpy as np
from rich.console import Console

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
def mock_console(monkeypatch):
    """Mock Rich Console for UI tests."""
    output = StringIO()
    console = Console(file=output, force_terminal=False, width=80, legacy_windows=False)

    # Replace global console in ui module
    import game.ui as ui_module
    monkeypatch.setattr(ui_module, 'console', console)

    return console, output


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
