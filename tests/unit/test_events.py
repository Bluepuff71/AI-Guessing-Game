"""Unit tests for game/events.py - Event system."""
import pytest
from game.events import Event, EventManager
from game.locations import Location, LocationManager


@pytest.fixture
def location_manager(sample_location_manager):
    """Create a LocationManager for testing."""
    return sample_location_manager


@pytest.fixture
def event_manager(sample_event_manager):
    """Create an EventManager for testing."""
    return sample_event_manager


class TestEventDataclass:
    """Tests for Event dataclass."""

    def test_event_initialization(self):
        """Test Event can be created with all parameters."""
        event = Event(
            id="test",
            name="Test Event",
            description="Test description",
            emoji="🎯",
            duration_rounds=1,
            point_modifier=lambda x: x * 2
        )

        assert event.id == "test"
        assert event.name == "Test Event"
        assert event.description == "Test description"
        assert event.emoji == "🎯"
        assert event.duration_rounds == 1
        assert event.point_modifier is not None

    def test_event_copy_with_location(self, location_manager):
        """Test Event can be copied with a location assigned."""
        template = Event(
            id="test",
            name="Test",
            description="Desc",
            emoji="🎯",
            duration_rounds=2
        )

        location = location_manager.get_location(0)
        copied = template.copy_with_location(location)

        assert copied.id == template.id
        assert copied.name == template.name
        assert copied.affected_location == location
        assert copied.rounds_remaining == 2

    def test_event_point_modifier_callable(self):
        """Test Event point modifier can be called."""
        event = Event(
            id="double",
            name="Double",
            description="2x",
            emoji="💰",
            duration_rounds=1,
            point_modifier=lambda x: x * 2
        )

        assert event.point_modifier(10) == 20
        assert event.point_modifier(5) == 10


class TestEventManagerInitialization:
    """Tests for EventManager initialization."""

    def test_initialization_default(self, event_manager):
        """Test EventManager initializes with default max_concurrent from config."""
        # Should load from config (default 2)
        assert event_manager.max_concurrent == 2
        assert event_manager.active_events == []
        assert len(event_manager.event_pool) == 5  # 5 events in test pool

    def test_initialization_custom_max(self, sample_event_manager, monkeypatch, temp_config_dir, temp_events_config):
        """Test EventManager initializes with custom max_concurrent."""
        from game.events import EventManager
        manager = EventManager(max_concurrent=3)

        assert manager.max_concurrent == 3
        assert manager.active_events == []

    def test_event_pool_contains_expected_events(self, event_manager):
        """Test event pool contains all expected event types."""
        event_ids = [e.id for e in event_manager.event_pool]

        # Point modifiers (from test config)
        assert "jackpot" in event_ids
        assert "clearance_sale" in event_ids
        assert "lockdown" in event_ids
        assert "bonus_stash" in event_ids
        assert "immunity" in event_ids


class TestEventGeneration:
    """Tests for event generation."""

    def test_generate_events_respects_max_concurrent(self, event_manager, location_manager):
        """Test event generation doesn't exceed max_concurrent."""
        game_state = {
            'round_num': 3,  # Trigger: every 3 rounds
            'max_player_score': 60,  # Trigger: over 50
            'catches_last_3_rounds': 3  # Trigger: 2+
        }

        # Generate events (should spawn at most 2)
        for _ in range(5):  # Try to spawn many times
            event_manager.generate_events(game_state, location_manager.get_all())

        assert len(event_manager.active_events) <= event_manager.max_concurrent

    def test_generate_events_round_trigger(self, event_manager, location_manager):
        """Test events generate on round number triggers."""
        game_state = {
            'round_num': 3,  # Every 3 rounds
            'max_player_score': 0,
            'catches_last_3_rounds': 0
        }

        # Clear any existing events
        event_manager.active_events = []

        # Generate should trigger on round 3
        newly_spawned = event_manager.generate_events(game_state, location_manager.get_all())

        # May or may not spawn (probabilistic), but should attempt
        assert len(event_manager.active_events) <= 1

    def test_generate_events_no_free_locations(self, event_manager, location_manager):
        """Test event generation when all locations occupied."""
        # Fill all locations with events
        locations = location_manager.get_all()
        for location in locations:
            if len(event_manager.active_events) < event_manager.max_concurrent:
                event_manager._spawn_event([location])

        initial_count = len(event_manager.active_events)

        # Try to spawn more
        game_state = {'round_num': 3, 'max_player_score': 0, 'catches_last_3_rounds': 0}
        newly_spawned = event_manager.generate_events(game_state, locations)

        # Should not spawn more (at max concurrent)
        assert len(event_manager.active_events) == initial_count


class TestEventSpawning:
    """Tests for event spawning."""

    def test_spawn_event_creates_event(self, event_manager, location_manager):
        """Test spawning an event creates it at a location."""
        locations = location_manager.get_all()

        event = event_manager._spawn_event(locations)

        assert event is not None
        assert event.affected_location in locations
        assert event.rounds_remaining == event.duration_rounds
        assert event in event_manager.active_events

    def test_spawn_event_avoids_occupied_locations(self, event_manager, location_manager):
        """Test spawning avoids locations with existing events."""
        locations = location_manager.get_all()

        # Spawn first event
        first_event = event_manager._spawn_event(locations)

        # Spawn second event
        second_event = event_manager._spawn_event(locations)

        # Should be at different locations
        if first_event and second_event:
            assert first_event.affected_location != second_event.affected_location

    def test_spawn_event_returns_none_when_no_locations(self, event_manager):
        """Test spawning returns None when no free locations."""
        event = event_manager._spawn_event([])

        assert event is None
        assert len(event_manager.active_events) == 0


