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
            'match_history': []
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

        # Set Alice to an older date, Bob to a more recent date
        profile1.last_played = "2025-01-01T00:00:00Z"
        profile2.last_played = "2025-12-31T23:59:59Z"
        pm.save_profile(profile1)
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


class TestHidingStats:
    """Tests for hiding stats updates."""

    def test_update_hiding_stats_basic(self, temp_profile_dir):
        """Test updating hiding stats from game data."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        game_data = {
            'game_id': str(uuid.uuid4()),
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': ['Bank Heist'],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 2,
                'total_escapes': 1,
                'hide_attempts': 1,
                'run_attempts': 1,
                'successful_hides': 1,
                'successful_runs': 0,
                'favorite_escape_options': {'store_stockroom': 1, 'store_backdoor': 1},
                'escape_option_history': ['store_stockroom', 'store_backdoor'],
                'ai_correct_predictions': 1
            }
        }

        pm.update_stats_after_game(profile.profile_id, game_data)
        updated = pm.load_profile(profile.profile_id)

        assert updated.hiding_stats.total_caught_instances == 2
        assert updated.hiding_stats.total_escapes == 1
        assert updated.hiding_stats.hide_attempts == 1
        assert updated.hiding_stats.run_attempts == 1

    def test_update_hiding_stats_accumulative(self, temp_profile_dir):
        """Test hiding stats accumulate across games."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # First game
        game_data1 = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 2,
                'total_escapes': 2,
                'hide_attempts': 2,
                'run_attempts': 0,
                'successful_hides': 2,
                'successful_runs': 0,
                'favorite_escape_options': {'store_stockroom': 2},
                'escape_option_history': ['store_stockroom', 'store_stockroom'],
                'ai_correct_predictions': 0
            }
        }
        pm.update_stats_after_game(profile.profile_id, game_data1)

        # Second game
        game_data2 = {
            'game_id': 'game-2',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 3,
                'total_escapes': 2,
                'hide_attempts': 1,
                'run_attempts': 2,
                'successful_hides': 0,
                'successful_runs': 2,
                'favorite_escape_options': {'store_backdoor': 3},
                'escape_option_history': ['store_backdoor', 'store_backdoor', 'store_backdoor'],
                'ai_correct_predictions': 1
            }
        }
        pm.update_stats_after_game(profile.profile_id, game_data2)

        updated = pm.load_profile(profile.profile_id)

        assert updated.hiding_stats.total_caught_instances == 5  # 2 + 3
        assert updated.hiding_stats.total_escapes == 4  # 2 + 2
        assert updated.hiding_stats.hide_attempts == 3  # 2 + 1
        assert updated.hiding_stats.run_attempts == 2  # 0 + 2

    def test_hiding_stats_risk_profile_aggressive_hider(self, temp_profile_dir):
        """Test risk profile becomes aggressive_hider when favoring hiding."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Game data with strong hide preference (>=70% hides)
        game_data = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 10,
                'total_escapes': 8,
                'hide_attempts': 8,  # 80% hide
                'run_attempts': 2,
                'successful_hides': 7,
                'successful_runs': 1,
                'favorite_escape_options': {},
                'escape_option_history': [],
                'ai_correct_predictions': 2
            }
        }
        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)
        assert updated.hiding_stats.risk_profile_when_caught == "aggressive_hider"

    def test_hiding_stats_risk_profile_runner(self, temp_profile_dir):
        """Test risk profile becomes runner when favoring running."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Game data with strong run preference (<=30% hides)
        game_data = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 10,
                'total_escapes': 8,
                'hide_attempts': 2,  # 20% hide
                'run_attempts': 8,
                'successful_hides': 1,
                'successful_runs': 7,
                'favorite_escape_options': {},
                'escape_option_history': [],
                'ai_correct_predictions': 2
            }
        }
        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)
        assert updated.hiding_stats.risk_profile_when_caught == "runner"

    def test_hiding_stats_risk_profile_balanced(self, temp_profile_dir):
        """Test risk profile stays balanced with mixed choices."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Game data with balanced preference
        game_data = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': [],
            'hiding_data': {
                'total_caught_instances': 10,
                'total_escapes': 8,
                'hide_attempts': 5,  # 50% hide
                'run_attempts': 5,
                'successful_hides': 4,
                'successful_runs': 4,
                'favorite_escape_options': {},
                'escape_option_history': [],
                'ai_correct_predictions': 2
            }
        }
        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)
        assert updated.hiding_stats.risk_profile_when_caught == "balanced"

    def test_hiding_stats_escape_option_history_limit(self, temp_profile_dir):
        """Test escape option history is limited to last 20 entries."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Add many games with escape history
        for i in range(5):
            game_data = {
                'game_id': f'game-{i}',
                'outcome': 'win',
                'final_score': 100,
                'rounds_played': 10,
                'caught': False,
                'num_opponents': 1,
                'locations_chosen': [],
                'items_used': [],
                'hiding_data': {
                    'total_caught_instances': 5,
                    'total_escapes': 5,
                    'hide_attempts': 5,
                    'run_attempts': 0,
                    'successful_hides': 5,
                    'successful_runs': 0,
                    'favorite_escape_options': {f'option_{i}': 5},
                    'escape_option_history': [f'option_{i}'] * 10,  # 10 per game = 50 total
                    'ai_correct_predictions': 0
                }
            }
            pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)
        # Should only keep last 20 entries
        assert len(updated.hiding_stats.escape_option_history) <= 20

    def test_hiding_stats_no_data_backward_compat(self, temp_profile_dir):
        """Test games without hiding_data don't crash."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Game data without hiding_data field
        game_data = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': ['Bank Heist'],
            'items_used': []
            # No 'hiding_data' key
        }
        pm.update_stats_after_game(profile.profile_id, game_data)

        updated = pm.load_profile(profile.profile_id)
        # Should not crash, hiding stats should remain at defaults
        assert updated.hiding_stats.total_caught_instances == 0


class TestLocationPreferences:
    """Tests for location preference analysis."""

    def test_get_location_preferences_empty(self, temp_profile_dir):
        """Test preferences with no history."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        preferences = pm.get_location_preferences(profile)
        assert preferences == {}

    def test_get_location_preferences_single(self, temp_profile_dir):
        """Test preferences with single location history."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        profile.behavioral_stats.location_frequencies = {'Bank Heist': 10}
        pm.save_profile(profile)

        preferences = pm.get_location_preferences(profile)
        assert preferences == {'Bank Heist': 1.0}


class TestProfileFromDictEdgeCases:
    """Tests for PlayerProfile.from_dict edge cases."""

    def test_from_dict_without_hiding_stats(self):
        """Test from_dict adds hiding_stats for old profiles."""
        data = {
            'profile_id': "test-id",
            'name': "OldPlayer",
            'created_date': "2025-12-01T00:00:00Z",
            'last_played': "2025-12-01T00:00:00Z",
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
            'match_history': []
            # Note: No 'hiding_stats' key
        }

        profile = PlayerProfile.from_dict(data)

        # Should have default hiding stats
        from game.profile_manager import HidingBehavioralStats
        assert isinstance(profile.hiding_stats, HidingBehavioralStats)
        assert profile.hiding_stats.total_caught_instances == 0

    def test_from_dict_with_match_history_entries(self):
        """Test from_dict converts match history entries."""
        data = {
            'profile_id': "test-id",
            'name': "Bob",
            'created_date': "2025-12-24T00:00:00Z",
            'last_played': "2025-12-24T00:00:00Z",
            'stats': {'total_games': 2, 'wins': 1, 'losses': 1, 'win_rate': 0.5,
                     'highest_score': 100, 'total_points_earned': 150, 'times_caught': 1,
                     'total_rounds_played': 20},
            'behavioral_stats': {'favorite_location': 'Bank', 'location_frequencies': {'Bank': 5},
                                'risk_profile': 'neutral', 'predictability_score': 0.5,
                                'avg_location_value': 0.0, 'most_profitable_location': 'Bank',
                                'item_usage': {}},
            'hiding_stats': {'total_caught_instances': 2, 'total_escapes': 1,
                            'hide_attempts': 1, 'run_attempts': 1,
                            'hide_success_rate': 1.0, 'run_success_rate': 0.0,
                            'favorite_escape_options': {}, 'escape_option_history': [],
                            'ai_prediction_accuracy': 0.5, 'ai_correct_predictions': 1,
                            'location_specific_preferences': {}, 'risk_profile_when_caught': 'balanced'},
            'ai_memory': {'times_predicted': 2, 'times_caught_by_ai': 1,
                         'catch_rate': 0.5, 'prediction_accuracy': 0,
                         'has_personal_model': False, 'model_trained_date': None},
            'match_history': [
                {'game_id': 'game-1', 'date': '2025-12-24T00:00:00Z', 'outcome': 'win',
                 'final_score': 100, 'rounds_played': 10, 'caught': False, 'num_opponents': 1,
                 'escapes_in_game': 0, 'high_threat_escape': False},
                {'game_id': 'game-2', 'date': '2025-12-24T01:00:00Z', 'outcome': 'loss',
                 'final_score': 50, 'rounds_played': 10, 'caught': True, 'num_opponents': 1,
                 'escapes_in_game': 1, 'high_threat_escape': False}
            ]
        }

        profile = PlayerProfile.from_dict(data)

        assert len(profile.match_history) == 2
        assert isinstance(profile.match_history[0], MatchHistoryEntry)
        assert profile.match_history[0].game_id == 'game-1'
        assert profile.match_history[1].caught is True


class TestWinRateEdgeCases:
    """Tests for win rate calculation edge cases."""

    def test_win_rate_zero_games(self):
        """Test win rate with zero games."""
        stats = ProfileStats()
        stats.update_win_rate()
        assert stats.win_rate == 0.0

    def test_catch_rate_zero_predictions(self):
        """Test catch rate with zero predictions."""
        ai_stats = AIMemoryStats()
        ai_stats.update_catch_rate()
        assert ai_stats.catch_rate == 0.0


class TestProfileLoadErrors:
    """Tests for error handling during profile loading."""

    def test_load_corrupt_profile(self, temp_profile_dir, monkeypatch):
        """Test loading a corrupt profile file."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")
        profile_id = profile.profile_id

        # Corrupt the profile file
        profile_path = temp_profile_dir / f"{profile_id}.json"
        with open(profile_path, 'w') as f:
            f.write("not valid json {{{{")

        # Should return None and print warning
        loaded = pm.load_profile(profile_id)
        assert loaded is None

    def test_list_profiles_with_corrupt_file(self, temp_profile_dir):
        """Test listing profiles handles corrupt files gracefully."""
        pm = ProfileManager()
        pm.create_profile("Alice")
        pm.create_profile("Bob")

        # Create a corrupt file
        corrupt_file = temp_profile_dir / "corrupt.json"
        with open(corrupt_file, 'w') as f:
            f.write("not json")

        # Should still list valid profiles
        profiles = pm.list_all_profiles()
        names = {p.name for p in profiles}
        assert "Alice" in names
        assert "Bob" in names


