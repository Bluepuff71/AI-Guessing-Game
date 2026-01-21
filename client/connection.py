"""WebSocket connection manager for LOOT RUN client."""

import asyncio
import json
from typing import Optional, Callable, Awaitable, Dict, Any

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketClientProtocol = None
    ConnectionClosed = Exception
    ConnectionClosedError = Exception
    ConnectionClosedOK = Exception

from server.protocol import Message, ClientMessageType


class ConnectionManager:
    """Manages WebSocket connection to game server."""

    # Reconnection settings
    MAX_RECONNECT_ATTEMPTS = 5
    INITIAL_BACKOFF_SECONDS = 1.0
    MAX_BACKOFF_SECONDS = 30.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(self):
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.player_id: Optional[str] = None
        self.game_id: Optional[str] = None
        self.connected = False
        self._message_handler: Optional[Callable[[Message], Awaitable[None]]] = None
        self._receive_task: Optional[asyncio.Task] = None
        self._on_disconnect: Optional[Callable[[], Awaitable[None]]] = None
        self._last_uri: Optional[str] = None
        self._reconnecting = False

    def set_on_disconnect(self, callback: Optional[Callable[[], Awaitable[None]]]):
        """Set callback to be called when connection is lost."""
        self._on_disconnect = callback

    async def connect(self, uri: str) -> bool:
        """Connect to server at given URI."""
        if not WEBSOCKETS_AVAILABLE:
            raise RuntimeError("websockets library not installed")

        try:
            self._last_uri = uri
            self.websocket = await websockets.connect(uri)
            self.connected = True
            self._reconnecting = False
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
        except ConnectionClosed as e:
            # Connection was closed (either normally or unexpectedly)
            self.connected = False
            if self._on_disconnect:
                await self._on_disconnect()
        except Exception:
            self.connected = False
            if self._on_disconnect:
                await self._on_disconnect()

    async def reconnect(self) -> bool:
        """Attempt to reconnect to the server with exponential backoff.

        Returns True if reconnection succeeded, False otherwise.
        """
        if not self._last_uri:
            return False

        if self._reconnecting:
            return False  # Already attempting reconnection

        self._reconnecting = True
        backoff = self.INITIAL_BACKOFF_SECONDS

        for attempt in range(1, self.MAX_RECONNECT_ATTEMPTS + 1):
            try:
                # Clean up old connection
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except Exception:
                        pass
                    self.websocket = None

                # Try to reconnect
                self.websocket = await websockets.connect(self._last_uri)
                self.connected = True
                self._reconnecting = False

                # Restart the receive loop
                await self.start_receiving()

                return True
            except Exception:
                if attempt < self.MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * self.BACKOFF_MULTIPLIER, self.MAX_BACKOFF_SECONDS)

        self._reconnecting = False
        return False

    def is_reconnecting(self) -> bool:
        """Check if currently attempting to reconnect."""
        return self._reconnecting

    async def send(self, message: Message):
        """Send message to server."""
        if not self.websocket or not self.connected:
            raise RuntimeError("Not connected")
        try:
            await self.websocket.send(message.to_json())
        except ConnectionClosed:
            self.connected = False
            if self._on_disconnect:
                await self._on_disconnect()
            raise RuntimeError("Not connected")

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
