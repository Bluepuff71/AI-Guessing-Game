# AI System Analysis & Recommendations

## Current Game Complexity (v1.0)

### Game Features
- **Events**: 10 types (point modifiers, risk modifiers, immunity, guaranteed catch)
- **Items**: Scout (preview rolls), Intel Report (threat analysis)
- **Player Profiles**: Persistent stats, learning across games
- **Dynamic Scoring**: Win threshold at 100, variable location values
- **Multi-player**: 2-6 players with different strategies

### Current AI Architecture

**Prediction Strategy:**
1. **Early (rounds 1-3)**: Random predictions
2. **Mid (rounds 4-6)**: Simple pattern matching (most frequent location)
3. **Late (rounds 7+)**: Advanced heuristics with features
4. **ML Model** (optional): Global or per-player models after sufficient games
5. **Event-aware**: Adjusts predictions based on active events

**Location Selection:**
- 70% pick highest impact location
- 30% pick random from top 3 locations

---

## Question 1: Better Location Selection

### Current Approach Problems
❌ **Hard 70/30 split** - Binary decision, not probabilistic
❌ **Top-3 uniform random** - Ignores relative importance (2nd best treated same as 3rd)
❌ **No exploration tuning** - Can't adjust exploration/exploitation balance
❌ **Ignores zero-impact scenarios** - Random fallback loses strategic info

### Recommended Approach: **Softmax Selection**

**Why Softmax:**
✅ **Probabilistic** - Natural probability distribution over locations
✅ **Weighted by impact** - Higher impact = higher probability (not absolute)
✅ **Temperature control** - Tune exploration vs exploitation
✅ **Mathematically sound** - Well-studied in ML/game theory

**Formula:**
```
P(location_i) = exp(impact_i / temperature) / Σ exp(impact_j / temperature)
```

**Temperature effects:**
- `temperature = 0.1` → Nearly deterministic (95%+ best location)
- `temperature = 0.5` → Balanced (AI's current "sweet spot")
- `temperature = 1.0` → More exploratory
- `temperature = 2.0` → Very exploratory (nearly uniform)

**Benefits:**
1. AI picks best location ~60-80% of time (vs hard 70%)
2. Second-best location has meaningful chance (vs random 10%)
3. Can tune aggression based on game state:
   - High temperature when losing/exploring
   - Low temperature when dominating/exploiting
4. Handles edge cases naturally (all zeros → uniform)

### Alternative: **Upper Confidence Bound (UCB)**
Could track success rate per location and use UCB formula:
```
UCB(location) = average_success + C * sqrt(log(total_searches) / location_searches)
```
**Pros:** Optimal exploration/exploitation with guarantees
**Cons:** More complex, requires tracking search history

---

## Question 2: Is Current AI Optimal?

### Overall Assessment: **Good foundation, needs tuning**

The hybrid heuristics + ML approach is **appropriate** for this game because:
✅ **Works immediately** - No training needed for first game
✅ **Interpretable** - Players can understand AI reasoning
✅ **Adapts** - Learns player patterns over time
✅ **Event-aware** - Responds to dynamic game elements

### Current Strengths
1. **Multi-tier strategy** - Progressive complexity as game advances
2. **Per-player ML** - Personalized models for profile players
3. **Event integration** - Considers immunity/guaranteed-catch events
4. **Win-threat prioritization** - Targets players near victory

### Current Weaknesses
1. **ML doesn't use event features** - Models ignore current events
2. **Pattern matching too simple** - Mid-game only looks at frequency
3. **No counter-strategy** - Doesn't adapt if player counters AI
4. **Location selection suboptimal** - (addressed above)
5. **No memory between rounds** - Forgets recent round outcomes

---

## Recommendations

### Priority 1: Fix Location Selection ⭐⭐⭐
**Replace 70/30 split with softmax selection**

Estimated impact: +15-20% win rate improvement
Complexity: Low (20 lines of code)

### Priority 2: Add Event Features to ML ⭐⭐
**Include event data in feature extraction**

Features to add:
- `has_immunity_event` (bool)
- `has_catch_event` (bool)
- `event_point_modifier` (float)
- `num_active_events` (int)

Estimated impact: +10% prediction accuracy
Complexity: Medium (modify features.py + retrain)

### Priority 3: Improve Mid-Game Strategy ⭐⭐
**Replace simple frequency with recency-weighted patterns**

Current: "Where did they go most often?"
Better: "Where did they go in last 3 rounds + overall trend?"

Estimated impact: +5-10% mid-game prediction
Complexity: Low (modify _simple_pattern_prediction)

### Priority 4: Add Meta-Learning ⭐
**Track AI's own success rate and adapt**

If AI catches player at location X frequently, player may avoid X.
Track catch success per location and adjust targeting.

Estimated impact: +5% against adaptive players
Complexity: High (new tracking system)

---

## AI Strategy Comparison

| Approach | Pros | Cons | Fit for Game |
|----------|------|------|--------------|
| **Current (Hybrid)** | Fast, interpretable, adaptive | Simple patterns, no meta-learning | ✅ Good |
| **Pure ML** | Optimal with data, learns complex patterns | Needs training, black box, overfits | ⚠️ Risky |
| **Pure Heuristics** | No training, interpretable, reliable | Doesn't improve, predictable | ⚠️ Limited |
| **Reinforcement Learning** | Learns optimal policy, handles dynamics | Needs many games, slow, complex | ❌ Overkill |
| **Monte Carlo Tree Search** | Optimal short-term, handles uncertainty | Expensive, needs game simulation | ❌ Overkill |

**Verdict: Keep hybrid approach, enhance with recommendations above**

---

## Implementation Priority

### Must Do (v1.1):
1. ✅ Softmax location selection (20 lines)
2. ✅ Event features in ML (50 lines)

### Should Do (v1.2):
3. ✅ Recency-weighted patterns (30 lines)
4. ✅ Dynamic temperature based on game state (10 lines)

### Nice to Have (v2.0):
5. ⚠️ Meta-learning catch tracker (100+ lines)
6. ⚠️ Multi-armed bandit for location selection (80 lines)
7. ⚠️ Deep learning model (500+ lines, requires dependencies)

---

## Proposed Temperature Tuning

```python
def get_selection_temperature(game_state):
    """Dynamic temperature based on game context."""

    # Base temperature
    temp = 0.5

    # Increase if all impacts are similar (explore more)
    if max_impact < 2 * avg_impact:
        temp += 0.3

    # Decrease if one player is close to winning (exploit)
    if max_player_score > 85:
        temp -= 0.2

    # Increase if AI hasn't caught anyone in 3 rounds (try different locations)
    if rounds_since_catch > 3:
        temp += 0.2

    return max(0.1, min(temp, 1.5))  # Clamp to [0.1, 1.5]
```

---

## Conclusion

**Answer 1:** Yes, use **softmax selection** instead of 70/30 split
**Answer 2:** Current AI is **good**, not optimal - implement Priority 1-3 recommendations

The hybrid approach is correct for this game. The main improvements needed are:
1. Better probabilistic location selection (softmax)
2. Event-aware ML features
3. Recency-weighted pattern matching

These are high-impact, low-complexity changes that will make the AI significantly stronger without over-engineering.
