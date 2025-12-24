"""Location definitions and point value management."""
import random
from typing import Dict, List
from game.config_loader import config


class Location:
    """Represents a lootable location."""

    def __init__(self, name: str, emoji: str, base_points: int, variance: float = 0.2):
        self.name = name
        self.emoji = emoji
        self.base_points = base_points
        self.current_points = base_points
        self.variance = variance

    def randomize_points(self) -> int:
        """Randomize point value based on variance % from base."""
        variance_amount = int(self.base_points * self.variance)
        self.current_points = self.base_points + random.randint(-variance_amount, variance_amount)
        return self.current_points

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}"


class LocationManager:
    """Manages all game locations."""

    def __init__(self):
        # Load from config
        locations_data = config.get_locations()
        variance = config.get('locations', 'point_variance', default=0.2)

        self.locations: List[Location] = []
        for loc_data in locations_data:
            self.locations.append(Location(
                name=loc_data['name'],
                emoji=loc_data['emoji'],
                base_points=loc_data['base_points'],
                variance=variance
            ))

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
