"""WebSocket connection manager for LOOT RUN client."""

import asyncio
import json
from typing import Optional, Callable, Awaitable, Dict, Any

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketClientProtocol = None

from server.protocol import Message, ClientMessageType


class ConnectionManager:
    """Manages WebSocket connection to game server."""

    def __init__(self):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.player_id: Optional[str] = None
        self.game_id: Optional[str] = None
        self.connected = False
        self._message_handler: Optional[Callable[[Message], Awaitable[None]]] = None
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self, uri: str) -> bool:
        """Connect to server at given URI."""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not installed")

        try:
            self.websocket = await websockets.connect(uri)
            self.connected = True
            return True
        except Exception as e:
            self.connected = False
            raise ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self):
        """Disconnect from server."""
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

    def set_message_handler(self, handler: Callable[[Message], Awaitable[None]]):
        """Set handler for incoming messages."""
        self._message_handler = handler

    async def start_receiving(self):
        """Start receiving messages in background."""
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def _receive_loop(self):
        """Receive messages from server."""
        if not self.websocket:
            return

        try:
            async for raw_message in self.websocket:
                msg = Message.from_json(raw_message)
                if self._message_handler:
                    await self._message_handler(msg)
        except asyncio.CancelledError:
            pass
        except Exception:
            self.connected = False

    async def send(self, message: Message):
        """Send message to server."""
        if not self.websocket or not self.connected:
            raise RuntimeError("Not connected")
        await self.websocket.send(message.to_json())

    async def send_join(self, username: str, profile_id: Optional[str] = None):
        """Send JOIN message."""
        await self.send(Message(
            type=ClientMessageType.JOIN.value,
            data={"username": username, "profile_id": profile_id}
        ))

    async def send_ready(self):
        """Send READY message."""
        await self.send(Message(type=ClientMessageType.READY.value, data={}))

    async def send_unready(self):
        """Send UNREADY message."""
        await self.send(Message(type=ClientMessageType.UNREADY.value, data={}))

    async def send_location_choice(self, location_index: int):
        """Send LOCATION_CHOICE message."""
        await self.send(Message(
            type=ClientMessageType.LOCATION_CHOICE.value,
            data={"location_index": location_index}
        ))

    async def send_escape_choice(self, option_id: str):
        """Send ESCAPE_CHOICE message."""
        await self.send(Message(
            type=ClientMessageType.ESCAPE_CHOICE.value,
            data={"option_id": option_id}
        ))

    async def send_shop_purchase(self, passive_id: str):
        """Send SHOP_PURCHASE message."""
        await self.send(Message(
            type=ClientMessageType.SHOP_PURCHASE.value,
            data={"passive_id": passive_id}
        ))

    async def send_skip_shop(self):
        """Send SKIP_SHOP message."""
        await self.send(Message(type=ClientMessageType.SKIP_SHOP.value, data={}))
