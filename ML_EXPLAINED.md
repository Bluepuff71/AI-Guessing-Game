# LOOT RUN - Machine Learning System Explained

## Overview

LOOT RUN uses a **two-tier AI system** that evolves from simple heuristics to advanced machine learning as you play more games.

## How It Works

### Tier 1: Baseline AI (Always Active)

The baseline AI uses rule-based heuristics:

**Rounds 1-3:** Random predictions
- AI is "learning" - picks random locations
- 12.5% confidence (1/8 chance)

**Rounds 4-6:** Frequency analysis
- Tracks which locations you visit most
- Predicts your most common choice
- Confidence = frequency (e.g., 40% if you picked Bank 2/5 times)

**Rounds 7+:** Behavioral analysis
- Analyzes risk patterns (high-value vs low-value preference)
- Tracks contextual behavior (what you do when winning/losing)
- Considers items, trends, and win threats
- Scores each location based on multiple factors

### Tier 2: ML-Enhanced AI (After Training)

Once enough games are played (2+), LightGBM kicks in:

**Model:** Gradient Boosted Decision Trees (LightGBM)
- Industry-standard ML algorithm
- Fast, accurate, interpretable
- Handles small datasets well

**Training Data:** Every player choice ever made
- Features: score, round, items, behavior patterns, trends
- Label: Which location they actually chose
- Minimum 20 samples needed (typically 2-3 games with 3-4 players)

**Prediction:** Probability distribution over 8 locations
- Example: Bank Vault (85%), Jewelry (8%), Electronics (4%), etc.
- AI searches location with highest expected "threat × confidence"

## Feature Engineering

The ML model uses 12 features to predict your next move:

### State Features (3)
1. **current_score** - How many points you have
2. **points_to_win** - 100 - current_score
3. **round_number** - Which round we're in

### Historical Behavior (8)
4. **avg_location_value** - Average points of locations you've chosen
5. **recent_avg_value** - Average of last 3 choices (detects trends)
6. **choice_variance** - How consistent your choices are
7. **high_value_preference** - % of times you pick 15+ point locations
8. **unique_locations_visited** - How many different spots (0-8)
9. **total_rounds_played** - Your experience level
10. **risk_trend** - Are you getting more/less aggressive? (-1, 0, 1)
11. **times_caught** - How often you've been eliminated before

### Item Features (1)
12. **num_items** - How many items you currently have

## Training Pipeline

### When Does Training Happen?

1. **Initial Training** - After 2+ games
   ```
   🤖 No AI model found. Training initial model from 2 games...
   Training with 47 samples from 2 games...
   ✓ Model trained successfully!
   ```

2. **Retraining** - Every 5 games
   ```
   🤖 Retraining AI model with 10 total games...
   Training with 234 samples from 10 games...
   ✓ Model trained successfully!
   ```

### What Happens During Training?

1. **Load game history** from `data/game_history.json`
2. **Extract features** for every choice ever made
3. **Encode locations** (Bank Vault → 0, Jewelry → 1, etc.)
4. **Train LightGBM** with 100 boosting rounds
5. **Save model** to `data/model.pkl`
6. **Display feature importance** (which patterns matter most)

### Feature Importance Example

```
Feature importance (top 5):
  avg_location_value: 824.5    ← What you usually pick
  current_score: 633.0          ← How close to winning
  recent_avg_value: 574.2       ← Recent trend
  round_number: 519.1           ← Game phase
  choice_variance: 518.5        ← Consistency
```

This tells you: "The AI mostly cares about your typical location value and current score"

## Prediction Flow

When the AI needs to predict your location:

### 1. Feature Extraction
```python
features = [
    50,     # current_score
    50,     # points_to_win
    8,      # round 8
    22.3,   # you average 22-point locations
    28.5,   # but recently going higher
    45.2,   # moderate variance
    0.75,   # 75% high-value choices
    6,      # visited 6/8 locations
    7,      # 7 rounds played
    1.0,    # trend: increasing risk
    0,      # never caught
    1       # have 1 item (Shield)
]
```

### 2. Model Prediction
```python
probabilities = {
    'Bank Vault': 0.65,        # 65% chance
    'Jewelry Store': 0.18,     # 18% chance
    'Electronics Store': 0.09, # 9% chance
    'Pharmacy': 0.04,          # 4% chance
    ...
}
```

### 3. Threat Calculation
```python
for each location:
    for each player:
        if predicted_at_location:
            threat = (proximity_to_100 * 0.7) + (predictability * 0.3)
            expected_impact = probability × threat

search = location_with_highest_impact
```

