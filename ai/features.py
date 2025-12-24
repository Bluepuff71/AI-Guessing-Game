"""Feature extraction for ML model."""
from typing import Dict, Any, List
from game.player import Player
from game.locations import LocationManager


def extract_features(player: Player, round_num: int, num_players_alive: int,
                    location_manager: LocationManager) -> Dict[str, Any]:
    """
    Extract features from player state for ML prediction.

    Returns a dictionary of features that describe player behavior and context.
    """
    features = {}

    # Current state features
    features['current_score'] = player.points
    features['round_number'] = round_num
    features['players_alive'] = num_players_alive

    # Score context
    features['points_to_win'] = max(0, 100 - player.points)
    features['win_threat'] = 1.0 if player.points >= 80 else player.points / 100.0

    # Get behavior summary
    behavior = player.get_behavior_summary()

    # Behavioral features
    features['avg_location_value'] = behavior['avg_location_value']
    features['choice_variety'] = behavior['choice_variety']
    features['high_value_preference'] = behavior['high_value_preference']
    features['total_choices'] = behavior['total_choices']

    # Item features
    active_items = player.get_active_items()
    features['has_shield'] = any(item.name == "Shield" for item in active_items)
    features['has_scanner'] = any(item.name == "Scanner" for item in active_items)
    features['has_lucky_charm'] = any(item.name == "Lucky Charm" for item in active_items)
    features['num_items'] = len(active_items)

    # Recent history features (last 3 choices)
    recent_choices = player.choice_history[-3:] if len(player.choice_history) >= 3 else player.choice_history
    features['recent_choice_count'] = len(recent_choices)

    # Calculate recent trends
    if len(player.round_history) >= 2:
        recent_rounds = player.round_history[-3:]
        recent_values = [r['location_value'] for r in recent_rounds]
        features['recent_avg_value'] = sum(recent_values) / len(recent_values)

        # Trend: increasing, decreasing, or stable
        if len(recent_values) >= 2:
            if recent_values[-1] > recent_values[0] + 5:
                features['risk_trend'] = 1  # Increasing
            elif recent_values[-1] < recent_values[0] - 5:
                features['risk_trend'] = -1  # Decreasing
            else:
                features['risk_trend'] = 0  # Stable
        else:
            features['risk_trend'] = 0
    else:
        features['recent_avg_value'] = 0
        features['risk_trend'] = 0

    # Location frequency features (simplified - just track high-value location preference)
    if behavior['location_frequencies']:
        high_value_locations = ['Bank Vault', 'Jewelry Store', 'Electronics Store']
        high_value_count = sum(behavior['location_frequencies'].get(loc, 0)
                              for loc in high_value_locations)
        features['high_value_location_frequency'] = (
            high_value_count / features['total_choices'] if features['total_choices'] > 0 else 0
        )
    else:
        features['high_value_location_frequency'] = 0

    return features


def calculate_predictability(player: Player) -> float:
    """
    Calculate how predictable a player's behavior is (0-1 scale).

    Higher values = more predictable
    """
    if len(player.choice_history) < 3:
        return 0.3  # Not enough data, assume moderate

    behavior = player.get_behavior_summary()

    # Factors that increase predictability:
    # 1. Low variety (visiting same locations repeatedly)
    variety_score = behavior['choice_variety']  # 0-1, lower = less variety

    # 2. Strong preference for high or low value
    value_preference = abs(behavior['high_value_preference'] - 0.5) * 2  # 0-1

    # 3. Consistent patterns in recent choices
    recent_choices = player.choice_history[-5:]
    unique_recent = len(set(recent_choices))
    pattern_score = 1.0 - (unique_recent / min(5, len(recent_choices)))

    # Combine factors
    predictability = (
        (1.0 - variety_score) * 0.4 +  # 40% weight on variety
        value_preference * 0.3 +         # 30% weight on value preference
        pattern_score * 0.3              # 30% weight on recent patterns
    )

    return min(1.0, max(0.0, predictability))


def generate_insights(player: Player) -> Dict[str, Any]:
    """Generate insights about player behavior for post-game reports."""
    insights = {
        'predictability': calculate_predictability(player),
        'patterns': [],
        'tips': []
    }

    if len(player.choice_history) < 3:
        insights['patterns'].append("Not enough data to identify patterns")
        return insights

    behavior = player.get_behavior_summary()

    # Identify patterns
    if behavior['high_value_preference'] > 0.7:
        insights['patterns'].append(
            f"High-value bias: You picked 15+ point locations {behavior['high_value_preference']:.0%} of the time"
        )
        insights['tips'].append("Mix in more low-value locations to become less predictable")

    if behavior['choice_variety'] < 0.5:
        insights['patterns'].append(
            f"Limited variety: Only visited {int(behavior['choice_variety'] * 8)} of 8 locations"
        )
        insights['tips'].append("Visit all locations to establish less predictable patterns")

    # Check for favorite locations
    if behavior['location_frequencies']:
        sorted_locs = sorted(behavior['location_frequencies'].items(),
                           key=lambda x: x[1], reverse=True)
        if sorted_locs[0][1] >= 3 and sorted_locs[0][1] / len(player.choice_history) > 0.3:
            insights['patterns'].append(
                f"Favorite location: {sorted_locs[0][0]} ({sorted_locs[0][1]} times)"
            )
            insights['tips'].append(f"Avoid over-relying on {sorted_locs[0][0]}")

    # Check for win-rush behavior
    if player.points >= 80:
        late_game_choices = player.round_history[-3:] if len(player.round_history) >= 3 else player.round_history
        late_game_avg = sum(r['location_value'] for r in late_game_choices) / len(late_game_choices) if late_game_choices else 0

        if late_game_avg > 20:
            insights['patterns'].append(
                "Win-rush detected: Became aggressive when close to winning"
            )
            insights['tips'].append("Consider safer choices when close to 100 points")

    return insights
