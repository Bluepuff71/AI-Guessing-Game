"""WebSocket message protocol definitions for LOOT RUN multiplayer."""
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
import json


class ServerMessageType(Enum):
    """Message types sent from server to client."""
    # Connection
    WELCOME = "WELCOME"
    ERROR = "ERROR"

    # Lobby
    LOBBY_STATE = "LOBBY_STATE"
    PLAYER_JOINED = "PLAYER_JOINED"
    PLAYER_LEFT = "PLAYER_LEFT"
    PLAYER_READY = "PLAYER_READY"

    # Game state
    GAME_STATE = "GAME_STATE"
    GAME_STARTED = "GAME_STARTED"

    # Round flow
    ROUND_START = "ROUND_START"
    PHASE_CHANGE = "PHASE_CHANGE"
    PLAYER_SUBMITTED = "PLAYER_SUBMITTED"
    ALL_CHOICES_LOCKED = "ALL_CHOICES_LOCKED"
    PLAYER_TIMEOUT = "PLAYER_TIMEOUT"

    # Resolution
    AI_ANALYZING = "AI_ANALYZING"
    ROUND_RESULT = "ROUND_RESULT"

    # Escape
    PLAYER_CAUGHT = "PLAYER_CAUGHT"
    ESCAPE_PHASE = "ESCAPE_PHASE"
    ESCAPE_RESULT = "ESCAPE_RESULT"
    PLAYER_ELIMINATED = "PLAYER_ELIMINATED"

    # Shop
    SHOP_STATE = "SHOP_STATE"
    PURCHASE_RESULT = "PURCHASE_RESULT"

    # Game end
    GAME_OVER = "GAME_OVER"


class ClientMessageType(Enum):
    """Message types sent from client to server."""
    # Connection
    JOIN = "JOIN"
    RECONNECT = "RECONNECT"
    DISCONNECT = "DISCONNECT"

    # Lobby
    READY = "READY"
    UNREADY = "UNREADY"

    # Game actions
    LOCATION_CHOICE = "LOCATION_CHOICE"
    ESCAPE_CHOICE = "ESCAPE_CHOICE"
    SHOP_PURCHASE = "SHOP_PURCHASE"
    SKIP_SHOP = "SKIP_SHOP"


class GamePhase(Enum):
    """Game phases for phase tracking."""
    LOBBY = "lobby"
    SHOP = "shop"
    CHOOSING = "choosing"
    AI_THINKING = "ai_thinking"
    RESOLVING = "resolving"
    ESCAPE = "escape"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"


