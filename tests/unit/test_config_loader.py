"""Unit tests for game/config_loader.py - ConfigLoader class."""
import pytest
import json
from game.config_loader import ConfigLoader


class TestConfigLoaderSingleton:
    """Tests for ConfigLoader singleton pattern."""

    def test_singleton_returns_same_instance(self, temp_config_dir):
        """Test ConfigLoader returns the same instance."""
        # Reset singleton
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config1 = ConfigLoader()
        config2 = ConfigLoader()

        assert config1 is config2

    def test_singleton_persists_data(self, temp_config_dir):
        """Test singleton preserves loaded data."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config1 = ConfigLoader()
        data1 = config1.game_settings

        config2 = ConfigLoader()
        data2 = config2.game_settings

        assert data1 is data2


class TestConfigLoading:
    """Tests for configuration file loading."""

    def test_loads_valid_json(self, temp_config_dir):
        """Test loading valid JSON configuration."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        assert config.game_settings is not None
        assert config.locations_config is not None
        assert config.passives_config is not None

    def test_missing_file_returns_empty_dict(self, temp_config_dir, capsys):
        """Test missing config file returns empty dict with warning."""
        # Remove one config file (locations.json is created by temp_config_dir)
        (temp_config_dir / "locations.json").unlink()

        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        assert config.locations_config == {}

        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "locations.json" in captured.out

    def test_invalid_json_returns_empty_dict(self, temp_config_dir, capsys):
        """Test invalid JSON returns empty dict with warning."""
        # Write invalid JSON
        (temp_config_dir / "game_settings.json").write_text("{invalid json")

        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        assert config.game_settings == {}

        # Check warning was printed
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "game_settings.json" in captured.out

    def test_utf8_encoding(self, temp_config_dir):
        """Test UTF-8 encoding for emoji support."""
        # Write config with emoji
        emoji_config = {
            "test": {
                "emoji": "🏪🔫💰"
            }
        }
        (temp_config_dir / "game_settings.json").write_text(
            json.dumps(emoji_config),
            encoding='utf-8'
        )

        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        assert config.game_settings['test']['emoji'] == "🏪🔫💰"


class TestGetMethod:
    """Tests for get() method."""

    def test_get_nested_value(self, temp_config_dir):
        """Test getting nested configuration value."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        # Get nested value from test config (win_threshold is in game_settings)
        value = config.get('game', 'win_threshold')
        assert value == 100

    def test_get_with_default(self, temp_config_dir):
        """Test get() returns default when key doesn't exist."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        value = config.get('nonexistent', 'key', default=42)
        assert value == 42

    def test_get_partial_path(self, temp_config_dir):
        """Test get() returns dict for partial path."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        value = config.get('game')
        assert isinstance(value, dict)
        assert 'win_threshold' in value

    def test_get_single_key(self, temp_config_dir):
        """Test get() with single key."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        value = config.get('game')
        assert isinstance(value, dict)


class TestGetLocationsAndPassives:
    """Tests for get_locations() and get_passives() methods."""

    def test_get_locations_returns_list(self, temp_config_dir):
        """Test get_locations() returns location list."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        locations = config.get_locations()
        assert isinstance(locations, list)
        assert len(locations) == 3  # Test config has 3 locations

    def test_get_passives_returns_list(self, temp_config_dir):
        """Test get_passives() returns passives list."""
        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        passives = config.get_passives()
        assert isinstance(passives, list)

    def test_get_locations_empty_on_missing_key(self, temp_config_dir):
        """Test get_locations() returns empty list when 'locations' key missing."""
        # Write config without 'locations' key
        (temp_config_dir / "locations.json").write_text(json.dumps({}))

        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        locations = config.get_locations()
        assert locations == []

    def test_get_passives_empty_on_missing_key(self, temp_config_dir):
        """Test get_passives() returns empty list when 'passives' key missing."""
        # Write config without 'passives' key
        (temp_config_dir / "passives.json").write_text(json.dumps({}))

        ConfigLoader._instance = None
        ConfigLoader._config_dir = str(temp_config_dir)

        config = ConfigLoader()

        passives = config.get_passives()
        assert passives == []
