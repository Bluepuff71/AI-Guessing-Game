"""Feature extraction for ML model."""
from typing import Dict, Any, List
from game.player import Player
from game.locations import LocationManager
from game.config_loader import config


def extract_features(player: Player, round_num: int, num_players_alive: int,
                    location_manager: LocationManager, event_manager=None) -> Dict[str, Any]:
    """
    Extract features from player state for ML prediction.

    Args:
        player: Player to extract features for
        round_num: Current round number
        num_players_alive: Number of alive players
        location_manager: LocationManager instance
        event_manager: Optional EventManager to extract event features

    Returns a dictionary of features that describe player behavior and context.
    """
    features = {}
    win_threshold = config.get('game', 'win_threshold', default=100)

    # Current state features
    features['current_score'] = player.points
    features['round_number'] = round_num
    features['players_alive'] = num_players_alive

    # Score context
    features['points_to_win'] = max(0, win_threshold - player.points)
    win_proximity_threshold = int(win_threshold * 0.8)  # 80% of win threshold
    features['win_threat'] = 1.0 if player.points >= win_proximity_threshold else player.points / win_threshold

    # Get behavior summary
    behavior = player.get_behavior_summary()

    # Behavioral features
    features['avg_location_value'] = behavior['avg_location_value']
    features['choice_variety'] = behavior['choice_variety']
    features['high_value_preference'] = behavior['high_value_preference']
    features['total_choices'] = behavior['total_choices']

    # Passive features (replaces old items system)
    from game.passives import PassiveType
    passives = player.get_passives()
    features['num_passives'] = len(passives)

    # Track specific passives that affect player behavior
    features['has_high_roller'] = player.has_passive(PassiveType.HIGH_ROLLER)
    features['has_escape_artist'] = player.has_passive(PassiveType.ESCAPE_ARTIST)
    features['has_shadow_walker'] = player.has_passive(PassiveType.SHADOW_WALKER)
    features['has_quick_feet'] = player.has_passive(PassiveType.QUICK_FEET)
    features['has_ai_whisperer'] = player.has_passive(PassiveType.AI_WHISPERER)
    features['has_inside_knowledge'] = player.has_passive(PassiveType.INSIDE_KNOWLEDGE)

    # Event features (game dynamics)
    if event_manager:
        features['num_active_events'] = len(event_manager.active_events)

        # Check for specific event types across all locations
        has_immunity = False
        has_catch = False
        max_point_modifier = 1.0
        min_point_modifier = 1.0

        for event in event_manager.active_events:
            if event.special_effect == "immunity":
                has_immunity = True
            elif event.special_effect == "guaranteed_catch":
                has_catch = True

            # Track point modifiers if they exist
            if event.point_modifier:
                # Test the modifier with a sample value to see effect
                test_val = event.apply_point_modifier(10)
                modifier_ratio = test_val / 10.0
                max_point_modifier = max(max_point_modifier, modifier_ratio)
                min_point_modifier = min(min_point_modifier, modifier_ratio)

        features['has_immunity_event'] = 1 if has_immunity else 0
        features['has_catch_event'] = 1 if has_catch else 0
        features['max_event_point_modifier'] = max_point_modifier
        features['min_event_point_modifier'] = min_point_modifier
    else:
        # No event manager, use default values
        features['num_active_events'] = 0
        features['has_immunity_event'] = 0
        features['has_catch_event'] = 0
        features['max_event_point_modifier'] = 1.0
        features['min_event_point_modifier'] = 1.0

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


