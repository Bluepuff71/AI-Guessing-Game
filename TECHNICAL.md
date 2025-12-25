# LOOT RUN - Technical Reference

## Project Structure

```
Xmas Game/
├── game/
│   ├── __init__.py
│   ├── engine.py          # Main game loop
│   ├── player.py          # Player class with history tracking
│   ├── locations.py       # 8 locations with dynamic values
│   ├── items.py           # Strategic items
│   └── ui.py              # Rich terminal UI
├── ai/
│   ├── __init__.py
│   ├── predictor.py       # AI prediction (baseline + ML)
│   ├── features.py        # Feature extraction & analysis
│   └── trainer.py         # LightGBM model training
├── data/                  # Auto-created
│   ├── game_history.json  # All games played
│   ├── model.pkl          # Trained LightGBM model
│   └── label_encoder.pkl  # Location encoder
├── main.py               # Game entry point
├── test_game.py          # Component tests
└── test_ml.py            # ML pipeline tests
```

## Two-Tier AI System

### Tier 1: Baseline AI (Always Active)

| Rounds | Strategy | Confidence |
|--------|----------|------------|
| 1-3 | Random predictions | 12.5% (1/8 chance) |
| 4-6 | Recency-weighted frequency analysis | Based on pattern strength |
| 7+ | Advanced behavioral heuristics | Multi-factor scoring |

### Tier 2: ML-Enhanced AI (After 2+ Games)

- **Model:** LightGBM Gradient Boosted Decision Trees
- **Training Data:** Every player choice ever made
- **Output:** Probability distribution over 8 locations
- **Minimum samples:** 20 (typically 2-3 games)

## Feature Engineering (17 Features)

### State Features (3)
| Feature | Description |
|---------|-------------|
| `current_score` | Player's current points |
| `points_to_win` | 100 - current_score |
| `round_number` | Current round |

### Historical Behavior (8)
| Feature | Description |
|---------|-------------|
| `avg_location_value` | Average points of chosen locations |
| `recent_avg_value` | Average of last 3 choices |
| `choice_variance` | Consistency of choices |
| `high_value_preference` | % of times picking 15+ point locations |
| `unique_locations_visited` | How many different spots (0-8) |
| `total_rounds_played` | Experience level |
| `risk_trend` | Getting more/less aggressive (-1, 0, 1) |
| `times_caught` | Elimination count |

### Item Features (1)
| Feature | Description |
|---------|-------------|
| `num_items` | Current item count |

### Event Features (5)
| Feature | Description |
|---------|-------------|
| `num_active_events` | Count of active events |
| `has_immunity_event` | Immunity event active |
| `has_catch_event` | Guaranteed catch event active |
| `max_event_point_modifier` | Highest point modifier |
| `min_event_point_modifier` | Lowest point modifier |

## Training Pipeline

1. **Data Collection:** Every choice saved to `game_history.json`
2. **Feature Extraction:** Convert choices to feature vectors
3. **Label Encoding:** Location names → integers
4. **Model Training:** LightGBM with 100 boosting rounds
5. **Model Saving:** Persist to `model.pkl`

**Training triggers:**
- Initial training after 2+ games
- Automatic retraining every 5 games

## Prediction Flow

1. **Extract features** from current player state
2. **Model inference** produces location probabilities
3. **Softmax selection** with dynamic temperature picks search location
4. **Threat calculation** combines probability × win threat

### Dynamic Temperature

```
base_temp = 0.5
if max_impact < 2 * avg_impact: temp += 0.3  # Explore if impacts similar
if player_score > 85: temp -= 0.2            # Exploit near victory
if rounds_since_catch > 3: temp += 0.2       # Explore if cold streak
temp = clamp(temp, 0.1, 1.5)
```

## AI Learning Progression

| Games Played | AI Status | Difficulty |
|--------------|-----------|------------|
| 1-2 | Baseline heuristics only | Easy |
| 3-5 | First ML model (50-100 samples) | Moderate |
| 6-10 | Improved ML (150-300 samples) | Challenging |
| 10+ | Advanced ML (300+ samples) | Very difficult |

## Design Decisions

### Why LightGBM?
- Fast training on small datasets
- Excellent with tabular data
- Interpretable (feature importance)
- Handles categorical features well

### Why Two-Tier AI?
- **Cold start solution:** Works from game 1
- **Smooth transition:** No sudden difficulty spikes
- **Reliability:** Fallback if ML fails
- **Progressive challenge:** Natural difficulty curve

## Dependencies

```
rich>=13.7.0          # Terminal UI
lightgbm>=4.1.0       # ML model
scikit-learn>=1.3.0   # ML utilities
numpy>=1.24.0         # Numerical operations
```

## Testing

```bash
python test_game.py  # Component tests
python test_ml.py    # ML pipeline tests
```
