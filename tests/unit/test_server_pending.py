# tests/unit/test_server_pending.py
"""Unit tests for pending state trackers."""

import pytest
from server.pending import PendingChoices, PendingEscapes


class TestPendingChoices:
    """Test PendingChoices tracker."""

    def test_record_location_choice(self):
        """Test recording a location choice."""
        pending = PendingChoices()
        pending.record_choice("player1", 2)

        assert pending.get_choice("player1") == 2
        assert pending.get_choice("player2") is None

    def test_has_all_choices(self):
        """Test checking if all players have chosen."""
        pending = PendingChoices()
        player_ids = ["p1", "p2", "p3"]

        assert not pending.has_all_choices(player_ids)

        pending.record_choice("p1", 0)
        pending.record_choice("p2", 1)
        assert not pending.has_all_choices(player_ids)

        pending.record_choice("p3", 2)
        assert pending.has_all_choices(player_ids)

    def test_clear(self):
        """Test clearing choices."""
        pending = PendingChoices()
        pending.record_choice("p1", 0)
        pending.clear()

        assert pending.get_choice("p1") is None


class TestPendingEscapes:
    """Test PendingEscapes tracker."""

    def test_add_pending_escape(self):
        """Test adding a pending escape."""
        pending = PendingEscapes()
        pending.add_escape(
            player_id="p1",
            location_name="Bank",
            location_points=50,
            escape_options=[{"id": "vault", "name": "Hide in Vault"}],
            ai_prediction="vault",
            ai_reasoning="Player usually hides"
        )

        assert pending.has_pending("p1")
        assert not pending.has_pending("p2")

    def test_record_escape_choice(self):
        """Test recording an escape choice."""
        pending = PendingEscapes()
        pending.add_escape(
            player_id="p1",
            location_name="Bank",
            location_points=50,
            escape_options=[{"id": "vault"}],
            ai_prediction="vault",
            ai_reasoning="test"
        )

        pending.record_choice("p1", "vault")
        escape = pending.get_escape("p1")

        assert escape.choice_received
        assert escape.chosen_option_id == "vault"

    def test_all_resolved(self):
        """Test checking if all escapes are resolved."""
        pending = PendingEscapes()
        pending.add_escape("p1", "Bank", 50, [], "x", "y")
        pending.add_escape("p2", "Museum", 30, [], "x", "y")

        assert not pending.all_resolved()

        pending.record_choice("p1", "hide")
        assert not pending.all_resolved()

        pending.record_choice("p2", "run")
        assert pending.all_resolved()

    def test_get_unresolved(self):
        """Test getting unresolved escapes."""
        pending = PendingEscapes()
        pending.add_escape("p1", "Bank", 50, [], "x", "y")
        pending.add_escape("p2", "Museum", 30, [], "x", "y")

        pending.record_choice("p1", "hide")

        unresolved = pending.get_unresolved_player_ids()
        assert unresolved == ["p2"]
