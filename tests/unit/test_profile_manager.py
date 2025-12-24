"""Unit tests for game/profile_manager.py - ProfileManager class."""
import pytest
import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from game.profile_manager import (
    ProfileManager, PlayerProfile, ProfileStats, BehavioralStats,
    AIMemoryStats, MatchHistoryEntry, ProfileSummary
)


@pytest.fixture
def temp_profile_dir(tmp_path):
    """Create temporary profile directory for testing."""
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    ai_models_dir = profile_dir / "ai_models"
    ai_models_dir.mkdir()

    # Override ProfileManager directories
    ProfileManager._profiles_dir = str(profile_dir)
    ProfileManager._ai_models_dir = str(ai_models_dir)
    ProfileManager._index_file = str(profile_dir / "profiles_index.json")

    # Reset singleton
    ProfileManager._instance = None

    yield profile_dir

    # Cleanup
    ProfileManager._instance = None


class TestProfileDataClasses:
    """Tests for profile data classes."""

    def test_profile_stats_initialization(self):
        """Test ProfileStats initializes with correct defaults."""
        stats = ProfileStats()

        assert stats.total_games == 0
        assert stats.wins == 0
        assert stats.losses == 0
        assert stats.win_rate == 0.0
        assert stats.highest_score == 0

    def test_profile_stats_win_rate_calculation(self):
        """Test win rate calculation."""
        stats = ProfileStats(total_games=10, wins=7, losses=3)
        stats.update_win_rate()

        assert stats.win_rate == 0.7

    def test_behavioral_stats_initialization(self):
        """Test BehavioralStats initializes correctly."""
        b_stats = BehavioralStats()

        assert b_stats.favorite_location == "Unknown"
        assert b_stats.location_frequencies == {}
        assert b_stats.risk_profile == "neutral"
        assert b_stats.predictability_score == 0.5

    def test_ai_memory_stats_catch_rate(self):
        """Test AI memory catch rate calculation."""
        ai_stats = AIMemoryStats(times_predicted=10, times_caught_by_ai=3)
        ai_stats.update_catch_rate()

        assert ai_stats.catch_rate == 0.3

    def test_match_history_entry(self):
        """Test MatchHistoryEntry creation."""
        entry = MatchHistoryEntry(
            game_id="test-123",
            date="2025-12-24T12:00:00Z",
            outcome="win",
            final_score=105,
            rounds_played=12,
            caught=False,
            num_opponents=2
        )

        assert entry.game_id == "test-123"
        assert entry.outcome == "win"
        assert entry.final_score == 105


class TestPlayerProfile:
    """Tests for PlayerProfile class."""

    def test_profile_creation(self):
        """Test creating a PlayerProfile."""
        profile = PlayerProfile(
            profile_id="test-id",
            name="Alice",
            created_date="2025-12-24T12:00:00Z",
            last_played="2025-12-24T12:00:00Z"
        )

        assert profile.profile_id == "test-id"
        assert profile.name == "Alice"
        assert isinstance(profile.stats, ProfileStats)
        assert isinstance(profile.behavioral_stats, BehavioralStats)

    def test_profile_to_dict(self):
        """Test converting profile to dictionary."""
        profile = PlayerProfile(
            profile_id="test-id",
            name="Alice",
            created_date="2025-12-24T12:00:00Z",
            last_played="2025-12-24T12:00:00Z"
        )

        data = profile.to_dict()

        assert data['profile_id'] == "test-id"
        assert data['name'] == "Alice"
        assert 'stats' in data
        assert 'behavioral_stats' in data

    def test_profile_from_dict(self):
        """Test creating profile from dictionary."""
        data = {
            'profile_id': "test-id",
            'name': "Bob",
            'created_date': "2025-12-24T12:00:00Z",
            'last_played': "2025-12-24T12:00:00Z",
            'stats': {'total_games': 5, 'wins': 3, 'losses': 2, 'win_rate': 0.6,
                     'highest_score': 95, 'total_points_earned': 0, 'times_caught': 0,
                     'total_rounds_played': 0},
            'behavioral_stats': {'favorite_location': 'Unknown',
                                'location_frequencies': {}, 'risk_profile': 'neutral',
                                'predictability_score': 0.5, 'avg_location_value': 0.0,
                                'most_profitable_location': 'Unknown', 'item_usage': {}},
            'ai_memory': {'times_predicted': 0, 'times_caught_by_ai': 0,
                         'catch_rate': 0.0, 'prediction_accuracy': 0,
                         'has_personal_model': False, 'model_trained_date': None},
            'match_history': [],
            'achievements': {}
        }

        profile = PlayerProfile.from_dict(data)

        assert profile.profile_id == "test-id"
        assert profile.name == "Bob"
        assert isinstance(profile.stats, ProfileStats)
        assert profile.stats.total_games == 5


