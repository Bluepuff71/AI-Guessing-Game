"""Tests for game.passives module."""
import pytest
from game.passives import PassiveType, Passive, PassiveShop, PassiveManager


class TestPassiveType:
    """Tests for PassiveType enum."""

    def test_passive_type_enum_values(self):
        """Test all PassiveType enum values exist."""
        assert PassiveType.AI_WHISPERER.value == "ai_whisperer"
        assert PassiveType.INSIDE_KNOWLEDGE.value == "inside_knowledge"
        assert PassiveType.ESCAPE_ARTIST.value == "escape_artist"
        assert PassiveType.QUICK_FEET.value == "quick_feet"
        assert PassiveType.HIGH_ROLLER.value == "high_roller"

    def test_passive_type_enum_count(self):
        """Test expected number of passive types."""
        assert len(PassiveType) == 5


class TestPassive:
    """Tests for Passive dataclass."""

    def test_passive_initialization(self):
        """Test Passive dataclass initialization."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="See detailed AI analysis",
            emoji="🔮",
            category="intel",
            effects={"intel_detail_level": "full"}
        )
        assert passive.type == PassiveType.AI_WHISPERER
        assert passive.name == "AI Whisperer"
        assert passive.cost == 15
        assert passive.description == "See detailed AI analysis"
        assert passive.emoji == "🔮"
        assert passive.category == "intel"
        assert passive.effects == {"intel_detail_level": "full"}

    def test_passive_default_effects(self):
        """Test Passive with default empty effects."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="Test",
            cost=10,
            description="Test desc",
            emoji="✨",
            category="test"
        )
        assert passive.effects == {}

    def test_passive_has_effect_true(self):
        """Test has_effect returns True when effect exists."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="Test",
            cost=10,
            description="Test",
            emoji="✨",
            category="test",
            effects={"intel_detail_level": "full"}
        )
        assert passive.has_effect("intel_detail_level") is True

    def test_passive_has_effect_false(self):
        """Test has_effect returns False when effect doesn't exist."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="Test",
            cost=10,
            description="Test",
            emoji="✨",
            category="test",
            effects={}
        )
        assert passive.has_effect("intel_detail_level") is False

    def test_passive_get_effect_exists(self):
        """Test get_effect returns value when effect exists."""
        passive = Passive(
            type=PassiveType.ESCAPE_ARTIST,
            name="Test",
            cost=10,
            description="Test",
            emoji="✨",
            category="escape",
            effects={"hide_bonus": 0.15, "run_bonus": 0.15}
        )
        assert passive.get_effect("hide_bonus") == 0.15
        assert passive.get_effect("run_bonus") == 0.15

    def test_passive_get_effect_default(self):
        """Test get_effect returns default when effect doesn't exist."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="Test",
            cost=10,
            description="Test",
            emoji="✨",
            category="test",
            effects={}
        )
        assert passive.get_effect("nonexistent", "default_value") == "default_value"
        assert passive.get_effect("nonexistent") is None


class TestPassiveShop:
    """Tests for PassiveShop class."""

    def test_load_passives_from_config(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test loading passives from config."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        passives = PassiveShop.get_all_passives()
        assert len(passives) == 5

    def test_get_passive_by_type(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting a specific passive by type."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        passive = PassiveShop.get_passive(PassiveType.AI_WHISPERER)
        assert passive is not None
        assert passive.type == PassiveType.AI_WHISPERER
        assert passive.name == "AI Whisperer"
        assert passive.cost == 15

    def test_get_all_passives(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting all passives."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        passives = PassiveShop.get_all_passives()
        assert isinstance(passives, list)
        assert len(passives) == 5
        assert all(isinstance(p, Passive) for p in passives)

    def test_get_passive_by_index_valid(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting passive by valid 1-based index."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        passive = PassiveShop.get_passive_by_index(1)
        assert passive is not None
        assert isinstance(passive, Passive)

    def test_get_passive_by_index_out_of_range(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting passive by out of range index returns None."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        assert PassiveShop.get_passive_by_index(0) is None
        assert PassiveShop.get_passive_by_index(100) is None
        assert PassiveShop.get_passive_by_index(-1) is None

    def test_get_passive_by_index_string_input(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting passive by string index (questionary returns strings)."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        # String "1" should work (questionary returns strings)
        passive = PassiveShop.get_passive_by_index("1")
        assert passive is not None
        assert isinstance(passive, Passive)

        # Invalid strings should return None
        assert PassiveShop.get_passive_by_index("abc") is None
        assert PassiveShop.get_passive_by_index("") is None

    def test_get_passive_count(self, temp_config_dir, temp_passives_config, monkeypatch):
        """Test getting count of available passives."""
        from game.config_loader import ConfigLoader
        ConfigLoader._instance = None
        new_config = ConfigLoader()

        from game import config_loader
        monkeypatch.setattr(config_loader, 'config', new_config)

        PassiveShop.PASSIVES = None
        count = PassiveShop.get_passive_count()
        assert count == 5


class TestPassiveManager:
    """Tests for PassiveManager class."""

    def test_initialization(self):
        """Test PassiveManager initializes with empty passives list."""
        manager = PassiveManager()
        assert manager.passives == []

    def test_add_passive_success(self, sample_passive_manager, temp_passives_config):
        """Test adding a passive successfully."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="Test",
            emoji="🔮",
            category="intel",
            effects={"intel_detail_level": "full"}
        )
        result = sample_passive_manager.add_passive(passive)
        assert result is True
        assert len(sample_passive_manager.passives) == 1

    def test_add_passive_already_owned_returns_false(self, sample_passive_manager):
        """Test adding duplicate passive returns False."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="Test",
            emoji="🔮",
            category="intel"
        )
        sample_passive_manager.add_passive(passive)
        result = sample_passive_manager.add_passive(passive)
        assert result is False
        assert len(sample_passive_manager.passives) == 1

    def test_has_passive_true(self, sample_passive_manager):
        """Test has_passive returns True when passive is owned."""
        passive = Passive(
            type=PassiveType.ESCAPE_ARTIST,
            name="Escape Artist",
            cost=12,
            description="Test",
            emoji="🎭",
            category="escape"
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.has_passive(PassiveType.ESCAPE_ARTIST) is True

    def test_has_passive_false(self, sample_passive_manager):
        """Test has_passive returns False when passive is not owned."""
        assert sample_passive_manager.has_passive(PassiveType.AI_WHISPERER) is False

    def test_get_passive_exists(self, sample_passive_manager):
        """Test get_passive returns passive when owned."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="Test",
            emoji="🔮",
            category="intel"
        )
        sample_passive_manager.add_passive(passive)
        result = sample_passive_manager.get_passive(PassiveType.AI_WHISPERER)
        assert result is not None
        assert result.type == PassiveType.AI_WHISPERER

    def test_get_passive_not_found(self, sample_passive_manager):
        """Test get_passive returns None when not owned."""
        result = sample_passive_manager.get_passive(PassiveType.AI_WHISPERER)
        assert result is None

    def test_get_all_returns_copy(self, sample_passive_manager):
        """Test get_all returns a copy of passives list."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="Test",
            emoji="🔮",
            category="intel"
        )
        sample_passive_manager.add_passive(passive)
        result = sample_passive_manager.get_all()
        assert result == sample_passive_manager.passives
        assert result is not sample_passive_manager.passives  # Should be a copy

    def test_get_effect_value_from_passive(self, sample_passive_manager):
        """Test get_effect_value returns effect value."""
        passive = Passive(
            type=PassiveType.ESCAPE_ARTIST,
            name="Escape Artist",
            cost=12,
            description="Test",
            emoji="🎭",
            category="escape",
            effects={"hide_bonus": 0.15, "run_bonus": 0.15}
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.get_effect_value("hide_bonus") == 0.15

    def test_get_effect_value_default(self, sample_passive_manager):
        """Test get_effect_value returns default when not found."""
        result = sample_passive_manager.get_effect_value("nonexistent", "default")
        assert result == "default"

    def test_get_cumulative_bonus(self, sample_passive_manager):
        """Test get_cumulative_bonus sums bonuses from all passives."""
        passive1 = Passive(
            type=PassiveType.ESCAPE_ARTIST,
            name="Escape Artist",
            cost=12,
            description="Test",
            emoji="🎭",
            category="escape",
            effects={"hide_bonus": 0.15, "run_bonus": 0.15}
        )
        passive2 = Passive(
            type=PassiveType.QUICK_FEET,
            name="Quick Feet",
            cost=12,
            description="Test",
            emoji="👟",
            category="escape",
            effects={"run_bonus": 0.25, "run_retention": 0.95}
        )
        sample_passive_manager.add_passive(passive1)
        sample_passive_manager.add_passive(passive2)
        assert sample_passive_manager.get_cumulative_bonus("run_bonus") == 0.40

    def test_get_intel_level_with_ai_whisperer(self, sample_passive_manager):
        """Test get_intel_level returns 'full' with AI Whisperer."""
        passive = Passive(
            type=PassiveType.AI_WHISPERER,
            name="AI Whisperer",
            cost=15,
            description="Test",
            emoji="🔮",
            category="intel"
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.get_intel_level() == "full"

    def test_get_intel_level_without_ai_whisperer(self, sample_passive_manager):
        """Test get_intel_level returns 'simple' without AI Whisperer."""
        assert sample_passive_manager.get_intel_level() == "simple"

    def test_shows_point_hints_true(self, sample_passive_manager):
        """Test shows_point_hints returns True with Inside Knowledge."""
        passive = Passive(
            type=PassiveType.INSIDE_KNOWLEDGE,
            name="Inside Knowledge",
            cost=10,
            description="Test",
            emoji="📊",
            category="intel"
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.shows_point_hints() is True

    def test_shows_point_hints_false(self, sample_passive_manager):
        """Test shows_point_hints returns False without Inside Knowledge."""
        assert sample_passive_manager.shows_point_hints() is False

    def test_get_hide_bonus(self, sample_passive_manager):
        """Test get_hide_bonus returns cumulative hide bonus."""
        passive = Passive(
            type=PassiveType.ESCAPE_ARTIST,
            name="Escape Artist",
            cost=12,
            description="Test",
            emoji="🎭",
            category="escape",
            effects={"hide_bonus": 0.15}
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.get_hide_bonus() == 0.15

    def test_get_run_bonus(self, sample_passive_manager):
        """Test get_run_bonus returns cumulative run bonus."""
        passive = Passive(
            type=PassiveType.QUICK_FEET,
            name="Quick Feet",
            cost=12,
            description="Test",
            emoji="👟",
            category="escape",
            effects={"run_bonus": 0.25}
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.get_run_bonus() == 0.25

    def test_get_run_retention(self, sample_passive_manager):
        """Test get_run_retention returns custom retention if set."""
        passive = Passive(
            type=PassiveType.QUICK_FEET,
            name="Quick Feet",
            cost=12,
            description="Test",
            emoji="👟",
            category="escape",
            effects={"run_retention": 0.95}
        )
        sample_passive_manager.add_passive(passive)
        assert sample_passive_manager.get_run_retention() == 0.95

    def test_get_run_retention_none(self, sample_passive_manager):
        """Test get_run_retention returns None when not set."""
        assert sample_passive_manager.get_run_retention() is None

    def test_get_high_roller_effect_at_bonus_location(self, sample_passive_manager):
        """Test get_high_roller_effect at bonus location."""
        passive = Passive(
            type=PassiveType.HIGH_ROLLER,
            name="High Roller",
            cost=8,
            description="Test",
            emoji="🎲",
            category="risk",
            effects={
                "bonus_locations": ["Casino Vault", "Bank Heist"],
                "point_bonus": 0.15,
                "bust_chance": 0.20
            }
        )
        sample_passive_manager.add_passive(passive)
        result = sample_passive_manager.get_high_roller_effect("Casino Vault")
        assert result is not None
        assert result["point_bonus"] == 0.15
        assert result["bust_chance"] == 0.20

    def test_get_high_roller_effect_at_non_bonus_location(self, sample_passive_manager):
        """Test get_high_roller_effect at non-bonus location."""
        passive = Passive(
            type=PassiveType.HIGH_ROLLER,
            name="High Roller",
            cost=8,
            description="Test",
            emoji="🎲",
            category="risk",
            effects={
                "bonus_locations": ["Casino Vault"],
                "point_bonus": 0.15,
                "bust_chance": 0.20
            }
        )
        sample_passive_manager.add_passive(passive)
        result = sample_passive_manager.get_high_roller_effect("Corner Store")
        assert result is None

    def test_get_high_roller_effect_without_passive(self, sample_passive_manager):
        """Test get_high_roller_effect without High Roller passive."""
        result = sample_passive_manager.get_high_roller_effect("Casino Vault")
        assert result is None
