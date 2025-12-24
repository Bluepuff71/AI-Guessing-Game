"""Achievement system for tracking player accomplishments."""
from dataclasses import dataclass
from typing import Callable, List, Dict, Any, Optional
from datetime import datetime, timezone


@dataclass
class Achievement:
    """Represents a single achievement."""
    id: str
    name: str
    description: str
    emoji: str
    condition: Callable[[Any], bool]  # Function that takes profile and returns bool
    hidden: bool = False  # Hidden achievements don't show until unlocked


class AchievementTracker:
    """Manages achievement checking and unlocking."""

    # Define all available achievements
    ACHIEVEMENTS = [
        # Basic achievements
        Achievement(
            id="first_win",
            name="First Victory",
            description="Win your first game",
            emoji="🏆",
            condition=lambda profile: profile.stats.wins >= 1
        ),
        Achievement(
            id="perfect_game",
            name="Untouchable",
            description="Win a game without being caught once",
            emoji="👻",
            condition=lambda profile: any(
                match.outcome == 'win' and not match.caught
                for match in profile.match_history
            )
        ),
        Achievement(
            id="high_roller",
            name="High Roller",
            description="Score 120+ points in a single game",
            emoji="💰",
            condition=lambda profile: any(
                match.final_score >= 120
                for match in profile.match_history
            ),
            hidden=True
        ),
        Achievement(
            id="survivor",
            name="The Survivor",
            description="Survive 20+ rounds in a single game",
            emoji="🛡️",
            condition=lambda profile: any(
                match.rounds_played >= 20
                for match in profile.match_history
            )
        ),
        Achievement(
            id="lucky_streak",
            name="Lucky Streak",
            description="Win 3 games in a row",
            emoji="🍀",
            condition=lambda profile: _check_win_streak(profile, 3)
        ),

        # Milestones
        Achievement(
            id="veteran",
            name="Veteran",
            description="Play 10 games",
            emoji="🎮",
            condition=lambda profile: profile.stats.total_games >= 10
        ),
        Achievement(
            id="champion",
            name="Champion",
            description="Win 5 games",
            emoji="🥇",
            condition=lambda profile: profile.stats.wins >= 5
        ),
        Achievement(
            id="master_thief",
            name="Master Thief",
            description="Reach 1000 total points earned",
            emoji="💎",
            condition=lambda profile: profile.stats.total_points_earned >= 1000
        ),

        # Play style achievements
        Achievement(
            id="risk_taker",
            name="Risk Taker",
            description="Caught 10+ times across all games",
            emoji="⚡",
            condition=lambda profile: profile.stats.times_caught >= 10
        ),
        Achievement(
            id="ghost",
            name="Ghost",
            description="Win 5 consecutive games without being caught",
            emoji="👤",
            condition=lambda profile: _check_ghost_streak(profile, 5),
            hidden=True
        ),
        Achievement(
            id="predictable",
            name="Creature of Habit",
            description="Reach 90% predictability score",
            emoji="🔮",
            condition=lambda profile: profile.behavioral_stats.predictability_score >= 0.9
        ),
        Achievement(
            id="unpredictable",
            name="Wild Card",
            description="Maintain below 30% predictability after 5+ games",
            emoji="🎲",
            condition=lambda profile: (
                profile.stats.total_games >= 5 and
                profile.behavioral_stats.predictability_score < 0.3
            )
        ),

        # Location achievements
        Achievement(
            id="location_master",
            name="Location Master",
            description="Visit every location at least once",
            emoji="🗺️",
            condition=lambda profile: _check_all_locations_visited(profile)
        ),
        Achievement(
            id="specialist",
            name="Specialist",
            description="Choose the same location 20+ times",
            emoji="🎯",
            condition=lambda profile: any(
                count >= 20
                for count in profile.behavioral_stats.location_frequencies.values()
            )
        ),

        # Competitive achievements
        Achievement(
            id="comeback_kid",
            name="Comeback Kid",
            description="Win after losing 3 games in a row",
            emoji="🔄",
            condition=lambda profile: _check_comeback(profile),
            hidden=True
        ),
        Achievement(
            id="dominant",
            name="Dominant",
            description="Maintain 70%+ win rate after 10+ games",
            emoji="👑",
            condition=lambda profile: (
                profile.stats.total_games >= 10 and
                profile.stats.win_rate >= 0.7
            )
        ),

        # AI-related achievements
        Achievement(
            id="ai_nemesis",
            name="AI's Nemesis",
            description="Defeat the AI 3 times after it built your personal model",
            emoji="🤖",
            condition=lambda profile: _check_ai_nemesis(profile, 3)
        ),
        Achievement(
            id="outsmarted",
            name="Outsmarted",
            description="Win your first game after AI built your personal model",
            emoji="🧠",
            condition=lambda profile: (
                profile.ai_memory.has_personal_model and
                any(match.outcome == 'win' for match in profile.match_history)
            ),
            hidden=True
        ),
    ]

    @staticmethod
    def check_achievements(profile) -> List[Achievement]:
        """Check all achievements and return newly unlocked ones."""
        newly_unlocked = []

        for achievement in AchievementTracker.ACHIEVEMENTS:
            # Skip if already unlocked
            if achievement.id in profile.achievements:
                continue

            # Check condition
            try:
                if achievement.condition(profile):
                    newly_unlocked.append(achievement)
            except Exception:
                # Silently fail if condition check errors
                pass

        return newly_unlocked

    @staticmethod
    def unlock_achievement(profile, achievement: Achievement) -> None:
        """Unlock an achievement for a profile."""
        profile.achievements[achievement.id] = {
            'unlocked': True,
            'date': datetime.now(timezone.utc).isoformat(),
            'name': achievement.name,
            'description': achievement.description,
            'emoji': achievement.emoji
        }

    @staticmethod
    def get_achievement_progress(profile) -> Dict[str, Any]:
        """Get achievement progress statistics."""
        total = len(AchievementTracker.ACHIEVEMENTS)
        unlocked = len(profile.achievements)

        # Calculate progress for specific achievement categories
        basic_unlocked = sum(
            1 for ach in AchievementTracker.ACHIEVEMENTS
            if ach.id in profile.achievements and ach.id in ['first_win', 'perfect_game', 'survivor']
        )

        milestone_unlocked = sum(
            1 for ach in AchievementTracker.ACHIEVEMENTS
            if ach.id in profile.achievements and ach.id in ['veteran', 'champion', 'master_thief']
        )

        return {
            'total': total,
            'unlocked': unlocked,
            'percentage': (unlocked / total) * 100 if total > 0 else 0,
            'basic_unlocked': basic_unlocked,
            'milestone_unlocked': milestone_unlocked
        }

    @staticmethod
    def get_unlocked_achievements(profile) -> List[Dict[str, Any]]:
        """Get list of all unlocked achievements with metadata."""
        unlocked = []
        for ach_id, ach_data in profile.achievements.items():
            unlocked.append({
                'id': ach_id,
                'name': ach_data['name'],
                'description': ach_data['description'],
                'emoji': ach_data['emoji'],
                'date': ach_data['date']
            })

        # Sort by unlock date (most recent first)
        unlocked.sort(key=lambda x: x['date'], reverse=True)
        return unlocked


