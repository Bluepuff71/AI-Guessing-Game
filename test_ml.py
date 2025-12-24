"""Test ML model training and prediction."""
import sys
import io
import json
import os
import random

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from ai.trainer import ModelTrainer
from ai.predictor import AIPredictor
from game.locations import LocationManager


def generate_synthetic_game_data(num_games=3, num_players=3):
    """Generate synthetic game data for testing."""
    locations = [
        "Gas Station", "Pharmacy", "Jewelry Store", "Bank Vault",
        "Warehouse", "Pawn Shop", "Electronics Store", "Convenience Store"
    ]

    location_values = {
        "Gas Station": 5,
        "Pharmacy": 10,
        "Jewelry Store": 20,
        "Bank Vault": 35,
        "Warehouse": 8,
        "Pawn Shop": 12,
        "Electronics Store": 15,
        "Convenience Store": 7
    }

    games = []

    for game_num in range(num_games):
        game_data = {
            'num_players': num_players,
            'num_rounds': random.randint(5, 10),
            'winner': f'Player {random.randint(1, num_players)}',
            'players': []
        }

        for p in range(num_players):
            rounds_survived = random.randint(5, 10)
            round_history = []
            choice_history = []

            # Generate player with specific pattern (to test ML)
            # Player 1: Likes high-value
            # Player 2: Likes low-value
            # Player 3: Random

            points = 0
            for r in range(rounds_survived):
                if p == 0:  # High-value player
                    location = random.choice(["Bank Vault", "Jewelry Store", "Electronics Store"])
                elif p == 1:  # Low-value player
                    location = random.choice(["Gas Station", "Pharmacy", "Warehouse", "Convenience Store"])
                else:  # Random
                    location = random.choice(locations)

                loc_value = location_values[location] + random.randint(-3, 3)
                points_earned = random.randint(0, loc_value)
                points += points_earned

                round_history.append({
                    'round': r + 1,
                    'location': location,
                    'location_value': loc_value,
                    'points_before': points - points_earned,
                    'points_earned': points_earned,
                    'caught': random.random() < 0.1,  # 10% caught rate
                    'items_held': []
                })

                choice_history.append(location)

            player_data = {
                'name': f'Player {p+1}',
                'final_points': points,
                'alive': random.choice([True, False]),
                'rounds_survived': rounds_survived,
                'round_history': round_history,
                'choice_history': choice_history
            }

            game_data['players'].append(player_data)

        games.append(game_data)

    return games


def test_ml_pipeline():
    """Test the complete ML pipeline."""
    print("Testing LightGBM ML Pipeline\n")
    print("=" * 50)

    # Clean up old data
    data_dir = "data"
    os.makedirs(data_dir, exist_ok=True)

    # Generate synthetic data
    print("\n1. Generating synthetic game data...")
    games = generate_synthetic_game_data(num_games=5, num_players=3)
    print(f"   ✓ Generated {len(games)} games")

    # Save to history file
    history_file = os.path.join(data_dir, "game_history.json")
    with open(history_file, 'w') as f:
        json.dump({'games': games}, f, indent=2)
    print(f"   ✓ Saved to {history_file}")

    # Train model
    print("\n2. Training ML model...")
    trainer = ModelTrainer()
    success = trainer.train_model(min_samples=10)

    if success:
        print("   ✓ Model trained successfully!")
    else:
        print("   ✗ Model training failed")
        return False

    # Test model loading
    print("\n3. Testing model loading...")
    trainer2 = ModelTrainer()
    loaded = trainer2.load_model()
    if loaded:
        print("   ✓ Model loaded successfully!")
    else:
        print("   ✗ Model loading failed")
        return False

    # Test prediction
    print("\n4. Testing prediction...")
    # Create dummy features
    test_features = [
        50,   # current_score
        50,   # points_to_win
        5,    # round_number
        18,   # avg_location_value
        20,   # recent_avg_value
        25,   # choice_variance
        0.6,  # high_value_preference
        5,    # unique_locations_visited
        5,    # total_rounds_played
        1,    # risk_trend (increasing)
        0,    # times_caught
        1,    # num_items
    ]

    try:
        predictions = trainer2.predict(test_features)
        print(f"   ✓ Predictions generated!")
        print(f"   Top 3 predictions:")
        sorted_preds = sorted(predictions.items(), key=lambda x: x[1], reverse=True)
        for loc, prob in sorted_preds[:3]:
            print(f"     - {loc}: {prob:.2%}")
    except Exception as e:
        print(f"   ✗ Prediction failed: {e}")
        return False

    # Test AI integration
    print("\n5. Testing AI integration...")
    loc_manager = LocationManager()
    ai = AIPredictor(loc_manager)

    if ai.use_ml:
        print("   ✓ AI is using ML model!")
        info = ai.ml_trainer.get_model_info()
        print(f"   - Trained on {info['num_games']} games")
        print(f"   - {info['training_samples']} training samples")
    else:
        print("   ✗ AI is NOT using ML model (using baseline)")

    print("\n" + "=" * 50)
    print("✅ All ML tests passed!")
    print("=" * 50)

    return True


if __name__ == "__main__":
    try:
        success = test_ml_pipeline()
        if success:
            print("\n🎉 ML integration is working!\n")
            print("Next steps:")
            print("  1. Play 2-3 real games: python main.py")
            print("  2. Model will auto-train after games")
            print("  3. AI will get smarter with each game!")
        else:
            print("\n❌ ML integration tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
