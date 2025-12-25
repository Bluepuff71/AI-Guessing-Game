"""Configuration loader for game settings."""
import json
import os
from typing import Dict, Any


class ConfigLoader:
    """Loads and provides access to game configuration."""

    _instance = None
    _config_dir = "config"

    def __new__(cls):
        """Singleton pattern to ensure only one config loader."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load_all_configs()
        return cls._instance

    def _load_all_configs(self):
        """Load all configuration files."""
        self.game_settings = self._load_json("game_settings.json")
        self.locations_config = self._load_json("locations.json")
        self.items_config = self._load_json("items.json")
        self.hiding_config = self._load_json("hiding.json")
        self.events_config = self._load_json("events.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Load a JSON configuration file."""
        filepath = os.path.join(self._config_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file {filename} not found. Using defaults.")
            return {}
        except json.JSONDecodeError as e:
            print(f"Warning: Error parsing {filename}: {e}. Using defaults.")
            return {}

    def get(self, *keys, default=None):
        """Get a nested configuration value."""
        value = self.game_settings
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def get_locations(self):
        """Get locations configuration."""
        return self.locations_config.get('locations', [])

    def get_items(self):
        """Get items configuration."""
        return self.items_config.get('items', [])

    def get_hiding_mechanics(self):
        """Get hiding mechanics configuration."""
        return self.hiding_config.get('mechanics', {})

    def get_hiding_spots(self):
        """Get hiding location spots configuration."""
        return self.hiding_config.get('location_hiding_spots', {})

    def get_events_settings(self):
        """Get events settings configuration."""
        return self.events_config.get('settings', {})

    def get_events_list(self):
        """Get events list configuration."""
        return self.events_config.get('events', [])


# Global config instance
config = ConfigLoader()