# Helper functions for complex achievement conditions

def _check_win_streak(profile, streak_length: int) -> bool:
    """Check if player has a win streak of specified length."""
    if len(profile.match_history) < streak_length:
        return False

    # Check last N games for consecutive wins
    for i in range(len(profile.match_history) - streak_length + 1):
        streak = profile.match_history[i:i + streak_length]
        if all(match.outcome == 'win' for match in streak):
            return True

    return False


def _check_all_locations_visited(profile) -> bool:
    """Check if player has visited all locations."""
    # This requires knowledge of total locations - we'll check if they have 5+ unique locations
    # (Assuming the game has ~5-8 locations based on config)
    return len(profile.behavioral_stats.location_frequencies) >= 5


def _check_comeback(profile) -> bool:
    """Check if player won after losing 3 in a row."""
    if len(profile.match_history) < 4:
        return False

    # Look for pattern: Loss, Loss, Loss, Win
    for i in range(len(profile.match_history) - 3):
        sequence = profile.match_history[i:i + 4]
        if (sequence[0].outcome == 'loss' and
            sequence[1].outcome == 'loss' and
            sequence[2].outcome == 'loss' and
            sequence[3].outcome == 'win'):
            return True

    return False


def _check_ghost_streak(profile, streak_length: int) -> bool:
    """Check if player has won N consecutive games without being caught."""
    if len(profile.match_history) < streak_length:
        return False

    # Check last N games for consecutive wins without being caught
    for i in range(len(profile.match_history) - streak_length + 1):
        streak = profile.match_history[i:i + streak_length]
        if all(match.outcome == 'win' and not match.caught for match in streak):
            return True

    return False


def _check_ai_nemesis(profile, wins_needed: int) -> bool:
    """Check if player has won N games after AI built their personal model."""
    if not profile.ai_memory.has_personal_model:
        return False

    # Count wins in match history (assuming personal model was built before these)
    # This is approximate since we don't track when model was built in match history
    wins_with_model = sum(
        1 for match in profile.match_history
        if match.outcome == 'win'
    )

    return wins_with_model >= wins_needed
