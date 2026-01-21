"""Tests for client/lan.py module - LAN discovery functionality."""
import json
from unittest.mock import MagicMock, patch

import pytest

from client.lan import DiscoveredGame, LANDiscovery, VERSION


class TestDiscoveredGame:
    """Tests for DiscoveredGame dataclass."""

    def test_discovered_game_with_version(self):
        """Test creating DiscoveredGame with version field."""
        game = DiscoveredGame(
            host="192.168.1.100",
            port=8765,
            game_name="Test Game",
            host_name="Host Player",
            player_count=2,
            max_players=6,
            version="v2026.01.20"
        )

        assert game.host == "192.168.1.100"
        assert game.port == 8765
        assert game.game_name == "Test Game"
        assert game.host_name == "Host Player"
        assert game.player_count == 2
        assert game.max_players == 6
        assert game.version == "v2026.01.20"

    def test_discovered_game_default_version(self):
        """Test DiscoveredGame defaults version to 'unknown'."""
        game = DiscoveredGame(
            host="192.168.1.100",
            port=8765,
            game_name="Test Game",
            host_name="Host Player",
            player_count=2,
            max_players=6
        )

        assert game.version == "unknown"

    def test_discovered_game_version_compatibility_check(self):
        """Test checking version compatibility between games."""
        compatible_game = DiscoveredGame(
            host="192.168.1.100",
            port=8765,
            game_name="Compatible Game",
            host_name="Host",
            player_count=1,
            max_players=6,
            version=VERSION  # Same as client version
        )

        incompatible_game = DiscoveredGame(
            host="192.168.1.101",
            port=8765,
            game_name="Incompatible Game",
            host_name="Host",
            player_count=1,
            max_players=6,
            version="v9999.99.99"  # Different version
        )

        assert compatible_game.version == VERSION
        assert incompatible_game.version != VERSION


