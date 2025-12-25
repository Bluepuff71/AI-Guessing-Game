"""Player profile management system for persistent player data and AI memory."""
import json
import os
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any


@dataclass
class ProfileStats:
    """Player statistics across all games."""
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    highest_score: int = 0
    total_points_earned: int = 0
    times_caught: int = 0
    total_rounds_played: int = 0

    def update_win_rate(self):
        """Calculate win rate from wins/total_games."""
        if self.total_games > 0:
            self.win_rate = self.wins / self.total_games
        else:
            self.win_rate = 0.0


@dataclass
class BehavioralStats:
    """Player behavioral patterns and tendencies."""
    favorite_location: str = "Unknown"
    location_frequencies: Dict[str, int] = field(default_factory=dict)
    risk_profile: str = "neutral"  # aggressive, conservative, neutral, unpredictable
    predictability_score: float = 0.5  # 0.0 = unpredictable, 1.0 = highly predictable
    avg_location_value: float = 0.0
    most_profitable_location: str = "Unknown"
    item_usage: Dict[str, int] = field(default_factory=dict)


@dataclass
class HidingBehavioralStats:
    """Player's escape patterns when caught (prediction-based system)."""
    total_caught_instances: int = 0  # Total times caught (regardless of escape)
    total_escapes: int = 0  # Total successful escapes
    hide_attempts: int = 0
    run_attempts: int = 0
    hide_success_rate: float = 0.0
    run_success_rate: float = 0.0
    favorite_escape_options: Dict[str, int] = field(default_factory=dict)  # option_id -> count
    escape_option_history: List[str] = field(default_factory=list)  # Last N escape choices for recency
    ai_prediction_accuracy: float = 0.0  # How often AI correctly predicts this player
    ai_correct_predictions: int = 0  # Raw count of correct AI predictions
    location_specific_preferences: Dict[str, str] = field(default_factory=dict)  # location -> 'hide'|'run'
    risk_profile_when_caught: str = "balanced"  # "aggressive_hider", "runner", "balanced"


@dataclass
class AIMemoryStats:
    """AI's memory of interactions with this player."""
    times_predicted: int = 0
    times_caught_by_ai: int = 0
    catch_rate: float = 0.0
    prediction_accuracy: int = 0
    has_personal_model: bool = False
    model_trained_date: Optional[str] = None

    def update_catch_rate(self):
        """Calculate AI's catch rate against this player."""
        if self.times_predicted > 0:
            self.catch_rate = self.times_caught_by_ai / self.times_predicted
        else:
            self.catch_rate = 0.0


@dataclass
class MatchHistoryEntry:
    """Single game entry in match history."""
    game_id: str
    date: str
    outcome: str  # "win" | "loss" | "ai_win"
    final_score: int
    rounds_played: int
    caught: bool
    num_opponents: int
    escapes_in_game: int = 0  # Number of successful escapes in this game
    high_threat_escape: bool = False  # Whether player escaped with 90%+ AI threat


