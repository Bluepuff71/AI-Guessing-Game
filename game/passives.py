"""Passive ability definitions and management."""
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field


class PassiveType(Enum):
    """Types of passive abilities."""
    AI_WHISPERER = "ai_whisperer"
    INSIDE_KNOWLEDGE = "inside_knowledge"
    ESCAPE_ARTIST = "escape_artist"
    QUICK_FEET = "quick_feet"
    HIGH_ROLLER = "high_roller"


@dataclass
class Passive:
    """Represents a passive ability."""
    type: PassiveType
    name: str
    cost: int
    description: str
    emoji: str
    category: str
    effects: Dict[str, Any] = field(default_factory=dict)

    def has_effect(self, effect_name: str) -> bool:
        """Check if passive has a specific effect."""
        return effect_name in self.effects

    def get_effect(self, effect_name: str, default: Any = None) -> Any:
        """Get effect value by name."""
        return self.effects.get(effect_name, default)


class PassiveShop:
    """Manages the passive abilities shop."""

    PASSIVES: Dict[PassiveType, Passive] = None

    @classmethod
    def _load_passives(cls):
        """Load passives from config if not already loaded."""
        if cls.PASSIVES is not None:
            return

        from game.config_loader import config

        cls.PASSIVES = {}
        passives_data = config.get_passives()

        for passive_data in passives_data:
            passive_id = passive_data['id']
            try:
                passive_type = PassiveType(passive_id)
                cls.PASSIVES[passive_type] = Passive(
                    type=passive_type,
                    name=passive_data['name'],
                    cost=passive_data['cost'],
                    description=passive_data['description'],
                    emoji=passive_data.get('emoji', '✨'),
                    category=passive_data.get('category', 'misc'),
                    effects=passive_data.get('effects', {})
                )
            except ValueError:
                print(f"Warning: Unknown passive type '{passive_id}' in config")

    @classmethod
    def get_passive(cls, passive_type: PassiveType) -> Optional[Passive]:
        """Get a passive by type."""
        cls._load_passives()
        return cls.PASSIVES.get(passive_type)

    @classmethod
    def get_all_passives(cls) -> List[Passive]:
        """Get all available passives."""
        cls._load_passives()
        return list(cls.PASSIVES.values())

    @classmethod
    def get_passive_by_index(cls, index: int) -> Optional[Passive]:
        """Get a passive by its display index (1-based)."""
        cls._load_passives()
        passives = list(cls.PASSIVES.values())
        if 1 <= index <= len(passives):
            return passives[index - 1]
        return None

    @classmethod
    def get_passive_count(cls) -> int:
        """Get the number of available passives."""
        cls._load_passives()
        return len(cls.PASSIVES)


class PassiveManager:
    """Manages a player's active passives and applies their effects."""

    def __init__(self):
        self.passives: List[Passive] = []

    def add_passive(self, passive: Passive) -> bool:
        """Add a passive. Returns False if already owned."""
        if any(p.type == passive.type for p in self.passives):
            return False
        self.passives.append(passive)
        return True

    def has_passive(self, passive_type: PassiveType) -> bool:
        """Check if player has a specific passive."""
        return any(p.type == passive_type for p in self.passives)

    def get_passive(self, passive_type: PassiveType) -> Optional[Passive]:
        """Get a specific passive if owned."""
        for p in self.passives:
            if p.type == passive_type:
                return p
        return None

    def get_all(self) -> List[Passive]:
        """Get all owned passives."""
        return self.passives.copy()

    def get_effect_value(self, effect_name: str, default: Any = None) -> Any:
        """Get effect value from any passive that has it."""
        for passive in self.passives:
            if passive.has_effect(effect_name):
                return passive.get_effect(effect_name, default)
        return default

    def get_cumulative_bonus(self, bonus_name: str) -> float:
        """Get cumulative bonus from all passives (for additive effects)."""
        total = 0.0
        for passive in self.passives:
            total += passive.get_effect(bonus_name, 0.0)
        return total

    def get_intel_level(self) -> str:
        """Get player's intel detail level."""
        if self.has_passive(PassiveType.AI_WHISPERER):
            return "full"
        return "simple"

    def shows_point_hints(self) -> bool:
        """Check if player can see point hints."""
        return self.has_passive(PassiveType.INSIDE_KNOWLEDGE)

    def get_hide_bonus(self) -> float:
        """Get total hiding success bonus."""
        return self.get_cumulative_bonus('hide_bonus')

    def get_run_bonus(self) -> float:
        """Get total running success bonus."""
        return self.get_cumulative_bonus('run_bonus')

    def get_run_retention(self) -> Optional[float]:
        """Get custom run point retention if any passive provides it."""
        return self.get_effect_value('run_retention')

    def get_high_roller_effect(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Get High Roller effect if applicable to location."""
        if not self.has_passive(PassiveType.HIGH_ROLLER):
            return None

        passive = self.get_passive(PassiveType.HIGH_ROLLER)
        bonus_locations = passive.get_effect('bonus_locations', [])

        if location_name in bonus_locations:
            return {
                'point_bonus': passive.get_effect('point_bonus', 0.15),
                'bust_chance': passive.get_effect('bust_chance', 0.20)
            }
        return None
