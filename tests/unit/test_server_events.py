# tests/unit/test_server_events.py
"""Unit tests for server event types."""

import pytest
from server.events import GameEvent, GameEventType


class TestGameEventType:
    """Test GameEventType enum."""

    def test_has_player_events(self):
        """Test player-related event types exist."""
        assert GameEventType.PLAYER_JOIN
        assert GameEventType.PLAYER_LEAVE
        assert GameEventType.PLAYER_READY

    def test_has_game_flow_events(self):
        """Test game flow event types exist."""
        assert GameEventType.GAME_START
        assert GameEventType.ROUND_START
        assert GameEventType.ALL_CHOICES_IN
        assert GameEventType.ROUND_COMPLETE

    def test_has_timeout_events(self):
        """Test timeout event types exist."""
        assert GameEventType.SHOP_TIMEOUT
        assert GameEventType.CHOICE_TIMEOUT
        assert GameEventType.ESCAPE_TIMEOUT


class TestGameEvent:
    """Test GameEvent dataclass."""

    def test_create_event_with_data(self):
        """Test creating an event with data."""
        event = GameEvent(
            type=GameEventType.PLAYER_JOIN,
            player_id="player123",
            data={"username": "Alice"}
        )
        assert event.type == GameEventType.PLAYER_JOIN
        assert event.player_id == "player123"
        assert event.data["username"] == "Alice"

    def test_create_event_without_player(self):
        """Test creating a system event without player_id."""
        event = GameEvent(
            type=GameEventType.SHOP_TIMEOUT,
            data={}
        )
        assert event.type == GameEventType.SHOP_TIMEOUT
        assert event.player_id is None