class TestProfileManager:
    """Tests for ProfileManager class."""

    def test_singleton_pattern(self, temp_profile_dir):
        """Test ProfileManager is a singleton."""
        pm1 = ProfileManager()
        pm2 = ProfileManager()

        assert pm1 is pm2

    def test_create_profile(self, temp_profile_dir):
        """Test creating a new profile."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        assert profile.name == "Alice"
        assert profile.profile_id is not None
        assert len(profile.profile_id) > 0
        assert profile.stats.total_games == 0

        # Verify file was created
        profile_file = temp_profile_dir / f"{profile.profile_id}.json"
        assert profile_file.exists()

    def test_save_and_load_profile(self, temp_profile_dir):
        """Test saving and loading a profile."""
        pm = ProfileManager()
        profile = pm.create_profile("Bob")

        # Modify profile
        profile.stats.total_games = 5
        profile.stats.wins = 3
        pm.save_profile(profile)

        # Load it back
        loaded = pm.load_profile(profile.profile_id)

        assert loaded is not None
        assert loaded.name == "Bob"
        assert loaded.stats.total_games == 5
        assert loaded.stats.wins == 3

    def test_load_nonexistent_profile(self, temp_profile_dir):
        """Test loading a profile that doesn't exist."""
        pm = ProfileManager()
        loaded = pm.load_profile("nonexistent-id")

        assert loaded is None

    def test_delete_profile(self, temp_profile_dir):
        """Test deleting a profile."""
        pm = ProfileManager()
        profile = pm.create_profile("Charlie")
        profile_id = profile.profile_id

        # Verify it exists
        assert pm.load_profile(profile_id) is not None

        # Delete it
        result = pm.delete_profile(profile_id)

        assert result is True
        assert pm.load_profile(profile_id) is None

    def test_list_all_profiles(self, temp_profile_dir):
        """Test listing all profiles."""
        pm = ProfileManager()

        pm.create_profile("Alice")
        pm.create_profile("Bob")
        pm.create_profile("Charlie")

        profiles = pm.list_all_profiles()

        assert len(profiles) == 3
        names = {p.name for p in profiles}
        assert "Alice" in names
        assert "Bob" in names
        assert "Charlie" in names

    def test_list_profiles_sorted_by_last_played(self, temp_profile_dir):
        """Test profiles are sorted by most recent first."""
        pm = ProfileManager()

        # Create profiles with different timestamps
        profile1 = pm.create_profile("Alice")
        profile2 = pm.create_profile("Bob")

        # Update Bob's last_played to be more recent
        profile2.last_played = "2025-12-25T12:00:00Z"
        pm.save_profile(profile2)

        profiles = pm.list_all_profiles()

        # Bob should be first (most recent)
        assert profiles[0].name == "Bob"


class TestStatsUpdate:
    """Tests for stats updates after games."""

    def test_update_stats_after_win(self, temp_profile_dir):
        """Test updating stats after winning a game."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        game_data = {
            'game_id': str(uuid.uuid4()),
            'outcome': 'win',
            'final_score': 105,
            'rounds_played': 12,
            'caught': False,
            'num_opponents': 2,
            'locations_chosen': ['Bank Heist', 'Jewelry Store', 'Bank Heist'],
            'items_used': ['Scout', 'Lucky Charm']
        }

        pm.update_stats_after_game(profile.profile_id, game_data)

        # Reload profile
        updated = pm.load_profile(profile.profile_id)

        assert updated.stats.total_games == 1
        assert updated.stats.wins == 1
        assert updated.stats.losses == 0
        assert updated.stats.win_rate == 1.0
        assert updated.stats.highest_score == 105

    def test_update_stats_after_loss(self, temp_profile_dir):
        """Test updating stats after losing a game."""
        pm = ProfileManager()
        profile = pm.create_profile("Bob")

        game_data = {
            'game_id': str(uuid.uuid4()),
            'outcome': 'loss',
            'final_score': 45,
            'rounds_played': 8,
            'caught': True,
            'num_opponents': 2,
            'locations_chosen': ['Pawn Shop', 'Gas Station'],
            'items_used': []
        }

        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)

        assert updated.stats.total_games == 1
        assert updated.stats.wins == 0
        assert updated.stats.losses == 1
        assert updated.stats.times_caught == 1

    def test_match_history_ring_buffer(self, temp_profile_dir):
        """Test match history keeps only last 10 games."""
        pm = ProfileManager()
        profile = pm.create_profile("Charlie")

        # Play 15 games
        for i in range(15):
            game_data = {
                'game_id': f"game-{i}",
                'outcome': 'win' if i % 2 == 0 else 'loss',
                'final_score': 50 + i,
                'rounds_played': 10,
                'caught': False,
                'num_opponents': 2,
                'locations_chosen': ['Bank Heist'],
                'items_used': []
            }
            pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)

        # Should only have last 10 games
        assert len(updated.match_history) == 10
        # Last game should be game-14
        assert updated.match_history[-1].game_id == "game-14"


class TestBehavioralStats:
    """Tests for behavioral statistics tracking."""

    def test_update_location_frequencies(self, temp_profile_dir):
        """Test location frequency tracking."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        game_data = {
            'game_id': str(uuid.uuid4()),
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 5,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': ['Bank Heist', 'Bank Heist', 'Jewelry Store', 'Bank Heist'],
            'items_used': []
        }

        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)

        assert updated.behavioral_stats.location_frequencies['Bank Heist'] == 3
        assert updated.behavioral_stats.location_frequencies['Jewelry Store'] == 1
        assert updated.behavioral_stats.favorite_location == 'Bank Heist'

    def test_update_item_usage(self, temp_profile_dir):
        """Test item usage tracking."""
        pm = ProfileManager()
        profile = pm.create_profile("Bob")

        game_data = {
            'game_id': str(uuid.uuid4()),
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 5,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': ['Bank Heist'],
            'items_used': ['Scout', 'Scout', 'Lucky Charm']
        }

        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)

        assert updated.behavioral_stats.item_usage['Scout'] == 2
        assert updated.behavioral_stats.item_usage['Lucky Charm'] == 1

    def test_predictability_score_calculation(self, temp_profile_dir):
        """Test predictability score calculation."""
        pm = ProfileManager()
        profile = pm.create_profile("Predictable")

        # Play games always choosing same location
        for _ in range(5):
            game_data = {
                'game_id': str(uuid.uuid4()),
                'outcome': 'win',
                'final_score': 100,
                'rounds_played': 3,
                'caught': False,
                'num_opponents': 1,
                'locations_chosen': ['Bank Heist', 'Bank Heist', 'Bank Heist'],
                'items_used': []
            }
            pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)

        # Should have high predictability (always choosing same location)
        assert updated.behavioral_stats.predictability_score == 1.0