class TestProfileDeletionEdgeCases:
    """Tests for profile deletion edge cases."""

    def test_delete_profile_with_model(self, temp_profile_dir):
        """Test deleting a profile also deletes its AI model."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")
        profile_id = profile.profile_id

        # Create fake model files
        ai_models_dir = temp_profile_dir / "ai_models"
        model_file = ai_models_dir / f"{profile_id}_model.pkl"
        encoder_file = ai_models_dir / f"{profile_id}_encoder.pkl"

        model_file.write_text("fake model")
        encoder_file.write_text("fake encoder")

        # Verify files exist
        assert model_file.exists()
        assert encoder_file.exists()

        # Delete profile
        result = pm.delete_profile(profile_id)

        assert result is True
        assert not model_file.exists()
        assert not encoder_file.exists()


class TestUpdateStatsEdgeCases:
    """Tests for update_stats_after_game edge cases."""

    def test_update_stats_nonexistent_profile(self, temp_profile_dir):
        """Test updating stats for nonexistent profile does nothing."""
        pm = ProfileManager()

        # Should not raise, just return
        pm.update_stats_after_game("nonexistent-id", {
            'outcome': 'win',
            'final_score': 100,
            'rounds_played': 10,
            'caught': False
        })

    def test_update_stats_highest_score_not_beaten(self, temp_profile_dir):
        """Test highest score not updated if not beaten."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # First game with high score
        game_data1 = {
            'game_id': 'game-1',
            'outcome': 'win',
            'final_score': 150,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': []
        }
        pm.update_stats_after_game(profile.profile_id, game_data1)

        # Second game with lower score
        game_data2 = {
            'game_id': 'game-2',
            'outcome': 'win',
            'final_score': 80,
            'rounds_played': 10,
            'caught': False,
            'num_opponents': 1,
            'locations_chosen': [],
            'items_used': []
        }
        pm.update_stats_after_game(profile.profile_id, game_data2)

        updated = pm.load_profile(profile.profile_id)
        assert updated.stats.highest_score == 150  # Should still be first game's score