def generate_insights(player: Player, num_locations: int = 5) -> Dict[str, Any]:
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
        locations_visited = int(behavior['choice_variety'] * num_locations)
        insights['patterns'].append(
            f"Limited variety: Only visited {locations_visited} of {num_locations} locations"
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
    win_threshold = config.get('game', 'win_threshold', default=100)
    win_proximity_threshold = int(win_threshold * 0.8)  # 80% of win threshold

    if player.points >= win_proximity_threshold:
        late_game_choices = player.round_history[-3:] if len(player.round_history) >= 3 else player.round_history
        late_game_avg = sum(r['location_value'] for r in late_game_choices) / len(late_game_choices) if late_game_choices else 0

        if late_game_avg > 20:
            insights['patterns'].append(
                "Win-rush detected: Became aggressive when close to winning"
            )
            insights['tips'].append(f"Consider safer choices when close to {win_threshold} points")

    # Hiding/escape behavior analysis
    if hasattr(player, 'hide_run_history') and len(player.hide_run_history) > 0:
        total_attempts = len(player.hide_run_history)
        successful_escapes = sum(1 for attempt in player.hide_run_history if attempt.get('escaped', False))
        escape_rate = successful_escapes / total_attempts if total_attempts > 0 else 0

        hide_attempts = player.hiding_stats['total_hide_attempts']
        run_attempts = player.hiding_stats['total_run_attempts']

        # Overall escape performance
        if escape_rate >= 0.8:
            insights['patterns'].append(f"Escape master: {escape_rate:.0%} escape success rate ({successful_escapes}/{total_attempts})")
        elif escape_rate <= 0.3:
            insights['patterns'].append(f"Caught often: Only {escape_rate:.0%} escape success rate ({successful_escapes}/{total_attempts})")
            insights['tips'].append("Try varying your hiding spots and mixing hide/run choices")

        # Hide vs run preference
        if total_attempts >= 3:
            if hide_attempts > run_attempts * 2:
                insights['patterns'].append(f"Hide preference: Chose to hide {hide_attempts} times vs run {run_attempts} times")
                if player.hiding_stats['hide_vs_run_ratio'] > 0.8:
                    insights['tips'].append("AI is learning your hiding patterns - consider running occasionally")
            elif run_attempts > hide_attempts * 2:
                insights['patterns'].append(f"Runner: Chose to run {run_attempts} times vs hide {hide_attempts} times")
                if player.hiding_stats['hide_vs_run_ratio'] < 0.2:
                    insights['tips'].append("Running is risky - hiding might improve your survival rate")

        # Favorite hiding spots
        if player.hiding_stats['favorite_hide_spots']:
            sorted_spots = sorted(player.hiding_stats['favorite_hide_spots'].items(),
                                key=lambda x: x[1], reverse=True)
            if sorted_spots[0][1] >= 2:
                spot_id = sorted_spots[0][0]
                count = sorted_spots[0][1]
                insights['patterns'].append(f"Favorite hiding spot: {spot_id} (used {count} times)")
                if count >= 3:
                    insights['tips'].append("AI learns your favorite spots - vary your hiding locations")

    return insights


def extract_hiding_features(player: Player) -> Dict[str, float]:
    """
    Extract features related to hiding/running behavior for AI learning.

    Args:
        player: Player to extract hiding features for

    Returns:
        Dict of hiding-related features for AI prediction
    """
    if not hasattr(player, 'hiding_stats'):
        # Player has no hiding history yet
        return {
            'hide_vs_run_ratio': 0.5,  # Default: no preference
            'hide_success_rate': 0.0,
            'run_success_rate': 0.0,
            'total_escape_attempts': 0,
            'predictability_when_caught': 0.5
        }

    stats = player.hiding_stats
    total_attempts = stats['total_hide_attempts'] + stats['total_run_attempts']

    return {
        'hide_vs_run_ratio': (
            stats['total_hide_attempts'] / total_attempts
            if total_attempts > 0 else 0.5
        ),
        'hide_success_rate': (
            stats['successful_hides'] / stats['total_hide_attempts']
            if stats['total_hide_attempts'] > 0 else 0.0
        ),
        'run_success_rate': (
            stats['successful_runs'] / stats['total_run_attempts']
            if stats['total_run_attempts'] > 0 else 0.0
        ),
        'total_escape_attempts': total_attempts,
        'predictability_when_caught': calculate_hide_predictability(player)
    }


def calculate_hide_predictability(player: Player) -> float:
    """
    Calculate how predictable a player's hiding choices are (0-1 scale).

    Higher values = more predictable (easier for AI to catch)

    Considers:
    - Favorite hiding spots (spot predictability)
    - Hide vs run tendency (choice predictability)

    Args:
        player: Player to analyze

    Returns:
        Predictability score (0.0-1.0)
    """
    if not hasattr(player, 'hiding_stats'):
        return 0.5  # Default: moderate predictability

    stats = player.hiding_stats

    # Calculate spot predictability
    if stats['favorite_hide_spots']:
        total = sum(stats['favorite_hide_spots'].values())
        if total > 0:
            most_common_count = max(stats['favorite_hide_spots'].values())
            spot_predictability = most_common_count / total
        else:
            spot_predictability = 0.5
    else:
        spot_predictability = 0.5

    # Calculate choice predictability (hide vs run bias)
    total_attempts = stats['total_hide_attempts'] + stats['total_run_attempts']
    if total_attempts >= 3:
        hide_ratio = stats['total_hide_attempts'] / total_attempts
        # Closer to 0.5 = more unpredictable, closer to 0 or 1 = predictable
        choice_unpredictability = 1.0 - abs(hide_ratio - 0.5) * 2
        choice_predictability = 1.0 - choice_unpredictability
    else:
        choice_predictability = 0.5

    # Combine factors (spot patterns are more important)
    predictability = (spot_predictability * 0.6 + choice_predictability * 0.4)

    return min(1.0, max(0.0, predictability))
