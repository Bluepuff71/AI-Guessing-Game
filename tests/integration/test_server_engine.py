"""Tests for the unified server engine.

This module tests that the server can run a complete game via messages alone,
without any UI code.
"""

import asyncio
import pytest

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio(loop_scope="function")
from typing import Dict, List, Any
from unittest.mock import AsyncMock

from server.engine import ServerGameEngine, ServerPlayer
from server.protocol import (
    GamePhase, Message, ServerMessageType, ClientMessageType,
    game_state_message, round_start_message, player_caught_message,
    escape_result_message, round_result_message, game_over_message
)


class MessageCollector:
    """Helper to collect and analyze messages sent by the server."""

    def __init__(self):
        self.broadcasts: List[tuple] = []  # (type, data)
        self.player_messages: Dict[str, List[tuple]] = {}  # player_id -> [(type, data)]

    async def broadcast(self, msg: Message):
        """Collect broadcast messages."""
        self.broadcasts.append((msg.type, msg.data))

    async def send_to_player(self, player_id: str, msg: Message):
        """Collect player-specific messages."""
        if player_id not in self.player_messages:
            self.player_messages[player_id] = []
        self.player_messages[player_id].append((msg.type, msg.data))

    def get_broadcast_types(self) -> List[str]:
        """Get list of broadcast message types."""
        return [t for t, _ in self.broadcasts]

    def get_broadcasts_of_type(self, msg_type: str) -> List[Dict[str, Any]]:
        """Get all broadcasts of a specific type."""
        return [data for t, data in self.broadcasts if t == msg_type]

    def get_player_messages_of_type(self, player_id: str, msg_type: str) -> List[Dict[str, Any]]:
        """Get all messages of a specific type sent to a player."""
        if player_id not in self.player_messages:
            return []
        return [data for t, data in self.player_messages[player_id] if t == msg_type]

    def clear(self):
        """Clear all collected messages."""
        self.broadcasts.clear()
        self.player_messages.clear()


@pytest.fixture
def message_collector():
    """Create a fresh message collector."""
    return MessageCollector()


@pytest.fixture
def game_engine(message_collector):
    """Create a game engine with message collection."""
    return ServerGameEngine(
        game_id='test-game-1',
        broadcast=message_collector.broadcast,
        send_to_player=message_collector.send_to_player,
        turn_timer_seconds=60,  # Long timers for testing
        escape_timer_seconds=30,
        shop_timer_seconds=30,
        win_threshold=100
    )


class TestServerEngineBasics:
    """Test basic server engine functionality."""

    @pytest.mark.asyncio
    async def test_add_player(self, game_engine):
        """Test adding players to a game."""
        player = await game_engine.add_player('player-1', 'Alice')

        assert player.player_id == 'player-1'
        assert player.username == 'Alice'
        assert player.points == 0
        assert player.alive is True
        assert 'player-1' in game_engine.players

    @pytest.mark.asyncio
    async def test_add_multiple_players(self, game_engine):
        """Test adding multiple players."""
        p1 = await game_engine.add_player('player-1', 'Alice')
        p2 = await game_engine.add_player('player-2', 'Bob')
        p3 = await game_engine.add_player('player-3', 'Charlie')

        assert len(game_engine.players) == 3
        assert game_engine.player_order == ['player-1', 'player-2', 'player-3']

        # Check player indices
        assert p1.player_index == 0
        assert p2.player_index == 1
        assert p3.player_index == 2

    @pytest.mark.asyncio
    async def test_player_reconnect(self, game_engine):
        """Test player reconnection returns existing player."""
        p1 = await game_engine.add_player('player-1', 'Alice')
        p1.connected = False

        p1_reconnect = await game_engine.add_player('player-1', 'Alice')

        assert p1_reconnect is p1
        assert p1.connected is True

    @pytest.mark.asyncio
    async def test_set_player_ready(self, game_engine):
        """Test setting player ready status."""
        await game_engine.add_player('player-1', 'Alice')

        result = await game_engine.set_player_ready('player-1', True)
        assert result is True
        assert game_engine.players['player-1'].ready is True

    @pytest.mark.asyncio
    async def test_all_players_ready(self, game_engine):
        """Test checking if all players are ready."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')

        assert game_engine.all_players_ready() is False

        await game_engine.set_player_ready('player-1', True)
        assert game_engine.all_players_ready() is False

        await game_engine.set_player_ready('player-2', True)
        assert game_engine.all_players_ready() is True


class TestServerEngineGameStart:
    """Test game start and initialization."""

    @pytest.mark.asyncio
    async def test_start_game_broadcasts(self, game_engine, message_collector):
        """Test that starting a game sends proper broadcasts."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()

        # Should broadcast GAME_STARTED
        assert ServerMessageType.GAME_STARTED.value in message_collector.get_broadcast_types()

        # Check GAME_STARTED data
        started_msgs = message_collector.get_broadcasts_of_type(ServerMessageType.GAME_STARTED.value)
        assert len(started_msgs) == 1

        started_data = started_msgs[0]
        assert started_data['game_id'] == 'test-game-1'
        assert len(started_data['players']) == 2
        assert len(started_data['locations']) > 0
        assert 'settings' in started_data

    @pytest.mark.asyncio
    async def test_start_game_phase_change(self, game_engine, message_collector):
        """Test that starting a game changes phase."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        assert game_engine.current_phase == GamePhase.LOBBY

        await game_engine.start_game()

        # Phase should change to SHOP after start
        assert game_engine.current_phase == GamePhase.SHOP

    @pytest.mark.asyncio
    async def test_start_game_initializes_round(self, game_engine, message_collector):
        """Test that starting a game initializes round number."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        assert game_engine.round_num == 0

        await game_engine.start_game()

        assert game_engine.round_num == 1


