"""Configuration loader for game settings."""
import json
import os
import sys
from typing import Dict, Any


def _get_base_path() -> str:
    """Get the base path for the application.

    When running from PyInstaller bundle, returns the path where files are extracted.
    When running from source, returns the project root directory.
    """
    if getattr(sys, 'frozen', False):
        # Running from PyInstaller bundle - use the bundle's base path
        return sys._MEIPASS
    else:
        # Running from source - config is relative to this file's parent directory
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ConfigLoader:
    """Loads and provides access to game configuration."""

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one config loader."""
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load_all_configs()
        return cls._instance

    def _load_all_configs(self):
        """Load all configuration files."""
        self._config_dir = os.path.join(_get_base_path(), "config")
        self.game_settings = self._load_json("game_settings.json")
        self.locations_config = self._load_json("locations.json")
        self.hiding_config = self._load_json("hiding.json")
        self.events_config = self._load_json("events.json")
        self.passives_config = self._load_json("passives.json")

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

    def get_hiding_mechanics(self):
        """Get hiding mechanics configuration."""
        return self.hiding_config.get('mechanics', {})

    def get_hiding_spots(self):
        """Get hiding location spots configuration (backward compatibility)."""
        # First try new format, then fall back to old format
        options = self.hiding_config.get('location_escape_options', {})
        if options:
            # Filter to only hide type options
            return {
                loc: [opt for opt in opts if opt.get('type', 'hide') == 'hide']
                for loc, opts in options.items()
            }
        return self.hiding_config.get('location_hiding_spots', {})

    def get_escape_options(self):
        """Get all escape options (hiding spots + escape routes) by location."""
        return self.hiding_config.get('location_escape_options', {})

    def get_events_settings(self):
        """Get events settings configuration."""
        return self.events_config.get('settings', {})

    def get_events_list(self):
        """Get events list configuration."""
        return self.events_config.get('events', [])

    def get_passives(self):
        """Get passives configuration."""
        return self.passives_config.get('passives', [])

    def get_passives_settings(self):
        """Get passives settings configuration."""
        return self.passives_config.get('settings', {})


# Global config instance
config = ConfigLoader()
