"""NetworkThread: Runs asyncio event loop in dedicated thread for WebSocket communication.

This module provides a bridge between the synchronous main thread (which uses
questionary for UI) and the asynchronous WebSocket communication with the
game server.
"""

import asyncio
import queue
import threading
from typing import Optional

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    ConnectionClosed = Exception
    ConnectionClosedError = Exception
    ConnectionClosedOK = Exception

from server.protocol import Message


class NetworkThread:
    """Runs asyncio event loop in dedicated thread for network I/O.

    This class manages a background thread that handles WebSocket communication,
    allowing the main thread to remain synchronous for UI operations.

    Queue message formats:

    Incoming (server -> main thread):
        {"type": "CONNECTED"}
        {"type": "SERVER_MESSAGE", "message_type": "...", "data": {...}}
        {"type": "CONNECTION_LOST", "error": "..."}

    Outgoing (main thread -> server):
        {"type": "SEND", "message_type": "...", "data": {...}}
        {"type": "DISCONNECT"}
    """

    # How often to check outgoing queue when connected (seconds)
    QUEUE_POLL_INTERVAL = 0.05

    # Timeout for thread stop operation (seconds)
    STOP_TIMEOUT = 5.0

    def __init__(self):
        """Initialize the NetworkThread."""
        self.incoming_queue: queue.Queue = queue.Queue()
        self.outgoing_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._url: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if the network thread is currently running."""
        return not self._stop_event.is_set() and self._thread is not None and self._thread.is_alive()

    def start(self, url: str) -> bool:
        """Start thread and connect to server.

        Args:
            url: WebSocket URL to connect to (e.g., "ws://localhost:8765")

        Returns:
            True if thread started successfully, False otherwise.
        """
        if not WEBSOCKETS_AVAILABLE:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": "websockets library not installed"
            })
            return False

        if self.is_running:
            return False

        self._url = url
        self._stop_event.clear()

        # Create and start the background thread
        self._thread = threading.Thread(
            target=self._thread_main,
            name="NetworkThread",
            daemon=True
        )
        self._thread.start()
        return True

    def stop(self):
        """Signal thread to stop and wait for it to finish."""
        if not self.is_running:
            return

        self._stop_event.set()

        # Queue a disconnect message to wake up the thread
        self.outgoing_queue.put({"type": "DISCONNECT"})

        # Wait for thread to finish with timeout
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=self.STOP_TIMEOUT)

        self._thread = None
        self._loop = None

    def send(self, message_type: str, data: dict):
        """Queue a message to send to server.

        Args:
            message_type: The type of message (e.g., "LOCATION_CHOICE")
            data: The message payload data
        """
        self.outgoing_queue.put({
            "type": "SEND",
            "message_type": message_type,
            "data": data
        })

    def poll(self, timeout: float = 0.1) -> Optional[dict]:
        """Non-blocking poll for incoming messages.

        Args:
            timeout: Maximum time to wait for a message (seconds)

        Returns:
            A message dict if available, None if timeout elapsed.
        """
        try:
            return self.incoming_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _thread_main(self):
        """Main entry point for the background thread."""
        # Create a new event loop for this thread
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": str(e)
            })
        finally:
            self._loop.close()
            self._loop = None

    async def _async_main(self):
        """Main async logic for the network thread."""
        websocket = None

        try:
            # Connect to the server
            websocket = await websockets.connect(self._url)

            # Signal successful connection
            self.incoming_queue.put({"type": "CONNECTED"})

            # Run send and receive tasks concurrently
            receive_task = asyncio.create_task(self._receive_loop(websocket))
            send_task = asyncio.create_task(self._send_loop(websocket))

            # Wait for either task to complete (or stop signal)
            done, pending = await asyncio.wait(
                [receive_task, send_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except ConnectionRefusedError:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": "Connection refused"
            })
        except Exception as e:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": str(e)
            })
        finally:
            if websocket is not None:
                try:
                    await websocket.close()
                except Exception:
                    pass

    async def _receive_loop(self, websocket):
        """Receive messages from the WebSocket and put them in the incoming queue."""
        try:
            async for raw_message in websocket:
                if self._stop_event.is_set():
                    break

                # Parse the message using the protocol
                msg = Message.from_json(raw_message)

                # Put it in the incoming queue
                self.incoming_queue.put({
                    "type": "SERVER_MESSAGE",
                    "message_type": msg.type,
                    "data": msg.data
                })

        except ConnectionClosed:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": "Connection closed"
            })
        except Exception as e:
            self.incoming_queue.put({
                "type": "CONNECTION_LOST",
                "error": str(e)
            })

    async def _send_loop(self, websocket):
        """Poll the outgoing queue and send messages over the WebSocket."""
        while not self._stop_event.is_set():
            try:
                # Check for outgoing messages (non-blocking with short timeout)
                try:
                    msg = self.outgoing_queue.get_nowait()
                except queue.Empty:
                    # No message, wait a bit and continue
                    await asyncio.sleep(self.QUEUE_POLL_INTERVAL)
                    continue

                if msg["type"] == "DISCONNECT":
                    # Stop signal received
                    break

                elif msg["type"] == "SEND":
                    # Create and send the message
                    message = Message(
                        type=msg["message_type"],
                        data=msg["data"]
                    )
                    await websocket.send(message.to_json())

            except ConnectionClosed:
                self.incoming_queue.put({
                    "type": "CONNECTION_LOST",
                    "error": "Connection closed"
                })
                break
            except Exception as e:
                self.incoming_queue.put({
                    "type": "CONNECTION_LOST",
                    "error": str(e)
                })
                break
