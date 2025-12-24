"""Player class and management."""
from typing import List, Optional, Dict, Any
from game.items import Item, ItemType
from game.locations import Location


class Player:
    """Represents a player in the game."""

    def __init__(self, player_id: int, name: str, profile_id: Optional[str] = None):
        self.id = player_id
        self.name = name
        self.profile_id = profile_id  # UUID of player's profile (None for guests)
        self.points = 0
        self.alive = True
        self.items: List[Item] = []

        # History tracking for AI
        self.choice_history: List[str] = []  # Location names chosen
        self.round_history: List[Dict[str, Any]] = []  # Full round data

    def add_points(self, points: int):
        """Add points to player."""
        self.points += points

    def buy_item(self, item: Item) -> bool:
        """Attempt to buy an item. Returns True if successful."""
        if self.points >= item.cost:
            self.points -= item.cost
            self.items.append(item)
            return True
        return False

    def has_item(self, item_type: ItemType) -> bool:
        """Check if player has an item of the given type."""
        return any(item.type == item_type and not item.consumed
                   for item in self.items)

    def use_item(self, item_type: ItemType) -> Optional[Item]:
        """Use an item (mark as consumed). Returns the item if found."""
        for item in self.items:
            if item.type == item_type and not item.consumed:
                item.consumed = True
                return item
        return None

    def get_item(self, item_type: ItemType) -> Optional[Item]:
        """Get a specific item by type."""
        for item in self.items:
            if item.type == item_type:
                return item
        return None

    def get_active_items(self) -> List[Item]:
        """Get list of items that haven't been consumed."""
        return [item for item in self.items if not item.consumed]

    def record_choice(self, location: Location, round_num: int,
                     caught: bool, points_earned: int, location_value: int = None):
        """Record a choice for AI learning."""
        self.choice_history.append(location.name)

        # If location_value not provided, use points_earned (base value before Lucky Charm)
        if location_value is None:
            location_value = points_earned

        self.round_history.append({
            'round': round_num,
            'location': location.name,
            'location_value': location_value,
            'points_before': self.points - points_earned,
            'points_earned': points_earned,
            'caught': caught,
            'items_held': [item.name for item in self.get_active_items()],
        })

    def get_behavior_summary(self) -> Dict[str, Any]:
        """Get summary of player behavior for AI analysis."""
        if not self.choice_history:
            return {
                'avg_location_value': 0,
                'choice_variety': 0,
                'high_value_preference': 0,
                'location_frequencies': {},
                'total_choices': 0,
            }

        # Calculate statistics
        location_counts = {}
        total_value = 0

        for round_data in self.round_history:
            loc = round_data['location']
            location_counts[loc] = location_counts.get(loc, 0) + 1
            total_value += round_data['location_value']

        num_choices = len(self.choice_history)
        unique_locations = len(location_counts)
        avg_value = total_value / num_choices if num_choices > 0 else 0

        # High-value choices (15+ points)
        high_value_count = sum(1 for r in self.round_history
                               if r['location_value'] >= 15)

        return {
            'avg_location_value': avg_value,
            'choice_variety': unique_locations / 8.0,  # 8 total locations
            'high_value_preference': high_value_count / num_choices if num_choices > 0 else 0,
            'location_frequencies': location_counts,
            'total_choices': num_choices,
        }

    def __str__(self) -> str:
        items_str = f" [{', '.join(i.name for i in self.get_active_items())}]" if self.get_active_items() else ""
        return f"{self.name} - {self.points} pts{items_str}"
