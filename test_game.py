"""Quick test script to verify game mechanics."""
import sys
import io

# Fix Windows console encoding for emojis
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from game.player import Player
from game.locations import LocationManager
from game.items import ItemShop, ItemType
from ai.predictor import AIPredictor
from ai.features import calculate_predictability, extract_features

def test_basics():
    """Test basic game components."""
    print("Testing LOOT RUN components...\n")

    # Test locations
    print("1. Testing Locations...")
    loc_manager = LocationManager()
    assert len(loc_manager.get_all()) == 8
    for loc in loc_manager.get_all():
        # Test individual rolls
        roll = loc.roll_points()
        assert loc.min_points <= roll <= loc.max_points, f"Roll {roll} outside range {loc.min_points}-{loc.max_points}"
        print(f"  {loc.emoji} {loc.name}: {loc.get_range_str()} pts (sample roll: {roll})")
    print("  ✓ Locations working\n")

    # Test player
    print("2. Testing Player...")
    player = Player(1, "Alice")
    assert player.points == 0
    player.add_points(25)
    assert player.points == 25
    print(f"  {player}")
    print("  ✓ Player working\n")

    # Test items
    print("3. Testing Items...")
    shield = ItemShop.get_item(ItemType.SHIELD)
    assert shield.cost == 15
    success = player.buy_item(shield)
    assert success == True
    assert player.points == 10
    assert player.has_item(ItemType.SHIELD)
    print(f"  {player}")
    print("  ✓ Items working\n")

    # Test AI predictor
    print("4. Testing AI Predictor...")
    ai = AIPredictor(loc_manager)

    # Simulate some choices
    for i in range(5):
        location = loc_manager.get_location(i % 3)  # Make a pattern
        player.record_choice(location, i+1, caught=False, points_earned=10)

    prediction = ai.predict_player_location(player, 1)
    print(f"  AI predicted: {prediction[0]} (confidence: {prediction[1]:.2%})")
    print(f"  Reasoning: {prediction[2]}")
    print("  ✓ AI working\n")

    # Test predictability
    print("5. Testing Predictability Calculation...")
    predictability = calculate_predictability(player)
    print(f"  Player predictability: {predictability:.2%}")
    print("  ✓ Predictability working\n")

    print("=" * 50)
    print("All tests passed! ✅")
    print("=" * 50)

if __name__ == "__main__":
    test_basics()
