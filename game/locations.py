"""Location definitions and point value management."""
import random
from typing import Dict, List
from game.config_loader import config


class Location:
    """Represents a lootable location."""

    def __init__(self, name: str, emoji: str, min_points: int, max_points: int):
        self.name = name
        self.emoji = emoji
        self.min_points = min_points
        self.max_points = max_points

    def roll_points(self) -> int:
        """Roll a random point value in this location's range for a player."""
        return random.randint(self.min_points, self.max_points)

    def get_range_str(self) -> str:
        """Get the point range as a string for display."""
        return f"{self.min_points}-{self.max_points}"

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}"


class LocationManager:
    """Manages all game locations."""

    def __init__(self):
        # Load from config
        locations_data = config.get_locations()

        self.locations: List[Location] = []
        for loc_data in locations_data:
            # Support new min/max format
            if 'min_points' in loc_data and 'max_points' in loc_data:
                min_points = loc_data['min_points']
                max_points = loc_data['max_points']
            # Backward compatibility: convert old base_points + variance format
            elif 'base_points' in loc_data:
                base = loc_data['base_points']
                variance = loc_data.get('variance', 0.2)
                variance_amount = int(base * variance)
                min_points = base - variance_amount
                max_points = base + variance_amount
            else:
                raise ValueError(f"Location '{loc_data['name']}' missing point configuration")

            self.locations.append(Location(
                name=loc_data['name'],
                emoji=loc_data['emoji'],
                min_points=min_points,
                max_points=max_points
            ))

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