Result: AI prioritizes catching players who are:
1. Close to winning (high score)
2. Predictable (high confidence)
3. At predicted locations

### 4. Reasoning Generation
```python
"ML model high confidence, 85 points - win threat, favors high-value locations"
```

## Why This Approach?

### LightGBM Advantages
✅ **Fast training** - Seconds, not minutes
✅ **Small data** - Works with 20+ samples
✅ **Interpretable** - Shows feature importance
✅ **Robust** - Doesn't overfit easily
✅ **Incremental** - Easy to retrain with new data

### Two-Tier Benefits
✅ **Works from game 1** - Baseline AI handles cold start
✅ **Smooth transition** - ML seamlessly takes over
✅ **Fallback safety** - If ML fails, baseline works
✅ **Progressive learning** - Gets smarter over time

## Player Experience

### Game 1-2: Beatable
- AI uses simple patterns
- Easy to outsmart with variety
- Build confidence and learn mechanics

### Game 3-5: Challenging
- ML model trains
- AI notices your preferences
- Must start varying strategies

### Game 6-10: Competitive
- Model has lots of data
- Recognizes meta-strategies
- Genuinely difficult to beat

### Game 10+: Master Level
- AI has seen hundreds of choices
- Adapts to counter-strategies
- Requires creativity and unpredictability

## Example Learning Curve

**Game 1:**
```
🤖 AI Status: Baseline AI (No ML model yet)
```
AI: Random guessing → Easy to survive

**Game 3:**
```
🤖 No AI model found. Training initial model from 3 games...
Training with 67 samples...
✓ Model trained!
```
Next game shows:
```
🤖 AI Status: ML Model Active (trained on 3 games, 67 samples)
```

**Game 10:**
```
🤖 Retraining AI model with 10 total games...
Training with 245 samples...
✓ Model trained!
```
AI is now significantly smarter

## Tips for Playing Against ML AI

### Early Games (Baseline)
- Be aggressive, grab points
- Build up score quickly
- Don't worry too much about patterns

### Mid Games (Early ML)
- Start varying your choices
- Buy Intel Reports to see if you're predictable
- Use Scout to preview rolls and make strategic choices

### Late Games (Advanced ML)
- Actively break patterns
- Mix high and low value unexpectedly
- Stay unpredictable when close to 100 points
- Use items strategically (Ghost Mode, Pattern Break)

## Technical Details

### Data Storage

**game_history.json:**
```json
{
  "games": [
    {
      "num_players": 3,
      "num_rounds": 8,
      "winner": "Alice",
      "players": [...]
    }
  ]
}
```

**model.pkl:**
- Trained LightGBM booster
- Feature names
- Binary pickle format

**label_encoder.pkl:**
- Location name ↔ integer mapping
- Consistent encoding across training

### Model Parameters

```python
{
    'objective': 'multiclass',        # 8 location classes
    'num_class': 8,
    'boosting_type': 'gbdt',          # Gradient boosting
    'num_leaves': 31,                 # Tree complexity
    'learning_rate': 0.05,            # Slow but stable
    'feature_fraction': 0.9,          # Feature sampling
    'bagging_fraction': 0.8,          # Data sampling
    'min_data_in_leaf': 5,            # Prevent overfitting
    'num_boost_round': 100            # 100 trees
}
```

Tuned for:
- Small datasets (50-500 samples)
- 12 features
- 8 classes
- Quick training
- Good generalization

## Debugging & Monitoring

### Check Model Status
```python
from ai.trainer import ModelTrainer
trainer = ModelTrainer()
info = trainer.get_model_info()
print(info)
```

Output:
```python
{
    'model_exists': True,
    'num_games': 5,
    'training_samples': 116,
    'locations': ['Bank Vault', 'Jewelry Store', ...],
    'num_features': 12
}
```

### Force Retrain
```python
from ai.trainer import ModelTrainer
trainer = ModelTrainer()
trainer.train_model(min_samples=10)  # Lower threshold
```

### Test Prediction
```python
features = [50, 50, 5, 20, 22, 30, 0.6, 5, 5, 1, 0, 1]
predictions = trainer.predict(features)
print(predictions)
```

## Future Enhancements

Possible improvements:
- **Ensemble models** - Combine multiple algorithms
- **Online learning** - Update model during game
- **Player clustering** - Identify player archetypes
- **Meta-features** - Learn from player-vs-player dynamics
- **Confidence calibration** - Improve probability estimates
- **A/B testing** - Compare baseline vs ML performance

---

**The AI is always learning. Are you?** 🤖