@dataclass
class Message:
    """Base message class for WebSocket communication."""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "type": self.type,
            "data": self.data
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize message from JSON string."""
        obj = json.loads(json_str)
        return cls(type=obj.get("type", ""), data=obj.get("data", {}))


# Server -> Client message builders
def welcome_message(player_id: str, game_id: str) -> Message:
    """Build welcome message for newly connected player."""
    return Message(
        type=ServerMessageType.WELCOME.value,
        data={
            "player_id": player_id,
            "game_id": game_id
        }
    )


def error_message(code: str, message: str) -> Message:
    """Build error message."""
    return Message(
        type=ServerMessageType.ERROR.value,
        data={
            "code": code,
            "message": message
        }
    )


def lobby_state_message(
    game_id: str,
    players: List[Dict[str, Any]],
    host_id: str,
    settings: Dict[str, Any]
) -> Message:
    """Build lobby state message."""
    return Message(
        type=ServerMessageType.LOBBY_STATE.value,
        data={
            "game_id": game_id,
            "players": players,
            "host_id": host_id,
            "settings": settings
        }
    )


def player_joined_message(player: Dict[str, Any]) -> Message:
    """Build player joined message."""
    return Message(
        type=ServerMessageType.PLAYER_JOINED.value,
        data={"player": player}
    )


def player_left_message(player_id: str, username: str) -> Message:
    """Build player left message."""
    return Message(
        type=ServerMessageType.PLAYER_LEFT.value,
        data={
            "player_id": player_id,
            "username": username
        }
    )


def player_ready_message(player_id: str, username: str, ready: bool) -> Message:
    """Build player ready status message."""
    return Message(
        type=ServerMessageType.PLAYER_READY.value,
        data={
            "player_id": player_id,
            "username": username,
            "ready": ready
        }
    )


def game_state_message(
    game_id: str,
    phase: str,
    round_num: int,
    players: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
    active_events: List[Dict[str, Any]],
    settings: Dict[str, Any],
    previous_ai_location: Optional[str] = None
) -> Message:
    """Build full game state sync message."""
    return Message(
        type=ServerMessageType.GAME_STATE.value,
        data={
            "game_id": game_id,
            "phase": phase,
            "round_num": round_num,
            "players": players,
            "locations": locations,
            "active_events": active_events,
            "settings": settings,
            "previous_ai_location": previous_ai_location
        }
    )


def game_started_message(
    game_id: str,
    players: List[Dict[str, Any]],
    locations: List[Dict[str, Any]],
    ai_status: Dict[str, Any],
    settings: Dict[str, Any]
) -> Message:
    """Build game started message."""
    return Message(
        type=ServerMessageType.GAME_STARTED.value,
        data={
            "game_id": game_id,
            "players": players,
            "locations": locations,
            "ai_status": ai_status,
            "settings": settings
        }
    )


def round_start_message(
    round_num: int,
    timer_seconds: int,
    server_timestamp: int,
    active_events: List[Dict[str, Any]],
    new_events: List[Dict[str, Any]],
    standings: List[Dict[str, Any]],
    previous_ai_location: Optional[str] = None
) -> Message:
    """Build round start message."""
    return Message(
        type=ServerMessageType.ROUND_START.value,
        data={
            "round_num": round_num,
            "timer_seconds": timer_seconds,
            "server_timestamp": server_timestamp,
            "active_events": active_events,
            "new_events": new_events,
            "standings": standings,
            "previous_ai_location": previous_ai_location
        }
    )


def phase_change_message(
    new_phase: str,
    round_num: int,
    data: Optional[Dict[str, Any]] = None
) -> Message:
    """Build phase change message."""
    return Message(
        type=ServerMessageType.PHASE_CHANGE.value,
        data={
            "phase": new_phase,
            "round_num": round_num,
            **(data or {})
        }
    )


def player_submitted_message(player_id: str, username: str) -> Message:
    """Build player submitted choice message (without revealing choice)."""
    return Message(
        type=ServerMessageType.PLAYER_SUBMITTED.value,
        data={
            "player_id": player_id,
            "username": username
        }
    )


def all_choices_locked_message(players_submitted: List[str]) -> Message:
    """Build all choices locked message."""
    return Message(
        type=ServerMessageType.ALL_CHOICES_LOCKED.value,
        data={"players_submitted": players_submitted}
    )


def player_timeout_message(player_id: str, username: str) -> Message:
    """Build player timeout message."""
    return Message(
        type=ServerMessageType.PLAYER_TIMEOUT.value,
        data={
            "player_id": player_id,
            "username": username,
            "assigned_random": True
        }
    )


def ai_analyzing_message(duration_ms: int = 2000) -> Message:
    """Build AI analyzing message."""
    return Message(
        type=ServerMessageType.AI_ANALYZING.value,
        data={"duration_ms": duration_ms}
    )


def round_result_message(
    round_num: int,
    ai_search_location: str,
    ai_search_emoji: str,
    ai_reasoning: str,
    player_results: List[Dict[str, Any]],
    standings: List[Dict[str, Any]]
) -> Message:
    """Build round result message."""
    return Message(
        type=ServerMessageType.ROUND_RESULT.value,
        data={
            "round_num": round_num,
            "ai_search_location": ai_search_location,
            "ai_search_emoji": ai_search_emoji,
            "ai_reasoning": ai_reasoning,
            "player_results": player_results,
            "standings": standings
        }
    )


def player_caught_message(
    player_id: str,
    username: str,
    location: str,
    location_points: int
) -> Message:
    """Build player caught message."""
    return Message(
        type=ServerMessageType.PLAYER_CAUGHT.value,
        data={
            "player_id": player_id,
            "username": username,
            "location": location,
            "location_points": location_points
        }
    )


def escape_phase_message(
    player_id: str,
    username: str,
    location: str,
    location_points: int,
    escape_options: List[Dict[str, Any]],
    timer_seconds: int
) -> Message:
    """Build escape phase message."""
    return Message(
        type=ServerMessageType.ESCAPE_PHASE.value,
        data={
            "player_id": player_id,
            "username": username,
            "location": location,
            "location_points": location_points,
            "escape_options": escape_options,
            "timer_seconds": timer_seconds
        }
    )


def escape_result_message(
    player_id: str,
    username: str,
    player_choice: str,
    player_choice_name: str,
    ai_prediction: str,
    ai_prediction_name: str,
    ai_reasoning: str,
    escaped: bool,
    points_awarded: int,
    passive_saved: bool = False
) -> Message:
    """Build escape result message."""
    return Message(
        type=ServerMessageType.ESCAPE_RESULT.value,
        data={
            "player_id": player_id,
            "username": username,
            "player_choice": player_choice,
            "player_choice_name": player_choice_name,
            "ai_prediction": ai_prediction,
            "ai_prediction_name": ai_prediction_name,
            "ai_reasoning": ai_reasoning,
            "escaped": escaped,
            "points_awarded": points_awarded,
            "passive_saved": passive_saved
        }
    )


def player_eliminated_message(
    player_id: str,
    username: str,
    final_score: int
) -> Message:
    """Build player eliminated message."""
    return Message(
        type=ServerMessageType.PLAYER_ELIMINATED.value,
        data={
            "player_id": player_id,
            "username": username,
            "final_score": final_score
        }
    )


def shop_state_message(
    player_id: str,
    player_points: int,
    available_passives: List[Dict[str, Any]],
    owned_passives: List[str],
    timer_seconds: int
) -> Message:
    """Build shop state message."""
    return Message(
        type=ServerMessageType.SHOP_STATE.value,
        data={
            "player_id": player_id,
            "player_points": player_points,
            "available_passives": available_passives,
            "owned_passives": owned_passives,
            "timer_seconds": timer_seconds
        }
    )


def purchase_result_message(
    player_id: str,
    success: bool,
    passive_name: Optional[str] = None,
    error: Optional[str] = None,
    new_points: Optional[int] = None
) -> Message:
    """Build purchase result message."""
    return Message(
        type=ServerMessageType.PURCHASE_RESULT.value,
        data={
            "player_id": player_id,
            "success": success,
            "passive_name": passive_name,
            "error": error,
            "new_points": new_points
        }
    )


def game_over_message(
    winner: Optional[Dict[str, Any]],
    ai_wins: bool,
    final_standings: List[Dict[str, Any]],
    rounds_played: int,
    game_duration_seconds: int
) -> Message:
    """Build game over message."""
    return Message(
        type=ServerMessageType.GAME_OVER.value,
        data={
            "winner": winner,
            "ai_wins": ai_wins,
            "final_standings": final_standings,
            "rounds_played": rounds_played,
            "game_duration_seconds": game_duration_seconds
        }
    )


# Client -> Server message parsers
def parse_join_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JOIN message data."""
    return {
        "username": data.get("username", ""),
        "profile_id": data.get("profile_id")
    }


def parse_reconnect_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse RECONNECT message data."""
    return {
        "player_id": data.get("player_id", ""),
        "game_id": data.get("game_id", "")
    }


def parse_location_choice_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse LOCATION_CHOICE message data."""
    return {
        "location_index": data.get("location_index", -1)
    }


def parse_escape_choice_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse ESCAPE_CHOICE message data."""
    return {
        "option_id": data.get("option_id", "")
    }


def parse_shop_purchase_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse SHOP_PURCHASE message data."""
    return {
        "passive_id": data.get("passive_id", "")
    }