class TestProfileAnalysis:
    """Tests for profile analysis methods."""

    def test_get_location_preferences(self, temp_profile_dir):
        """Test getting normalized location preferences."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Manually set location frequencies
        profile.behavioral_stats.location_frequencies = {
            'Bank Heist': 6,
            'Jewelry Store': 3,
            'Pawn Shop': 1
        }
        pm.save_profile(profile)

        preferences = pm.get_location_preferences(profile)

        assert preferences['Bank Heist'] == 0.6
        assert preferences['Jewelry Store'] == 0.3
        assert preferences['Pawn Shop'] == 0.1

    def test_get_play_style_unpredictable(self, temp_profile_dir):
        """Test play style detection - unpredictable."""
        pm = ProfileManager()
        profile = pm.create_profile("Unpredictable")

        profile.stats.total_games = 5
        profile.behavioral_stats.predictability_score = 0.3
        pm.save_profile(profile)

        style = pm.get_play_style(profile)

        assert style == "unpredictable"

    def test_get_play_style_aggressive(self, temp_profile_dir):
        """Test play style detection - aggressive."""
        pm = ProfileManager()
        profile = pm.create_profile("Aggressive")

        profile.stats.total_games = 10
        profile.stats.times_caught = 7
        profile.behavioral_stats.predictability_score = 0.6
        pm.save_profile(profile)

        style = pm.get_play_style(profile)

        assert style == "aggressive"

    def test_get_play_style_conservative(self, temp_profile_dir):
        """Test play style detection - conservative."""
        pm = ProfileManager()
        profile = pm.create_profile("Conservative")

        profile.stats.total_games = 10
        profile.stats.times_caught = 2
        profile.behavioral_stats.predictability_score = 0.6
        pm.save_profile(profile)

        style = pm.get_play_style(profile)

        assert style == "conservative"

    def test_get_play_style_new_player(self, temp_profile_dir):
        """Test play style for new players defaults to neutral."""
        pm = ProfileManager()
        profile = pm.create_profile("NewPlayer")

        style = pm.get_play_style(profile)

        assert style == "neutral"


class TestProfileIndex:
    """Tests for profile index management."""

    def test_index_created_on_profile_creation(self, temp_profile_dir):
        """Test index file is created when profiles are created."""
        pm = ProfileManager()
        pm.create_profile("Alice")

        index_file = temp_profile_dir / "profiles_index.json"
        assert index_file.exists()

        with open(index_file, 'r') as f:
            index_data = json.load(f)

        assert index_data['total_profiles'] == 1
        assert len(index_data['profiles']) == 1
        assert index_data['profiles'][0]['name'] == "Alice"

    def test_index_updated_on_profile_changes(self, temp_profile_dir):
        """Test index is updated when profiles change."""
        pm = ProfileManager()
        pm.create_profile("Alice")
        pm.create_profile("Bob")

        index_file = temp_profile_dir / "profiles_index.json"
        with open(index_file, 'r') as f:
            index_data = json.load(f)

        assert index_data['total_profiles'] == 2