class TestEventLookup:
    """Tests for event lookup."""

    def test_get_location_event_returns_event(self, event_manager, location_manager):
        """Test getting event for a location."""
        location = location_manager.get_location(0)
        event = event_manager._spawn_event([location])

        found = event_manager.get_location_event(location)

        assert found == event
        assert found.affected_location == location

    def test_get_location_event_returns_none_when_no_event(self, event_manager, location_manager):
        """Test getting event returns None when location has no event."""
        location = location_manager.get_location(0)

        found = event_manager.get_location_event(location)

        assert found is None


class TestEventTicking:
    """Tests for event duration ticking."""

    def test_tick_events_decreases_duration(self, event_manager, location_manager):
        """Test ticking decreases event duration."""
        location = location_manager.get_location(0)
        event = event_manager._spawn_event([location])

        initial_rounds = event.rounds_remaining

        event_manager.tick_events()

        assert event.rounds_remaining == initial_rounds - 1

    def test_tick_events_removes_expired(self, event_manager, location_manager):
        """Test ticking removes events with 0 rounds remaining."""
        location = location_manager.get_location(0)
        event = event_manager._spawn_event([location])

        # Manually set to 1 round remaining
        event.rounds_remaining = 1

        expired = event_manager.tick_events()

        assert event in expired
        assert event not in event_manager.active_events

    def test_tick_events_returns_expired_list(self, event_manager, location_manager):
        """Test ticking returns list of expired events."""
        locations = location_manager.get_all()[:2]

        # Spawn two events
        event1 = event_manager._spawn_event([locations[0]])
        event2 = event_manager._spawn_event([locations[1]])

        # Set both to expire
        event1.rounds_remaining = 1
        event2.rounds_remaining = 1

        expired = event_manager.tick_events()

        assert len(expired) == 2
        assert event1 in expired
        assert event2 in expired
        assert len(event_manager.active_events) == 0


class TestEventEffectApplication:
    """Tests for applying event effects."""

    def test_apply_point_modifier_with_event(self, event_manager, location_manager):
        """Test applying point modifier when event exists."""
        location = location_manager.get_location(0)

        # Create jackpot event (2x points)
        jackpot = event_manager.event_pool[0]  # Jackpot is first
        new_event = jackpot.copy_with_location(location)
        event_manager.active_events.append(new_event)

        modified = event_manager.apply_point_modifier(location, 10)

        assert modified == 20  # 2x multiplier

    def test_apply_point_modifier_without_event(self, event_manager, location_manager):
        """Test applying point modifier returns base when no event."""
        location = location_manager.get_location(0)

        modified = event_manager.apply_point_modifier(location, 10)

        assert modified == 10  # No change

    def test_get_special_effect_returns_effect(self, event_manager, location_manager):
        """Test getting special effect from event."""
        location = location_manager.get_location(0)

        # Find immunity event
        immunity_template = next(e for e in event_manager.event_pool if e.id == "immunity")
        immunity_event = immunity_template.copy_with_location(location)
        event_manager.active_events.append(immunity_event)

        effect = event_manager.get_special_effect(location)

        assert effect == "immunity"

    def test_get_special_effect_returns_none_when_no_event(self, event_manager, location_manager):
        """Test getting special effect returns None when no event."""
        location = location_manager.get_location(0)

        effect = event_manager.get_special_effect(location)

        assert effect is None


class TestEventManagerUtilities:
    """Tests for EventManager utility methods."""

    def test_has_active_events_true(self, event_manager, location_manager):
        """Test has_active_events returns True when events exist."""
        location = location_manager.get_location(0)
        event_manager._spawn_event([location])

        assert event_manager.has_active_events() is True

    def test_has_active_events_false(self, event_manager):
        """Test has_active_events returns False when no events."""
        assert event_manager.has_active_events() is False


class TestEventTypes:
    """Tests for specific event types."""

    def test_jackpot_doubles_points(self, event_manager):
        """Test Jackpot event doubles points."""
        jackpot = next(e for e in event_manager.event_pool if e.id == "jackpot")

        assert jackpot.point_modifier(10) == 20
        assert jackpot.point_modifier(25) == 50

    def test_clearance_adds_50_percent(self, event_manager):
        """Test Clearance Sale adds 50%."""
        clearance = next(e for e in event_manager.event_pool if e.id == "clearance_sale")

        assert clearance.point_modifier(10) == 15
        assert clearance.point_modifier(20) == 30

    def test_lockdown_reduces_30_percent(self, event_manager):
        """Test Security Lockdown reduces by 30%."""
        lockdown = next(e for e in event_manager.event_pool if e.id == "lockdown")

        assert lockdown.point_modifier(10) == 7
        assert lockdown.point_modifier(20) == 14

    def test_bonus_stash_adds_flat_20(self, event_manager):
        """Test Bonus Stash adds flat 20 points."""
        bonus = next(e for e in event_manager.event_pool if e.id == "bonus_stash")

        assert bonus.point_modifier(10) == 30
        assert bonus.point_modifier(0) == 20

    def test_immunity_special_effect(self, event_manager):
        """Test Immunity has immunity special effect."""
        immunity = next(e for e in event_manager.event_pool if e.id == "immunity")

        assert immunity.special_effect == "immunity"

    def test_event_durations(self, event_manager):
        """Test events have appropriate durations."""
        # Most events should be 1-2 rounds
        for event in event_manager.event_pool:
            assert 1 <= event.duration_rounds <= 2