class TestLocationPreferencesEdgeCases:
    """Tests for get_location_preferences edge cases."""

    def test_location_preferences_zero_total(self, temp_profile_dir):
        """Test preferences when total is zero."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        # Set location frequencies with zeros (edge case)
        profile.behavioral_stats.location_frequencies = {}
        pm.save_profile(profile)

        preferences = pm.get_location_preferences(profile)
        assert preferences == {}


class TestTrainPlayerModel:
    """Tests for _train_player_model method."""

    def test_train_model_at_milestone(self, temp_profile_dir, monkeypatch):
        """Test model training is triggered at milestone games."""
        pm = ProfileManager()
        profile = pm.create_profile("Alice")

        trained = []

        # Mock PlayerPredictor
        class MockPredictor:
            def __init__(self, profile_id, data_dir):
                pass

            def train_personal_model(self, min_samples=10):
                trained.append(True)
                return True

        monkeypatch.setattr("ai.player_predictor.PlayerPredictor", MockPredictor, raising=False)

        # Play exactly 5 games to trigger training
        for i in range(5):
            game_data = {
                'game_id': f'game-{i}',
                'outcome': 'win',
                'final_score': 100,
                'rounds_played': 10,
                'caught': False,
                'num_opponents': 1,
                'locations_chosen': ['Bank'],
                'items_used': []
            }
            pm.update_stats_after_game(profile.profile_id, game_data)

        # Model should have been trained once at game 5
        assert len(trained) >= 1
