# LOOT RUN - Quick Start Guide

## Installation

1. **Install Python dependencies:**
```bash
pip install rich
```

*Note: LightGBM and scikit-learn are optional for now - the game uses a baseline AI*

2. **Run the game:**
```bash
python main.py
```

## How to Play (Quick Summary)

### Objective
- Be the first to reach **100 points** OR be the last player standing

### Each Round

1. **Shop Phase** - Buy items if you want:
   - **Lucky Charm** (9 pts) - 15% bonus points this round
   - **Intel Report** (10 pts) - See how predictable you are
   - **Scout** (6 pts) - Preview loot rolls before choosing

2. **Choose Location** - Pick where to loot (1-8):
   - Higher point locations = higher risk (AI targets them)
   - Point values change each round (±20%)

3. **AI Searches** - The AI picks ONE location to search
   - Caught without Shield = **ELIMINATED**
   - Caught with Shield = Survive but get 0 points
   - Not caught = Collect your points!

### Strategy Tips

🎯 **Early Game (Rounds 1-3)**
- AI is random - safe to be aggressive!
- Build up points quickly

🧠 **Mid Game (Rounds 4-6)**
- AI starts learning simple patterns
- Vary your choices
- Consider buying Intel Report to see if you're predictable

⚔️ **Late Game (Rounds 7+)**
- AI knows your habits!
- If you're close to 100, AI will hunt you hard
- Consider going low-value to survive
- Use Scout to preview rolls and make informed choices

### Key Mechanics

**The AI gets smarter each round:**
- Tracks your favorite locations
- Learns if you prefer high/low value spots
- Notices win-rush behavior (going aggressive near 100 pts)
- Prioritizes players closest to winning

**Being predictable is dangerous:**
- Going to the same location repeatedly
- Always choosing high-value when ahead
- Consistent patterns after close calls

**Stay unpredictable:**
- Mix high and low value locations
- Visit all 8 locations
- Break your own patterns
- Use items strategically

## Example Round

```
=== ROUND 5 ===

Standings:
1. Alice - 72 pts [Shield]
2. You - 58 pts
3. Bob - 45 pts

Available Loot:
[1] 🏪 Gas Station: 6 pts
[2] 💊 Pharmacy: 11 pts
[3] 💎 Jewelry Store: 22 pts
[4] 🏦 Bank Vault: 38 pts
...

Your turn:
> Buy item? (1-4 or skip): skip

> Choose location (1-5): 2
You chose: Pharmacy (11 pts)

...AI analyzes...

🎯 AI SEARCHES: BANK VAULT
💀 Alice was caught! Shield activated - survives!
✅ You looted Pharmacy: +11 pts (69 total)
✅ Bob looted Warehouse: +9 pts (54 total)
```

## Winning Strategies

1. **The Scout** - Use Scout to preview rolls, maximize every heist
2. **The Gambler** - Go for high-variance locations, use Lucky Charm when you hit big
3. **The Ghost** - Stay unpredictable, fly under the radar
4. **The Analyst** - Buy Intel Reports, adapt based on feedback

## Troubleshooting

**Emojis not showing?**
- Windows: The game automatically sets UTF-8 encoding
- If issues persist, use Windows Terminal instead of cmd.exe

**Want to see AI stats?**
- Buy an Intel Report during the game
- Check post-game report when eliminated

**Game too easy/hard?**
- Early games: AI is learning, easier
- After 10+ games: AI has more data, harder
- Play with more players for more chaos!

---

**Have fun and may the odds be ever in your favor!** 🎲