@dataclass
class PlayerProfile:
    """Complete player profile with stats and history."""
    profile_id: str
    name: str
    created_date: str
    last_played: str
    stats: ProfileStats = field(default_factory=ProfileStats)
    behavioral_stats: BehavioralStats = field(default_factory=BehavioralStats)
    hiding_stats: HidingBehavioralStats = field(default_factory=HidingBehavioralStats)
    ai_memory: AIMemoryStats = field(default_factory=AIMemoryStats)
    match_history: List[MatchHistoryEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert profile to dictionary for JSON serialization."""
        data = asdict(self)
        return data

    @staticmethod
    def from_dict(data: dict) -> 'PlayerProfile':
        """Create PlayerProfile from dictionary."""
        # Remove deprecated/unknown fields
        data.pop('achievements', None)  # Achievements feature was removed

        # Convert nested dataclasses
        if 'stats' in data and isinstance(data['stats'], dict):
            data['stats'] = ProfileStats(**data['stats'])

        if 'behavioral_stats' in data and isinstance(data['behavioral_stats'], dict):
            data['behavioral_stats'] = BehavioralStats(**data['behavioral_stats'])

        if 'hiding_stats' in data and isinstance(data['hiding_stats'], dict):
            hiding_data = data['hiding_stats']
            # Backward compatibility: migrate old field names to new ones
            if 'favorite_hiding_spots' in hiding_data:
                hiding_data['favorite_escape_options'] = hiding_data.pop('favorite_hiding_spots')
            if 'ai_detection_rate_by_spot' in hiding_data:
                hiding_data.pop('ai_detection_rate_by_spot')  # Remove deprecated field
            # Add default values for new fields that may be missing
            hiding_data.setdefault('total_escapes', 0)
            hiding_data.setdefault('favorite_escape_options', {})
            hiding_data.setdefault('escape_option_history', [])
            hiding_data.setdefault('ai_prediction_accuracy', 0.0)
            hiding_data.setdefault('ai_correct_predictions', 0)
            data['hiding_stats'] = HidingBehavioralStats(**hiding_data)
        elif 'hiding_stats' not in data:
            # Backward compatibility for old profiles without hiding stats
            data['hiding_stats'] = HidingBehavioralStats()

        if 'ai_memory' in data and isinstance(data['ai_memory'], dict):
            data['ai_memory'] = AIMemoryStats(**data['ai_memory'])

        if 'match_history' in data and isinstance(data['match_history'], list):
            data['match_history'] = [
                MatchHistoryEntry(**entry) if isinstance(entry, dict) else entry
                for entry in data['match_history']
            ]

        return PlayerProfile(**data)


@dataclass
class ProfileSummary:
    """Lightweight profile summary for list views."""
    profile_id: str
    name: str
    last_played: str
    total_games: int
    wins: int
    losses: int
    win_rate: float


class ProfileManager:
    """Singleton manager for player profiles."""

    _instance = None
    _profiles_dir = "data/profiles"
    _ai_models_dir = "data/profiles/ai_models"
    _index_file = "data/profiles/profiles_index.json"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProfileManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._ensure_directories()

    def _ensure_directories(self):
        """Create profile directories if they don't exist."""
        os.makedirs(self._profiles_dir, exist_ok=True)
        os.makedirs(self._ai_models_dir, exist_ok=True)

    def create_profile(self, name: str) -> PlayerProfile:
        """Create a new player profile."""
        now = datetime.now(timezone.utc).isoformat()

        profile = PlayerProfile(
            profile_id=str(uuid.uuid4()),
            name=name,
            created_date=now,
            last_played=now
        )

        self.save_profile(profile)
        self._update_index()

        return profile

    def load_profile(self, profile_id: str) -> Optional[PlayerProfile]:
        """Load a profile by ID."""
        profile_path = Path(self._profiles_dir) / f"{profile_id}.json"

        if not profile_path.exists():
            print(f"Warning: Profile {profile_id} not found")
            return None

        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return PlayerProfile.from_dict(data)
        except Exception as e:
            print(f"Error loading profile {profile_id}: {e}")
            return None

    def save_profile(self, profile: PlayerProfile) -> None:
        """Save a profile to disk."""
        profile_path = Path(self._profiles_dir) / f"{profile.profile_id}.json"

        try:
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving profile {profile.profile_id}: {e}")

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile and its AI model."""
        profile_path = Path(self._profiles_dir) / f"{profile_id}.json"
        model_path = Path(self._ai_models_dir) / f"{profile_id}_model.pkl"
        encoder_path = Path(self._ai_models_dir) / f"{profile_id}_encoder.pkl"

        try:
            if profile_path.exists():
                profile_path.unlink()
            if model_path.exists():
                model_path.unlink()
            if encoder_path.exists():
                encoder_path.unlink()

            self._update_index()
            return True
        except Exception as e:
            print(f"Error deleting profile {profile_id}: {e}")
            return False

    def list_all_profiles(self) -> List[ProfileSummary]:
        """List all profiles with summary information."""
        profiles = []
        profiles_dir = Path(self._profiles_dir)

        for profile_file in profiles_dir.glob("*.json"):
            if profile_file.stem == "profiles_index":
                continue

            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                summary = ProfileSummary(
                    profile_id=data['profile_id'],
                    name=data['name'],
                    last_played=data['last_played'],
                    total_games=data.get('stats', {}).get('total_games', 0),
                    wins=data.get('stats', {}).get('wins', 0),
                    losses=data.get('stats', {}).get('losses', 0),
                    win_rate=data.get('stats', {}).get('win_rate', 0.0)
                )
                profiles.append(summary)
            except Exception as e:
                print(f"Error reading profile {profile_file}: {e}")

        # Sort by last played (most recent first)
        profiles.sort(key=lambda p: p.last_played, reverse=True)
        return profiles

    def update_stats_after_game(self, profile_id: str, game_data: Dict[str, Any]) -> None:
        """Update profile stats after a game completes."""
        profile = self.load_profile(profile_id)
        if not profile:
            return

        # Update basic stats
        profile.stats.total_games += 1

        if game_data['outcome'] == 'win':
            profile.stats.wins += 1
        else:
            profile.stats.losses += 1

        profile.stats.update_win_rate()

        if game_data['final_score'] > profile.stats.highest_score:
            profile.stats.highest_score = game_data['final_score']

        profile.stats.total_points_earned += game_data['final_score']
        profile.stats.total_rounds_played += game_data['rounds_played']

        if game_data.get('caught', False):
            profile.stats.times_caught += 1

        # Update behavioral stats
        self._update_behavioral_stats(profile, game_data)

        # Update hiding stats
        self._update_hiding_stats(profile, game_data)

        # Update match history (ring buffer - keep last 10)
        match_entry = MatchHistoryEntry(
            game_id=game_data.get('game_id', str(uuid.uuid4())),
            date=datetime.now(timezone.utc).isoformat(),
            outcome=game_data['outcome'],
            final_score=game_data['final_score'],
            rounds_played=game_data['rounds_played'],
            caught=game_data.get('caught', False),
            num_opponents=game_data.get('num_opponents', 1),
            escapes_in_game=game_data.get('escapes_in_game', 0),
            high_threat_escape=game_data.get('high_threat_escape', False)
        )

        profile.match_history.append(match_entry)

        # Keep only last 10 games
        if len(profile.match_history) > 10:
            profile.match_history = profile.match_history[-10:]

        # Update last played
        profile.last_played = datetime.now(timezone.utc).isoformat()

        # Save updated profile
        self.save_profile(profile)
        self._update_index()

        # Train per-player model at milestones (5, 10, 15, 20 games)
        if profile.stats.total_games in [5, 10, 15, 20]:
            self._train_player_model(profile_id)

    def _train_player_model(self, profile_id: str) -> None:
        """Train a per-player AI model for this profile."""
        try:
            from ai.player_predictor import PlayerPredictor

            predictor = PlayerPredictor(profile_id, self._profiles_dir.replace('/profiles', ''))
            success = predictor.train_personal_model(min_samples=10)

            if success:
                print(f"[dim green]Trained personal AI model for profile {profile_id}[/dim green]")
            else:
                print(f"[dim yellow]Could not train model for profile {profile_id} yet[/dim yellow]")

        except Exception as e:
            print(f"[dim red]Error training personal model: {e}[/dim red]")

    def _update_behavioral_stats(self, profile: PlayerProfile, game_data: Dict[str, Any]) -> None:
        """Update behavioral patterns from game data."""
        locations_chosen = game_data.get('locations_chosen', [])

        # Update location frequencies
        for location in locations_chosen:
            if location in profile.behavioral_stats.location_frequencies:
                profile.behavioral_stats.location_frequencies[location] += 1
            else:
                profile.behavioral_stats.location_frequencies[location] = 1

        # Determine favorite location
        if profile.behavioral_stats.location_frequencies:
            profile.behavioral_stats.favorite_location = max(
                profile.behavioral_stats.location_frequencies,
                key=profile.behavioral_stats.location_frequencies.get
            )

        # Update item usage
        items_used = game_data.get('items_used', [])
        for item in items_used:
            if item in profile.behavioral_stats.item_usage:
                profile.behavioral_stats.item_usage[item] += 1
            else:
                profile.behavioral_stats.item_usage[item] = 1

        # Calculate predictability score (simplified for now)
        # Higher variance in location choices = lower predictability
        if len(profile.behavioral_stats.location_frequencies) > 0:
            total_choices = sum(profile.behavioral_stats.location_frequencies.values())
            if total_choices > 0:
                # Calculate entropy-based predictability
                max_freq = max(profile.behavioral_stats.location_frequencies.values())
                profile.behavioral_stats.predictability_score = max_freq / total_choices

    def _update_hiding_stats(self, profile: PlayerProfile, game_data: Dict[str, Any]) -> None:
        """Update escape patterns from game data (prediction-based system)."""
        hiding_data = game_data.get('hiding_data', {})

        if not hiding_data:
            # No hiding data in this game (backward compatibility)
            return

        # Update totals
        profile.hiding_stats.total_caught_instances += hiding_data.get('total_caught_instances', 0)
        profile.hiding_stats.total_escapes += hiding_data.get('total_escapes', 0)
        profile.hiding_stats.hide_attempts += hiding_data.get('hide_attempts', 0)
        profile.hiding_stats.run_attempts += hiding_data.get('run_attempts', 0)

        # Update escape option frequencies (new system)
        escape_options = hiding_data.get('favorite_escape_options', {})
        for option_id, count in escape_options.items():
            if option_id in profile.hiding_stats.favorite_escape_options:
                profile.hiding_stats.favorite_escape_options[option_id] += count
            else:
                profile.hiding_stats.favorite_escape_options[option_id] = count

        # Add to escape option history (keep last 20 for recency-weighted prediction)
        new_history = hiding_data.get('escape_option_history', [])
        profile.hiding_stats.escape_option_history.extend(new_history)
        profile.hiding_stats.escape_option_history = profile.hiding_stats.escape_option_history[-20:]

        # Update AI prediction accuracy
        ai_correct = hiding_data.get('ai_correct_predictions', 0)
        profile.hiding_stats.ai_correct_predictions += ai_correct
        if profile.hiding_stats.total_caught_instances > 0:
            profile.hiding_stats.ai_prediction_accuracy = (
                profile.hiding_stats.ai_correct_predictions /
                profile.hiding_stats.total_caught_instances
            )

        # Calculate success rates
        if profile.hiding_stats.hide_attempts > 0:
            successful_hides = hiding_data.get('successful_hides', 0)
            prev_hide_attempts = profile.hiding_stats.hide_attempts - hiding_data.get('hide_attempts', 0)
            total_successful_hides = profile.hiding_stats.hide_success_rate * prev_hide_attempts
            total_successful_hides += successful_hides
            profile.hiding_stats.hide_success_rate = total_successful_hides / profile.hiding_stats.hide_attempts

        if profile.hiding_stats.run_attempts > 0:
            successful_runs = hiding_data.get('successful_runs', 0)
            prev_run_attempts = profile.hiding_stats.run_attempts - hiding_data.get('run_attempts', 0)
            total_successful_runs = profile.hiding_stats.run_success_rate * prev_run_attempts
            total_successful_runs += successful_runs
            profile.hiding_stats.run_success_rate = total_successful_runs / profile.hiding_stats.run_attempts

        # Determine risk profile when caught
        total_attempts = profile.hiding_stats.hide_attempts + profile.hiding_stats.run_attempts
        if total_attempts >= 5:
            hide_ratio = profile.hiding_stats.hide_attempts / total_attempts
            if hide_ratio >= 0.7:
                profile.hiding_stats.risk_profile_when_caught = "aggressive_hider"
            elif hide_ratio <= 0.3:
                profile.hiding_stats.risk_profile_when_caught = "runner"
            else:
                profile.hiding_stats.risk_profile_when_caught = "balanced"

    def _update_index(self) -> None:
        """Update the profiles index file for fast lookups."""
        summaries = self.list_all_profiles()
        index_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_profiles": len(summaries),
            "profiles": [
                {
                    "id": s.profile_id,
                    "name": s.name,
                    "last_played": s.last_played,
                    "games": s.total_games
                }
                for s in summaries
            ]
        }

        try:
            with open(self._index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error updating profiles index: {e}")

    def get_location_preferences(self, profile: PlayerProfile) -> Dict[str, float]:
        """Get normalized location preference scores."""
        if not profile.behavioral_stats.location_frequencies:
            return {}

        total = sum(profile.behavioral_stats.location_frequencies.values())
        if total == 0:
            return {}

        return {
            location: count / total
            for location, count in profile.behavioral_stats.location_frequencies.items()
        }

    def get_play_style(self, profile: PlayerProfile) -> str:
        """Determine player's play style based on behavioral stats."""
        # Aggressive: High predictability, favors high-value locations
        # Conservative: Low risk, avoids getting caught often
        # Unpredictable: Low predictability score

        if profile.stats.total_games < 3:
            return "neutral"

        predictability = profile.behavioral_stats.predictability_score

        if predictability < 0.4:
            return "unpredictable"
        elif profile.stats.times_caught / max(profile.stats.total_games, 1) > 0.5:
            return "aggressive"
        else:
            return "conservative"

    def migrate_legacy_games(self) -> Dict[str, Any]:
        """
        Migrate existing game_history.json to profile system.

        Creates profiles from unique player names and links historical games.

        Returns:
            Dict with migration statistics
        """
        history_file = os.path.join(self._profiles_dir.replace('/profiles', ''), 'game_history.json')

        if not os.path.exists(history_file):
            return {'error': 'No game_history.json found', 'profiles_created': 0, 'games_migrated': 0}

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
        except Exception as e:
            return {'error': f'Failed to load game_history.json: {e}', 'profiles_created': 0, 'games_migrated': 0}

        games = history_data.get('games', [])

        # Step 1: Extract unique player names
        player_names = set()
        for game in games:
            for player_data in game.get('players', []):
                player_names.add(player_data['name'])

        # Step 2: Create profiles for each unique name (or load if exists)
        name_to_profile = {}
        profiles_created = 0

        for name in player_names:
            # Check if profile already exists by name
            existing_profiles = self.list_all_profiles()
            existing = next((p for p in existing_profiles if p.name == name), None)

            if existing:
                profile = self.load_profile(existing.profile_id)
                name_to_profile[name] = profile
            else:
                profile = self.create_profile(name)
                name_to_profile[name] = profile
                profiles_created += 1

        # Step 3: Migrate games and update profiles
        games_migrated = 0

        for game in games:
            # Add game_id and timestamp if missing
            if 'game_id' not in game:
                game['game_id'] = str(uuid.uuid4())
            if 'timestamp' not in game:
                # Use a default historical date
                game['timestamp'] = datetime(2025, 12, 1, tzinfo=timezone.utc).isoformat()
            if 'winner_profile_id' not in game:
                winner_name = game.get('winner')
                if winner_name and winner_name in name_to_profile:
                    game['winner_profile_id'] = name_to_profile[winner_name].profile_id
                else:
                    game['winner_profile_id'] = None

            # Add profile_id to each player and update their profile
            for player_data in game.get('players', []):
                player_name = player_data['name']

                if player_name not in name_to_profile:
                    continue

                profile = name_to_profile[player_name]

                # Add profile_id to player data
                if 'profile_id' not in player_data:
                    player_data['profile_id'] = profile.profile_id

                # Update profile stats from this game
                outcome = 'win' if game.get('winner') == player_name else 'loss'
                caught = not player_data.get('alive', True)

                game_data = {
                    'game_id': game['game_id'],
                    'outcome': outcome,
                    'final_score': player_data.get('final_points', 0),
                    'rounds_played': player_data.get('rounds_survived', 0),
                    'caught': caught,
                    'num_opponents': game.get('num_players', 2) - 1,
                    'locations_chosen': player_data.get('choice_history', []),
                    'items_used': []  # Legacy games don't track items
                }

                # Update profile (without triggering model training)
                self.update_stats_after_game(profile.profile_id, game_data)

            games_migrated += 1

        # Step 4: Save updated game_history.json
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, indent=2)
        except Exception as e:
            return {
                'error': f'Failed to save migrated game_history.json: {e}',
                'profiles_created': profiles_created,
                'games_migrated': games_migrated
            }

        return {
            'success': True,
            'profiles_created': profiles_created,
            'total_profiles': len(name_to_profile),
            'games_migrated': games_migrated,
            'player_names': list(player_names)
        }
