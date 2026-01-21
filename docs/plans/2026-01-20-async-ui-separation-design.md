# Async/UI Separation Design

## Problem

Questionary (arrow-key selection library) internally uses `asyncio.run()`. The game loop runs inside `asyncio.run()` for WebSocket communication. When questionary is called during gameplay (location choice, escape choice, shop), it crashes with "asyncio.run() cannot be called from a running event loop".

## Solution

Separate async network operations from sync UI operations using a background thread.

## Architecture

### Two Layers

1. **Main Thread (Sync)** - All UI/terminal interaction
   - Menu selection
   - Location/escape choices during gameplay
   - Shop purchases
   - All questionary calls work naturally

2. **Background Thread (Async)** - Network communication
   - WebSocket connection
   - Receiving server messages
   - Sending player actions
   - Connection state management

### Communication

Thread-safe queues connect the layers:
- `incoming_queue`: Messages from server → main thread
- `outgoing_queue`: Player actions from main thread → server

## Components

### NetworkThread class (new file: client/network_thread.py)

```python
class NetworkThread:
    """Runs asyncio event loop in dedicated thread for network I/O."""

    def __init__(self):
        self.incoming_queue: queue.Queue  # Server → Main thread
        self.outgoing_queue: queue.Queue  # Main thread → Server
        self._thread: threading.Thread
        self._running: bool

    def start(self, url: str) -> bool:
        """Start thread and connect to server."""

    def stop(self):
        """Signal thread to stop and wait for it."""

    def send(self, message_type: str, data: dict):
        """Queue a message to send to server."""

    def poll(self, timeout: float = 0.1) -> Optional[dict]:
        """Non-blocking poll for incoming messages."""
```

### GameClient changes (client/main.py)

- `run()` stays synchronous (main thread)
- Starts NetworkThread on connect
- Main loop: poll incoming_queue, update state, prompt UI when needed
- UI calls (questionary) happen naturally in sync context

### Queue Message Format

```python
# Incoming (server → main thread)
{
    "type": "SERVER_MESSAGE",
    "message_type": "GAME_STATE",  # Original server message type
    "data": {...}
}

{
    "type": "CONNECTION_LOST",
    "error": "Connection closed"
}

# Outgoing (main thread → server)
{
    "type": "SEND",
    "message_type": "LOCATION_CHOICE",
    "data": {"location": 2}
}

{
    "type": "DISCONNECT"
}
```

## Data Flow

### Startup

1. Main thread: Show menu (questionary) → user selects "Host Online"
2. Main thread: Gather input (name, game_name) with questionary
3. Main thread: Create NetworkThread, call start(url)
4. Network thread: Connect to WebSocket, send JOIN
5. Network thread: Receive WELCOME → put in incoming_queue
6. Main thread: Poll incoming_queue, see WELCOME, update state

### Gameplay

1. Network thread: Receives GAME_STATE with phase=CHOOSING → incoming_queue
2. Main thread: Polls queue, sees phase change, calls ui.get_location_choice()
3. Main thread: User picks location (questionary works - we're in sync context)
4. Main thread: Call network.send("LOCATION_CHOICE", {...})
5. Network thread: Sends to server

### Connection Loss

1. Network thread: WebSocket disconnects → put CONNECTION_LOST in incoming_queue
2. Main thread: Sees CONNECTION_LOST, shows error, cleans up
3. Network thread: Stops itself cleanly

## Error Handling

### Connection Errors
- Network thread catches WebSocket exceptions
- Puts CONNECTION_LOST in incoming_queue with error details
- Main thread handles cleanup and shows user-friendly message

### Thread Shutdown
- Main thread calls network.stop()
- Network thread closes WebSocket, stops event loop, exits
- Main thread joins with timeout
- Thread marked as daemon as fallback

### Queue Blocking
- Use queue.get(timeout=0.1) in main thread to stay responsive
- No infinite blocking anywhere

### Hot-seat Multiplayer
- Multiple connections still work
- NetworkThread can manage multiple WebSocket connections
- Messages tagged with connection_id/player_id

## Files

### New
- `client/network_thread.py` - NetworkThread class

### Modified
- `client/main.py` - GameClient refactored to use sync main loop with NetworkThread

### Unchanged
- `client/ui.py` - All questionary code stays as-is
- `client/state.py` - State management unchanged
- `client/handler.py` - Message handling logic reused

## Testing

- Unit tests for NetworkThread (mock WebSocket)
- Integration test: verify questionary works during gameplay
- Manual test: full game flow on Windows executable
