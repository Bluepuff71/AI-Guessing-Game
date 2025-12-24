# LOOT RUN

A strategic text-based party game where players compete to reach 100 points by looting locations, while an adaptive AI learns their patterns and hunts them down.

## Game Overview

**Objective:** Be the first to reach 100 points, or be the last player standing.

**Players:** 2-6 players

**The Twist:** An AI analyzes your behavior and learns to predict where you'll loot. The more predictable you are, the easier you are to catch!

## How to Play

### Setup
1. Each round, locations have randomized point values (±20% variance)
2. Players can buy items from the shop
3. Players secretly choose which location to loot

### Resolution
1. The AI predicts where each player will go
2. The AI searches ONE location
3. Any player at that location is caught (eliminated unless they have a Shield)
4. Other players collect their points

### Win Conditions
- **Player Victory:** First to 100 points
- **AI Victory:** All players eliminated
- **Last Standing:** If only one player remains

## Locations

| Location | Base Points |
|----------|-------------|
| 🏪 Gas Station | 5 pts |
| 💊 Pharmacy | 10 pts |
| 🔨 Pawn Shop | 12 pts |
| 💻 Electronics Store | 15 pts |
| 💎 Jewelry Store | 20 pts |
| 🏦 Bank Vault | 35 pts |
| 📦 Warehouse | 8 pts |
| 🏬 Convenience Store | 7 pts |

## Items

| Item | Cost | Effect |
|------|------|--------|
| **Lucky Charm** | 9 pts | 15% bonus points this round (single use) |
| **Intel Report** | 10 pts | See your AI threat level & predictability |
| **Scout** | 6 pts | Preview loot rolls before choosing (single use) |

## Strategy Tips

1. **Be Unpredictable:** The AI learns patterns. Vary your choices!
2. **Risk vs Reward:** High-value locations are obvious targets
3. **Item Timing:** Save defensive items for when you need them most
4. **Win Rush:** Going aggressive when close to 100 makes you a priority target
5. **Use Intel:** If you feel predictable, buy an Intel Report to see what the AI knows

## How the AI Works

### Two-Tier AI System

**Baseline AI (No Model):**
- **Rounds 1-3:** Random (learning phase)
- **Rounds 4-6:** Simple pattern matching
- **Rounds 7+:** Advanced behavioral heuristics

**ML-Enhanced AI (After 2+ Games):**
- Uses trained LightGBM model
- Learns from ALL previous games
- Adapts to meta-strategies
- Gets smarter with every game played

The AI considers:
- Your location history and preferences
- Your current score (players near 100 are high priority)
- Items you own
- Risk patterns and trends
- How predictable your behavior is

### Model Training

After every **5 games**, the AI automatically retrains:
- Analyzes all player decisions from game history
- Learns which features predict location choices
- Updates predictions for future games
- Displays training progress and feature importance

## Installation

```bash
# Install dependencies
pip install rich lightgbm scikit-learn numpy

# Run the game
python main.py

# Optional: Run tests
python test_game.py    # Test game components
python test_ml.py      # Test ML pipeline
```

## Requirements

- Python 3.9+
- rich (terminal UI)
- lightgbm (ML model)
- scikit-learn (ML utilities)
- numpy

## ML Model Status

**First Game:** AI uses baseline heuristics

**After 2-3 Games:** AI trains its first ML model
- You'll see: "🤖 No AI model found. Training initial model from X games..."

**After 5+ Games:** AI retrains automatically
- You'll see: "🤖 Retraining AI model with X total games..."
- Model gets progressively smarter

**Game Start:** Shows current AI status
- "ML Model Active (trained on X games)" = AI is using machine learning
- "Baseline AI" = Need more games for model training

## Advanced Features

✅ **LightGBM ML Model** - Trained on game history
✅ **Cross-game Learning** - AI improves from previous games
✅ **Feature Importance** - Shows what patterns matter most
✅ **Automatic Retraining** - Model updates every 5 games
✅ **Graceful Fallback** - Uses baseline AI if ML unavailable

## Future Enhancements

- More items and locations
- Difficulty levels (adjust AI aggression)
- Statistics dashboard
- Leaderboards across games

## Credits

Built with:
- [Rich](https://github.com/Textualize/rich) for beautiful terminal UI
- [LightGBM](https://lightgbm.readthedocs.io/) for machine learning

## License

MIT License - Feel free to modify and share!

---

**Have fun, and remember: The AI is always watching... and learning.** 🤖
