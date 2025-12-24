"""Item definitions and shop management."""
from typing import Dict, List, Optional
from enum import Enum


class ItemType(Enum):
    """Types of items available in the shop."""
    SHIELD = "shield"
    SCANNER = "scanner"
    LUCKY_CHARM = "lucky_charm"
    INTEL_REPORT = "intel_report"


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

    ITEMS = {
        ItemType.SHIELD: Item(
            ItemType.SHIELD,
            "Shield",
            15,
            "Survive one capture (single use)"
        ),
        ItemType.SCANNER: Item(
            ItemType.SCANNER,
            "Scanner",
            25,
            "See AI's top 2 predicted search locations"
        ),
        ItemType.LUCKY_CHARM: Item(
            ItemType.LUCKY_CHARM,
            "Lucky Charm",
            18,
            "Double points this round (single use)"
        ),
        ItemType.INTEL_REPORT: Item(
            ItemType.INTEL_REPORT,
            "Intel Report",
            20,
            "See your AI threat level and predictability"
        ),
    }

    @classmethod
    def get_item(cls, item_type: ItemType) -> Item:
        """Get a fresh copy of an item."""
        original = cls.ITEMS[item_type]
        return Item(original.type, original.name, original.cost, original.description)

    @classmethod
    def get_all_items(cls) -> List[Item]:
        """Get all available items."""
        return [cls.get_item(item_type) for item_type in ItemType]

    @classmethod
    def display_shop(cls) -> str:
        """Get formatted shop display."""
        lines = ["ITEM SHOP:"]
        for i, item_type in enumerate(ItemType, 1):
            item = cls.ITEMS[item_type]
            lines.append(f"[{i}] {item.name} - {item.cost} pts ({item.description})")
        lines.append("[Skip] No purchase")
        return "\n".join(lines)
