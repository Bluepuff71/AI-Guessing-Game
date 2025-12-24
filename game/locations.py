"""Location definitions and point value management."""
import random
from typing import Dict, List


class Location:
    """Represents a lootable location."""

    def __init__(self, name: str, emoji: str, base_points: int):
        self.name = name
        self.emoji = emoji
        self.base_points = base_points
        self.current_points = base_points

    def randomize_points(self) -> int:
        """Randomize point value ±20% from base."""
        variance = int(self.base_points * 0.2)
        self.current_points = self.base_points + random.randint(-variance, variance)
        return self.current_points

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}"


class LocationManager:
    """Manages all game locations."""

    def __init__(self):
        self.locations: List[Location] = [
            Location("Gas Station", "🏪", 5),
            Location("Pharmacy", "💊", 10),
            Location("Jewelry Store", "💎", 20),
            Location("Bank Vault", "🏦", 35),
            Location("Warehouse", "📦", 8),
            Location("Pawn Shop", "🔨", 12),
            Location("Electronics Store", "💻", 15),
            Location("Convenience Store", "🏬", 7),
        ]

    def randomize_all_points(self):
        """Randomize all location point values for a new round."""
        for loc in self.locations:
            loc.randomize_points()

    def get_location(self, index: int) -> Location:
        """Get location by index (0-based)."""
        return self.locations[index]

    def get_location_by_name(self, name: str) -> Location:
        """Get location by name."""
        for loc in self.locations:
            if loc.name == name:
                return loc
        raise ValueError(f"Location '{name}' not found")

    def get_all(self) -> List[Location]:
        """Get all locations."""
        return self.locations

    def __len__(self) -> int:
        return len(self.locations)
