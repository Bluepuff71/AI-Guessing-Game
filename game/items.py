"""Item definitions and shop management."""
from typing import Dict, List, Optional
from enum import Enum
from game.config_loader import config


class ItemType(Enum):
    """Types of items available in the shop."""
    SHIELD = "shield"
    SCANNER = "scanner"
    LUCKY_CHARM = "lucky_charm"
    INTEL_REPORT = "intel_report"
    SCOUT = "scout"


class Item:
    """Represents a purchasable item."""

    def __init__(self, item_type: ItemType, name: str, cost: int, description: str):
        self.type = item_type
        self.name = name
        self.cost = cost
        self.description = description
        self.consumed = False  # Track if single-use item was used

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Item({self.name})"


class ItemShop:
    """Manages the item shop."""

    ITEMS = None  # Will be loaded from config

    @classmethod
    def _load_items(cls):
        """Load items from config if not already loaded."""
        if cls.ITEMS is None:
            cls.ITEMS = {}
            items_data = config.get_items()

            for item_data in items_data:
                item_id = item_data['id']
                try:
                    item_type = ItemType(item_id)
                    cls.ITEMS[item_type] = Item(
                        item_type,
                        item_data['name'],
                        item_data['cost'],
                        item_data['description']
                    )
                except ValueError:
                    print(f"Warning: Unknown item type '{item_id}' in config")

    @classmethod
    def get_item(cls, item_type: ItemType) -> Item:
        """Get a fresh copy of an item."""
        cls._load_items()
        original = cls.ITEMS[item_type]
        return Item(original.type, original.name, original.cost, original.description)

    @classmethod
    def get_all_items(cls) -> List[Item]:
        """Get all available items."""
        cls._load_items()
        return [cls.get_item(item_type) for item_type in ItemType]

    @classmethod
    def display_shop(cls) -> str:
        """Get formatted shop display."""
        cls._load_items()
        lines = ["ITEM SHOP:"]
        for i, item_type in enumerate(ItemType, 1):
            item = cls.ITEMS[item_type]
            lines.append(f"[{i}] {item.name} - {item.cost} pts ({item.description})")
        lines.append("[Enter] Skip purchase")
        return "\n".join(lines)