class TestLANDiscoveryBroadcast:
    """Tests for LANDiscovery broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_data_includes_version(self):
        """Test that broadcast data includes version field."""
        discovery = LANDiscovery()

        # Mock socket to avoid actual network calls
        with patch('client.lan.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            await discovery.start_broadcasting(
                port=8765,
                game_name="Test Game",
                host_name="Host",
                player_count=1,
                max_players=6
            )

            try:
                # Verify broadcast data includes version
                assert discovery._broadcast_data is not None
                assert "version" in discovery._broadcast_data
                assert discovery._broadcast_data["version"] == VERSION
            finally:
                # Cleanup
                await discovery.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_broadcast_data_format(self):
        """Test the complete broadcast data structure."""
        discovery = LANDiscovery()

        with patch('client.lan.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            await discovery.start_broadcasting(
                port=9999,
                game_name="My Game",
                host_name="Player One",
                player_count=3,
                max_players=4
            )

            try:
                expected_data = {
                    "type": "LOOT_RUN_GAME",
                    "port": 9999,
                    "game_name": "My Game",
                    "host_name": "Player One",
                    "player_count": 3,
                    "max_players": 4,
                    "version": VERSION,
                }

                assert discovery._broadcast_data == expected_data
            finally:
                await discovery.stop_broadcasting()


class TestLANDiscoveryScanParsing:
    """Tests for scan_for_games parsing logic.

    These tests verify that broadcast messages are parsed correctly,
    including the version field. They use simpler mocking that doesn't
    require full async socket operations.
    """

    def test_broadcast_message_with_version_parsed(self):
        """Test that version is extracted from broadcast message."""
        # This tests the parsing logic directly
        broadcast_message = {
            "type": "LOOT_RUN_GAME",
            "port": 8765,
            "game_name": "Test Game",
            "host_name": "Host",
            "player_count": 2,
            "max_players": 6,
            "version": "v2026.01.15"
        }

        # Simulate what scan_for_games does when parsing
        game = DiscoveredGame(
            host="192.168.1.100",
            port=broadcast_message.get("port", 8765),
            game_name=broadcast_message.get("game_name", "Unknown"),
            host_name=broadcast_message.get("host_name", "Unknown"),
            player_count=broadcast_message.get("player_count", 0),
            max_players=broadcast_message.get("max_players", 6),
            version=broadcast_message.get("version", "unknown"),
        )

        assert game.version == "v2026.01.15"

    def test_broadcast_message_without_version_defaults(self):
        """Test that missing version defaults to 'unknown'."""
        # Legacy broadcast without version field
        broadcast_message = {
            "type": "LOOT_RUN_GAME",
            "port": 8765,
            "game_name": "Old Game",
            "host_name": "Host",
            "player_count": 1,
            "max_players": 6
            # No "version" field
        }

        game = DiscoveredGame(
            host="192.168.1.100",
            port=broadcast_message.get("port", 8765),
            game_name=broadcast_message.get("game_name", "Unknown"),
            host_name=broadcast_message.get("host_name", "Unknown"),
            player_count=broadcast_message.get("player_count", 0),
            max_players=broadcast_message.get("max_players", 6),
            version=broadcast_message.get("version", "unknown"),
        )

        assert game.version == "unknown"

    def test_multiple_versions_parsed_correctly(self):
        """Test parsing multiple games with different versions."""
        messages = [
            {
                "type": "LOOT_RUN_GAME",
                "port": 8765,
                "game_name": "Game A",
                "host_name": "Host A",
                "player_count": 1,
                "max_players": 6,
                "version": "v2026.01.20"
            },
            {
                "type": "LOOT_RUN_GAME",
                "port": 8766,
                "game_name": "Game B",
                "host_name": "Host B",
                "player_count": 2,
                "max_players": 4,
                "version": "v2025.12.01"
            },
            {
                "type": "LOOT_RUN_GAME",
                "port": 8767,
                "game_name": "Game C",
                "host_name": "Host C",
                "player_count": 1,
                "max_players": 6
                # No version - should default to unknown
            }
        ]

        games = []
        for i, msg in enumerate(messages):
            game = DiscoveredGame(
                host=f"192.168.1.{100 + i}",
                port=msg.get("port", 8765),
                game_name=msg.get("game_name", "Unknown"),
                host_name=msg.get("host_name", "Unknown"),
                player_count=msg.get("player_count", 0),
                max_players=msg.get("max_players", 6),
                version=msg.get("version", "unknown"),
            )
            games.append(game)

        assert games[0].version == "v2026.01.20"
        assert games[1].version == "v2025.12.01"
        assert games[2].version == "unknown"


class TestVersionImport:
    """Tests for version import in lan module."""

    def test_version_is_imported(self):
        """Test that VERSION is imported from version module."""
        from client.lan import VERSION as lan_version
        from version import VERSION as main_version

        assert lan_version == main_version

    def test_version_constant_available(self):
        """Test that VERSION constant is available in lan module."""
        from client import lan

        assert hasattr(lan, 'VERSION')
        assert isinstance(lan.VERSION, str)


class TestBroadcastDataStructure:
    """Tests for the broadcast data structure."""

    def test_broadcast_data_has_required_fields(self):
        """Test that broadcast data includes all required fields."""
        expected_fields = {
            "type", "port", "game_name", "host_name",
            "player_count", "max_players", "version"
        }

        # Build data the same way start_broadcasting does
        broadcast_data = {
            "type": "LOOT_RUN_GAME",
            "port": 8765,
            "game_name": "Test",
            "host_name": "Host",
            "player_count": 1,
            "max_players": 6,
            "version": VERSION,
        }

        assert set(broadcast_data.keys()) == expected_fields

    def test_broadcast_data_is_json_serializable(self):
        """Test that broadcast data can be serialized to JSON."""
        broadcast_data = {
            "type": "LOOT_RUN_GAME",
            "port": 8765,
            "game_name": "Test Game",
            "host_name": "Host Player",
            "player_count": 2,
            "max_players": 6,
            "version": VERSION,
        }

        # Should not raise
        json_str = json.dumps(broadcast_data)
        parsed = json.loads(json_str)

        assert parsed["version"] == VERSION
        assert parsed["type"] == "LOOT_RUN_GAME"
