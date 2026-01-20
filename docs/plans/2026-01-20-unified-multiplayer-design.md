# Unified Multiplayer Architecture Design

## Overview

Refactor LOOT RUN to use a unified client-server architecture (Minecraft-style) where game logic lives entirely on the server. Single-player, local multiplayer, and online multiplayer all use the same server implementation.

## Architecture

### Single-player / Local Multiplayer
```
┌─────────────────────────────────┐
│          Game Server            │
│  (subprocess on same machine)   │
└─────────────────────────────────┘
              ▲
              │ WebSocket (localhost)
              ▼
       ┌─────────────┐
       │  Terminal   │
       │   Client    │
       │ [1-6 local  │
       │  players]   │
       └─────────────┘
```

### Online Multiplayer
```
┌─────────────────────────────────┐
│          Game Server            │
│   (on host's machine, exposed)  │
└─────────────────────────────────┘
        ▲               ▲
        │ localhost     │ LAN / Internet
        ▼               ▼
   ┌──────────┐   ┌──────────┐
   │ Terminal │   │ Terminal │
   │ (Host)   │   │ (Guest)  │
   │ 1 player │   │ 1 player │
   └──────────┘   └──────────┘
```

**Key distinction:** Local mode allows hot-seat (multiple players, one terminal). Online mode is one player per terminal. A game is either local OR online, not mixed.

## Game Modes

### Main Menu Options
1. **Single Player** - Start local server, one human vs Seeker AI
2. **Local Multiplayer** - Start local server, 2-6 humans (hot-seat) vs Seeker AI
3. **Host Online Game** - Start server exposed on network, host joins as player
4. **Join Online Game** - Browse LAN or enter IP to connect

### Game Flow (all modes)
```
Main Menu
    │
    ▼
Lobby (wait for players / ready up)
    │
    ▼
Game Loop:
    ├── Shop Phase (buy items/passives)
    ├── Location Selection (all players choose secretly)
    ├── Seeker AI decides where to search
    ├── Results (caught players → escape attempt)
    └── Repeat until win condition
    │
    ▼
Game Over (show winner, return to menu)
```

### Win Conditions
- First player to 100 points wins
- Last player standing wins (if others eliminated)
- Seeker wins if all players eliminated

## Server Responsibilities

The server owns all game state and logic. Clients are purely input/display.

### Server handles:
- Game state (scores, player status, current round, phase)
- Seeker AI decisions (where to search, escape predictions)
- Location data (point values, events)
- Shop inventory and purchases
- Turn timing and phase transitions
- Validating player actions

### Server does NOT handle:
- Display/rendering
- Input collection
- Sound/effects

### Message Types (Server → Client)
- `GAME_STATE` - Full state sync (on connect, round start)
- `PHASE_CHANGE` - Moving to next phase
- `PLAYER_CAUGHT` - Someone got caught, escape phase starting
- `ESCAPE_RESULT` - Outcome of escape attempt
- `ROUND_RESULT` - Points awarded, updated scores
- `GAME_OVER` - Winner announced

### Message Types (Client → Server)
- `JOIN` - Player joining with name
- `READY` - Player ready to start
- `LOCATION_CHOICE` - Where the player is looting
- `ESCAPE_CHOICE` - Hide or run decision
- `SHOP_PURCHASE` - Buying item/passive

## Client Responsibilities

### Terminal client handles:
- Rendering game state (using `rich` library)
- Collecting player input
- Managing local players in hot-seat mode
- Connecting to server (spawn local or connect remote)
- LAN discovery (broadcasting/listening for games)

### Hot-seat mode specifics:
- Client tracks which local players have submitted choices
- Each player takes their turn privately (screen clears between players)
- Only sends choices to server once all local players have decided
- Prevents players from seeing each other's choices

### Online mode specifics:
- One player per client
- Client displays "waiting for other players" during selection phase

### Server spawning (Host):
- Client starts server as subprocess
- Waits for server to be ready (health check)
- Connects like any other client
- On exit, client terminates the server subprocess

## LAN Discovery & Connection

### LAN Discovery (UDP Broadcast)
- Server broadcasts presence on UDP port (e.g., 19132) every 2 seconds
- Broadcast contains: game name, host name, player count, max players, port
- Clients listen for broadcasts when browsing for games
- Stops broadcasting once game starts

### Connection Flow (Host)
1. Player selects "Host Online Game"
2. Server starts, binds WebSocket to `0.0.0.0:<port>`
3. Server starts UDP broadcast
4. Host's client connects to `localhost:<port>`
5. Lobby shows join code (IP:port) and player list
6. Host starts game when ready

### Connection Flow (Guest)
1. Player selects "Join Online Game"
2. Client listens for UDP broadcasts, displays found games
3. Or player manually enters IP:port
4. Client connects via WebSocket
5. Enters name, joins lobby
6. Waits for host to start

**No late joins:** Once game starts, no new players can join.

## Code Changes

### What stays:
- `game/locations.py` - Location definitions, point values
- `game/events.py` - Event system
- `game/hiding.py` - Escape options per location
- `ai/predictor.py` - Seeker AI logic (ML model)
- `ai/escape_predictor.py` - Escape prediction
- `config/` - Game configuration

### What gets refactored:
- `game/engine.py` → Move game logic to `server/engine.py`. Remove all UI code.
- `game/player.py` → Server-side player state only.

### What gets replaced:
- Current `main.py` → New `client/main.py` (UI and WebSocket only)

### What gets deleted:
- `server/core/engine.py` - Merge useful parts into unified server
- `client/` (web client) - Removed entirely

### New code needed:
- `server/main.py` - WebSocket server, message handling
- `server/protocol.py` - Message definitions
- `client/main.py` - Terminal UI, input handling, WebSocket client
- `client/lan.py` - LAN discovery (UDP broadcast)

## Implementation Phases

### Phase 1: Unified Server
- Extract game logic from `game/engine.py` into `server/engine.py`
- Remove all UI code from server
- Add WebSocket message handling
- Server can run a complete game via messages alone

### Phase 2: Terminal Client
- New `client/main.py` with `rich` UI
- WebSocket connection to server
- Main menu (single/local/host/join)
- Game rendering and input collection

### Phase 3: Local Play
- Client spawns server subprocess
- Single-player works end-to-end
- Hot-seat local multiplayer (multiple local players)

### Phase 4: Online Play
- LAN discovery (UDP broadcast/listen)
- Direct IP connection option
- Host/join flow working
- Multiple clients, one game

### Phase 5: Polish
- Reconnection handling
- Error handling and edge cases
- Testing across machines

Each phase produces a working (if limited) game.