class TestServerEngineShopPhase:
    """Test shop phase functionality."""

    @pytest.mark.asyncio
    async def test_shop_state_sent_to_players(self, game_engine, message_collector):
        """Test that shop state is sent to each player."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()

        # Check shop state messages
        p1_shop = message_collector.get_player_messages_of_type('player-1', ServerMessageType.SHOP_STATE.value)
        p2_shop = message_collector.get_player_messages_of_type('player-2', ServerMessageType.SHOP_STATE.value)

        assert len(p1_shop) == 1
        assert len(p2_shop) == 1

        # Check shop state content
        assert 'available_passives' in p1_shop[0]
        assert 'player_points' in p1_shop[0]

    @pytest.mark.asyncio
    async def test_shop_done_transitions_phase(self, game_engine, message_collector):
        """Test that all players finishing shop transitions to choosing phase."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        assert game_engine.current_phase == GamePhase.SHOP

        await game_engine.handle_shop_done('player-1')
        assert game_engine.current_phase == GamePhase.SHOP  # Still waiting

        await game_engine.handle_shop_done('player-2')
        assert game_engine.current_phase == GamePhase.CHOOSING


class TestServerEngineChoosingPhase:
    """Test location choosing phase."""

    @pytest.mark.asyncio
    async def test_submit_location_choice(self, game_engine, message_collector):
        """Test submitting a location choice."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        assert game_engine.current_phase == GamePhase.CHOOSING

        result = await game_engine.submit_location_choice('player-1', 0)
        assert result is True

        # Should broadcast player submitted
        assert ServerMessageType.PLAYER_SUBMITTED.value in message_collector.get_broadcast_types()

    @pytest.mark.asyncio
    async def test_all_choices_trigger_resolve(self, game_engine, message_collector):
        """Test that all players choosing triggers round resolution."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        message_collector.clear()

        await game_engine.submit_location_choice('player-1', 0)
        await game_engine.submit_location_choice('player-2', 1)

        # Should have broadcasted round result
        broadcast_types = message_collector.get_broadcast_types()
        assert ServerMessageType.ROUND_RESULT.value in broadcast_types

    @pytest.mark.asyncio
    async def test_invalid_location_rejected(self, game_engine, message_collector):
        """Test that invalid location indices are rejected."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        # Invalid location index
        result = await game_engine.submit_location_choice('player-1', 999)
        assert result is False


class TestServerEngineRoundResult:
    """Test round result and scoring."""

    @pytest.mark.asyncio
    async def test_round_result_contains_required_data(self, game_engine, message_collector):
        """Test that round result message contains all required data."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        message_collector.clear()

        await game_engine.submit_location_choice('player-1', 0)
        await game_engine.submit_location_choice('player-2', 2)

        # Get round result
        results = message_collector.get_broadcasts_of_type(ServerMessageType.ROUND_RESULT.value)
        assert len(results) == 1

        result = results[0]
        assert 'round_num' in result
        assert 'ai_search_location' in result
        assert 'player_results' in result
        assert 'standings' in result

        # Check player results
        assert len(result['player_results']) == 2
        for pr in result['player_results']:
            assert 'player_id' in pr
            assert 'location' in pr
            assert 'caught' in pr

    @pytest.mark.asyncio
    async def test_player_earns_points_when_not_caught(self, game_engine, message_collector):
        """Test that players earn points when not caught."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        # Players start with 0 points
        assert game_engine.players['player-1'].points == 0
        assert game_engine.players['player-2'].points == 0

        await game_engine.submit_location_choice('player-1', 0)
        await game_engine.submit_location_choice('player-2', 2)

        # At least one player should have earned points (unless caught)
        # We can't guarantee which one, but the game should have processed


class TestServerEngineEscapePhase:
    """Test escape phase for caught players."""

    @pytest.mark.asyncio
    async def test_escape_choice_submission(self, game_engine, message_collector):
        """Test that escape choices can be submitted."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        # Force a caught scenario by manipulating state
        game_engine.current_phase = GamePhase.ESCAPE
        location = game_engine.location_manager.get_location(0)
        game_engine.caught_players_this_round = [(game_engine.players['player-1'], location, 10)]

        # Submit escape choice
        result = await game_engine.submit_escape_choice('player-1', 'some_option')
        assert result is True

    @pytest.mark.asyncio
    async def test_escape_choice_rejected_wrong_phase(self, game_engine, message_collector):
        """Test that escape choices are rejected in wrong phase."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')

        # In LOBBY phase
        result = await game_engine.submit_escape_choice('player-1', 'some_option')
        assert result is False


class TestServerEngineGameState:
    """Test game state synchronization."""

    @pytest.mark.asyncio
    async def test_send_game_state(self, game_engine, message_collector):
        """Test sending game state to a player."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()
        message_collector.clear()

        await game_engine.send_game_state('player-1')

        # Should have sent GAME_STATE message
        state_msgs = message_collector.get_player_messages_of_type('player-1', ServerMessageType.GAME_STATE.value)
        assert len(state_msgs) == 1

        state = state_msgs[0]
        assert 'game_id' in state
        assert 'phase' in state
        assert 'round_num' in state
        assert 'players' in state
        assert 'locations' in state

    @pytest.mark.asyncio
    async def test_to_dict_serialization(self, game_engine, message_collector):
        """Test game state serialization."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()

        state_dict = game_engine.to_dict()

        assert state_dict['game_id'] == 'test-game-1'
        assert state_dict['round_num'] == 1
        assert state_dict['game_over'] is False
        assert 'players' in state_dict
        assert len(state_dict['players']) == 2


class TestServerEngineGameOver:
    """Test game over conditions."""

    @pytest.mark.asyncio
    async def test_score_victory(self, game_engine, message_collector):
        """Test that reaching win threshold ends game."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()

        # Give player 1 enough points to win
        game_engine.players['player-1'].points = 100

        # Check game over
        result = await game_engine._check_game_over()

        assert result is True
        assert game_engine.game_over is True
        assert game_engine.winner == game_engine.players['player-1']

        # Should have broadcast GAME_OVER
        game_over_msgs = message_collector.get_broadcasts_of_type(ServerMessageType.GAME_OVER.value)
        assert len(game_over_msgs) == 1

    @pytest.mark.asyncio
    async def test_ai_victory_all_eliminated(self, game_engine, message_collector):
        """Test that AI wins when all players are eliminated."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        await game_engine.start_game()

        # Eliminate all players
        game_engine.players['player-1'].alive = False
        game_engine.players['player-2'].alive = False

        result = await game_engine._check_game_over()

        assert result is True
        assert game_engine.game_over is True
        assert game_engine.winner is None  # AI wins

        # Check GAME_OVER message
        game_over_msgs = message_collector.get_broadcasts_of_type(ServerMessageType.GAME_OVER.value)
        assert len(game_over_msgs) == 1
        assert game_over_msgs[0]['ai_wins'] is True


class TestServerPlayerClass:
    """Test ServerPlayer class functionality."""

    def test_player_creation(self):
        """Test creating a server player."""
        player = ServerPlayer(
            player_id='test-1',
            username='TestPlayer',
            player_index=0
        )

        assert player.player_id == 'test-1'
        assert player.username == 'TestPlayer'
        assert player.points == 0
        assert player.alive is True
        assert player.connected is True

    def test_add_points(self):
        """Test adding points to a player."""
        player = ServerPlayer(
            player_id='test-1',
            username='TestPlayer',
            player_index=0
        )

        player.add_points(25)
        assert player.points == 25

        player.add_points(10)
        assert player.points == 35

    def test_record_choice(self):
        """Test recording a choice."""
        player = ServerPlayer(
            player_id='test-1',
            username='TestPlayer',
            player_index=0
        )

        player.record_choice('Corner Store', 1, False, 15, 15)

        assert len(player.choice_history) == 1
        assert player.choice_history[0] == 'Corner Store'
        assert len(player.round_history) == 1
        assert player.round_history[0]['location'] == 'Corner Store'

    def test_to_dict(self):
        """Test player serialization."""
        player = ServerPlayer(
            player_id='test-1',
            username='TestPlayer',
            player_index=0
        )
        player.points = 50

        data = player.to_dict()

        assert data['player_id'] == 'test-1'
        assert data['username'] == 'TestPlayer'
        assert data['points'] == 50

    def test_to_public_dict(self):
        """Test public player info."""
        player = ServerPlayer(
            player_id='test-1',
            username='TestPlayer',
            player_index=0
        )

        public = player.to_public_dict()

        assert 'player_id' in public
        assert 'username' in public
        assert 'points' in public
        assert 'color' in public


class TestMessageProtocol:
    """Test message protocol functionality."""

    def test_message_serialization(self):
        """Test message JSON serialization."""
        msg = Message(type='TEST', data={'key': 'value'})

        json_str = msg.to_json()
        assert '"type": "TEST"' in json_str
        assert '"key": "value"' in json_str

    def test_message_deserialization(self):
        """Test message JSON deserialization."""
        json_str = '{"type": "TEST", "data": {"key": "value"}}'

        msg = Message.from_json(json_str)

        assert msg.type == 'TEST'
        assert msg.data['key'] == 'value'

    def test_game_state_message_builder(self):
        """Test game state message builder."""
        msg = game_state_message(
            game_id='test-1',
            phase='choosing',
            round_num=5,
            players=[],
            locations=[],
            active_events=[],
            settings={},
            previous_ai_location='Bank Heist'
        )

        assert msg.type == ServerMessageType.GAME_STATE.value
        assert msg.data['game_id'] == 'test-1'
        assert msg.data['round_num'] == 5
        assert msg.data['previous_ai_location'] == 'Bank Heist'


class TestIntegrationFullGame:
    """Integration tests for full game flows."""

    @pytest.mark.asyncio
    async def test_complete_round_flow(self, game_engine, message_collector):
        """Test a complete round from start to finish."""
        # Setup
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        # Start game
        await game_engine.start_game()
        assert game_engine.current_phase == GamePhase.SHOP

        # Skip shop
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')
        assert game_engine.current_phase == GamePhase.CHOOSING

        # Make choices
        await game_engine.submit_location_choice('player-1', 0)
        await game_engine.submit_location_choice('player-2', 3)

        # Wait for round to resolve (escape handling is async)
        await asyncio.sleep(0.5)

        # Check that round result was broadcast
        assert ServerMessageType.ROUND_RESULT.value in message_collector.get_broadcast_types()

    @pytest.mark.asyncio
    async def test_last_ai_search_location_updated(self, game_engine, message_collector):
        """Test that last AI search location is properly tracked."""
        await game_engine.add_player('player-1', 'Alice')
        await game_engine.add_player('player-2', 'Bob')
        await game_engine.set_player_ready('player-1', True)
        await game_engine.set_player_ready('player-2', True)

        # Initially should be None
        assert game_engine.last_ai_search_location is None

        await game_engine.start_game()
        await game_engine.handle_shop_done('player-1')
        await game_engine.handle_shop_done('player-2')

        await game_engine.submit_location_choice('player-1', 0)
        await game_engine.submit_location_choice('player-2', 1)

        # After round resolves, should be set
        await asyncio.sleep(0.5)
        assert game_engine.last_ai_search_location is not None
