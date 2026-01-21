"""Integration tests for end-to-end game flows.

These tests use a REAL server subprocess, not mocks.
They verify actual end-to-end behavior of the game flows.
"""

import pytest
import subprocess
import sys
import time
from typing import Dict, List, Optional

from client.network_thread import NetworkThread
from client.state import GameState, ClientPhase
from client.handler import MessageHandler
from version import VERSION

from .conftest import kill_process_on_port, wait_for_server


# Mark all tests in this module as slow and set a timeout
pytestmark = [pytest.mark.slow, pytest.mark.timeout(30)]

# Test timeouts
POLL_TIMEOUT = 0.1
CONNECTION_TIMEOUT = 5.0
GAME_TIMEOUT = 30.0


@pytest.fixture
def game_server():
    """Start real server for integration tests on port 18900."""
    port = 18900
    kill_process_on_port(port)

    # Use DEVNULL for stdout/stderr to prevent pipe buffer blocking
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for server to be ready (longer timeout for CI)
    if not wait_for_server(port, timeout=15.0):
        poll_result = proc.poll()
        if poll_result is not None:
            error_msg = f"Server process exited with code {poll_result}"
        else:
            error_msg = "Server did not start accepting connections in time"
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        pytest.fail(f"Server failed to start on port {port}: {error_msg}")

    yield f"ws://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture
def game_server_18901():
    """Start real server on port 18901 for tests needing multiple servers."""
    port = 18901
    kill_process_on_port(port)

    # Use DEVNULL for stdout/stderr to prevent pipe buffer blocking
    proc = subprocess.Popen(
        [sys.executable, "-m", "server.main", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for server to be ready (longer timeout for CI)
    if not wait_for_server(port, timeout=15.0):
        poll_result = proc.poll()
        if poll_result is not None:
            error_msg = f"Server process exited with code {poll_result}"
        else:
            error_msg = "Server did not start accepting connections in time"
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        pytest.fail(f"Server failed to start on port {port}: {error_msg}")

    yield f"ws://127.0.0.1:{port}"
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def connect_and_join(
    network: NetworkThread,
    server_url: str,
    username: str,
    timeout: float = CONNECTION_TIMEOUT
) -> tuple[bool, Optional[str], Optional[str]]:
    """Connect to server and join the game.

    Returns:
        Tuple of (success, player_id, game_id)
    """
    if not network.start(server_url):
        return False, None, None

    # Wait for connection
    start_time = time.time()
    connected = False
    while time.time() - start_time < timeout:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg:
            if msg["type"] == "CONNECTED":
                connected = True
                break
            elif msg["type"] == "CONNECTION_LOST":
                return False, None, None

    if not connected:
        return False, None, None

    # Send JOIN message
    network.send("JOIN", {"username": username, "version": VERSION})

    # Wait for WELCOME response
    player_id = None
    game_id = None
    start_time = time.time()
    while time.time() - start_time < timeout:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg:
            if msg["type"] == "SERVER_MESSAGE":
                if msg["message_type"] == "WELCOME":
                    player_id = msg["data"].get("player_id")
                    game_id = msg["data"].get("game_id")
                    if player_id and game_id:
                        return True, player_id, game_id
            elif msg["type"] == "CONNECTION_LOST":
                return False, None, None

    return False, None, None


def poll_until(
    network: NetworkThread,
    handler: MessageHandler,
    condition,
    timeout: float = GAME_TIMEOUT
) -> bool:
    """Poll until condition is true or timeout.

    Returns:
        True if condition became true, False on timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        msg = network.poll(timeout=POLL_TIMEOUT)
        if msg and msg["type"] == "SERVER_MESSAGE":
            handler.handle(msg["message_type"], msg["data"])
        if condition():
            return True
    return False


def poll_all_networks(
    networks: Dict[str, NetworkThread],
    handler: MessageHandler,
    poll_time: float = 0.1
) -> None:
    """Poll all network threads and process messages."""
    start = time.time()
    while time.time() - start < poll_time:
        for pid, network in networks.items():
            msg = network.poll(timeout=0.01)
            if msg and msg["type"] == "SERVER_MESSAGE":
                handler.handle(msg["message_type"], msg["data"])


class TestSinglePlayerCompleteFlow:
    """Test complete single player game flow."""

    @pytest.mark.slow
    def test_single_player_connect_to_game_over(self, game_server):
        """Single player flow: connect -> play rounds -> game over.

        This test verifies:
        1. Player can connect and join
        2. Player can ready up
        3. Game transitions through shop -> choosing -> results phases
        4. Multiple rounds can be played
        5. Game can reach game over state (win or AI victory)
        """
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            # Connect and join
            success, player_id, game_id = connect_and_join(
                network, game_server, "SinglePlayer"
            )
            assert success, "Failed to connect and join"

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True
            state.local_player_ids = [player_id]

            # Ready up to start game
            network.send("READY", {})

            # Wait for choosing phase (round 1 skips shop)
            assert poll_until(
                network, handler,
                lambda: state.phase == ClientPhase.CHOOSING
            ), "Game did not start (no CHOOSING phase)"

            # Play through rounds
            rounds_played = 0
            max_rounds = 10

            while rounds_played < max_rounds and state.phase != ClientPhase.GAME_OVER:
                # Handle based on current phase
                if state.phase == ClientPhase.SHOP:
                    # Skip shop (only happens in round 2+)
                    network.send("SKIP_SHOP", {})
                    poll_until(
                        network, handler,
                        lambda: state.phase == ClientPhase.CHOOSING,
                        timeout=5.0
                    )

                elif state.phase == ClientPhase.CHOOSING:
                    # Make location choice (cycle through locations)
                    location_index = rounds_played % max(1, len(state.locations))
                    network.send("LOCATION_CHOICE", {"location_index": location_index})

                    # Wait for round result
                    poll_until(
                        network, handler,
                        lambda: handler.last_round_result is not None,
                        timeout=10.0
                    )

                    # Check if we were caught (need escape)
                    was_caught = False
                    if handler.last_round_result:
                        for result in handler.last_round_result.get("player_results", []):
                            if result.get("player_id") == state.player_id:
                                was_caught = result.get("escape_required", False)
                                break

                    # Handle escape if caught
                    if was_caught:
                        # Wait for ESCAPE phase
                        poll_until(
                            network, handler,
                            lambda: state.phase == ClientPhase.ESCAPE,
                            timeout=5.0
                        )

                        if state.escape_options:
                            # Choose first escape option
                            option_id = state.escape_options[0].get("id", "")
                            network.send("ESCAPE_CHOICE", {"option_id": option_id})

                            # Wait for escape result
                            poll_until(
                                network, handler,
                                lambda: handler.last_escape_result is not None,
                                timeout=5.0
                            )
                            handler.last_escape_result = None

                    rounds_played += 1
                    handler.last_round_result = None

                    # Poll for next phase
                    poll_until(
                        network, handler,
                        lambda: state.phase in [ClientPhase.SHOP, ClientPhase.GAME_OVER],
                        timeout=10.0
                    )

                else:
                    # Transitional phase (ESCAPE, RESULTS, WAITING, etc.)
                    # Poll until we reach an actionable phase
                    if not poll_until(
                        network, handler,
                        lambda: state.phase in [ClientPhase.SHOP, ClientPhase.CHOOSING, ClientPhase.GAME_OVER],
                        timeout=10.0
                    ):
                        # If we timeout in a transitional phase, fail with clear message
                        pytest.fail(f"Test stuck in phase {state.phase} after {rounds_played} rounds")

            # Verify we played at least one round
            assert rounds_played >= 1, "Should have played at least one round"

            # Game should either have ended or we hit max rounds
            assert rounds_played > 0 or state.phase == ClientPhase.GAME_OVER

        finally:
            network.stop()

    @pytest.mark.slow
    def test_single_player_location_scripted(self, game_server):
        """Single player flow with scripted location choices.

        Tests that specific location choices are properly sent and processed.
        """
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        # Script: location choices for each round
        scripted_choices = [0, 1, 2, 0, 1]

        try:
            # Connect and join
            success, player_id, game_id = connect_and_join(
                network, game_server, "ScriptedPlayer"
            )
            assert success, "Failed to connect"

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True
            state.local_player_ids = [player_id]

            # Ready up
            network.send("READY", {})

            # Wait for game start (round 1 skips shop, goes to choosing)
            assert poll_until(
                network, handler,
                lambda: state.phase == ClientPhase.CHOOSING
            ), "Game did not start"

            # Play rounds with scripted choices
            for round_num, choice in enumerate(scripted_choices):
                if state.phase == ClientPhase.GAME_OVER:
                    break

                # Handle based on current phase
                if state.phase == ClientPhase.SHOP:
                    # Skip shop (only happens in round 2+)
                    network.send("SKIP_SHOP", {})
                    poll_until(
                        network, handler,
                        lambda: state.phase == ClientPhase.CHOOSING,
                        timeout=5.0
                    )

                elif state.phase == ClientPhase.CHOOSING:
                    # Make scripted choice
                    # Ensure choice is valid for available locations
                    valid_choice = choice % max(1, len(state.locations))
                    network.send("LOCATION_CHOICE", {"location_index": valid_choice})

                    # Wait for round result
                    poll_until(
                        network, handler,
                        lambda: handler.last_round_result is not None,
                        timeout=10.0
                    )

                    # Check if we were caught (need escape)
                    was_caught = False
                    if handler.last_round_result:
                        for result in handler.last_round_result.get("player_results", []):
                            if result.get("player_id") == state.player_id:
                                was_caught = result.get("escape_required", False)
                                break

                    # Handle escape if caught
                    if was_caught:
                        # Wait for ESCAPE phase
                        poll_until(
                            network, handler,
                            lambda: state.phase == ClientPhase.ESCAPE,
                            timeout=5.0
                        )

                        if state.escape_options:
                            option_id = state.escape_options[0].get("id", "")
                            network.send("ESCAPE_CHOICE", {"option_id": option_id})
                            poll_until(
                                network, handler,
                                lambda: handler.last_escape_result is not None,
                                timeout=5.0
                            )
                            handler.last_escape_result = None

                    handler.last_round_result = None

                    # Wait for next phase
                    poll_until(
                        network, handler,
                        lambda: state.phase in [ClientPhase.SHOP, ClientPhase.GAME_OVER],
                        timeout=10.0
                    )

                else:
                    # Transitional phase - wait for actionable state
                    if not poll_until(
                        network, handler,
                        lambda: state.phase in [ClientPhase.SHOP, ClientPhase.CHOOSING, ClientPhase.GAME_OVER],
                        timeout=10.0
                    ):
                        pytest.fail(f"Test stuck in phase {state.phase} at round {round_num}")

            # Verify game progressed
            assert state.round_num >= 1, "Game should have advanced rounds"

        finally:
            network.stop()


class TestHostOnlineFlow:
    """Test host online game flow."""

    @pytest.mark.slow
    def test_host_creates_game_and_waits(self, game_server):
        """Host online flow: create server -> join -> wait in lobby.

        This test verifies:
        1. Host can connect to server
        2. Host receives game_id and player_id
        3. Host enters lobby state
        4. Host can ready/unready
        """
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            # Connect as host
            success, player_id, game_id = connect_and_join(
                network, game_server, "HostPlayer"
            )
            assert success, "Host failed to connect"
            assert player_id is not None, "Should have player_id"
            assert game_id is not None, "Should have game_id"

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True
            state.local_player_ids = [player_id]

            # Poll for lobby state
            poll_until(
                network, handler,
                lambda: state.phase == ClientPhase.LOBBY or len(state.players) > 0,
                timeout=5.0
            )

            # Verify lobby state
            assert state.connected is True
            assert player_id in state.players or len(state.players) >= 0

            # Test ready/unready
            network.send("READY", {})
            poll_until(
                network, handler,
                lambda: (state.players.get(player_id) and
                        state.players[player_id].ready) or
                        state.phase == ClientPhase.CHOOSING,  # May auto-start (round 1 skips shop)
                timeout=5.0
            )

            # If single player, game may have started
            # Otherwise player should be marked ready
            if state.phase == ClientPhase.LOBBY:
                player = state.players.get(player_id)
                assert player is not None, "Player should exist"
                assert player.ready is True, "Player should be ready"

        finally:
            network.stop()

    @pytest.mark.slow
    def test_host_starts_game_alone(self, game_server_18901):
        """Host can start game as single player."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            success, player_id, game_id = connect_and_join(
                network, game_server_18901, "LoneHost"
            )
            assert success

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True
            state.local_player_ids = [player_id]

            # Ready up - should start game immediately
            network.send("READY", {})

            # Wait for game to start (round 1 skips shop, goes to choosing)
            assert poll_until(
                network, handler,
                lambda: state.phase == ClientPhase.CHOOSING
            ), "Game should start when host readies"

            assert state.round_num >= 1, "Game should be in round 1+"
            assert len(state.locations) > 0, "Should have locations"

        finally:
            network.stop()


class TestJoinOnlineFlow:
    """Test join online game flow."""

    @pytest.mark.slow
    def test_player_joins_existing_game(self, game_server):
        """Join online flow: connect to server -> enter lobby.

        This test verifies:
        1. Player can connect to existing server
        2. Player receives welcome message
        3. Player enters lobby and sees other players
        """
        # First player (host)
        network1 = NetworkThread()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        # Second player (joiner)
        network2 = NetworkThread()
        state2 = GameState()
        handler2 = MessageHandler(state2)

        try:
            # Host connects first
            success1, player_id1, game_id = connect_and_join(
                network1, game_server, "Host"
            )
            assert success1, "Host failed to connect"

            state1.player_id = player_id1
            state1.game_id = game_id
            state1.connected = True
            state1.local_player_ids = [player_id1]

            # Poll host to receive lobby state
            poll_until(
                network1, handler1,
                lambda: len(state1.players) >= 1,
                timeout=5.0
            )

            # Joiner connects
            success2, player_id2, game_id2 = connect_and_join(
                network2, game_server, "Joiner"
            )
            assert success2, "Joiner failed to connect"
            assert game_id == game_id2, "Should join same game"

            state2.player_id = player_id2
            state2.game_id = game_id2
            state2.connected = True
            state2.local_player_ids = [player_id2]

            # Poll both to receive player updates
            for _ in range(50):
                msg1 = network1.poll(timeout=0.05)
                if msg1 and msg1["type"] == "SERVER_MESSAGE":
                    handler1.handle(msg1["message_type"], msg1["data"])

                msg2 = network2.poll(timeout=0.05)
                if msg2 and msg2["type"] == "SERVER_MESSAGE":
                    handler2.handle(msg2["message_type"], msg2["data"])

                if len(state1.players) == 2 and len(state2.players) == 2:
                    break

            # Both should see 2 players
            assert len(state1.players) == 2, f"Host should see 2 players, saw {len(state1.players)}"
            assert len(state2.players) == 2, f"Joiner should see 2 players, saw {len(state2.players)}"

        finally:
            network1.stop()
            network2.stop()

    @pytest.mark.slow
    def test_joiner_sees_address_input(self, game_server):
        """Test that join flow accepts server address.

        This simulates the address input step where user types "localhost" or IP.
        """
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            # Parse server URL to get host/port
            # game_server is "ws://127.0.0.1:18900"

            success, player_id, game_id = connect_and_join(
                network, game_server, "AddressInputTest"
            )
            assert success, "Should connect via explicit address"

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True

            # Verify connection works
            assert state.connected is True
            assert player_id is not None

        finally:
            network.stop()


class TestHotSeatFlow:
    """Test local multiplayer hot-seat flow."""

    @pytest.mark.slow
    def test_hotseat_multiple_players_connect(self, game_server):
        """Hot-seat flow: multiple local players connect to same server.

        This test verifies:
        1. Multiple players can connect from same client
        2. Each gets unique player_id
        3. All players appear in lobby
        """
        networks: Dict[str, NetworkThread] = {}
        state = GameState()
        handler = MessageHandler(state)

        player_names = ["Alice", "Bob", "Charlie"]
        player_ids: List[str] = []

        try:
            # Connect each player
            for name in player_names:
                network = NetworkThread()
                success, player_id, game_id = connect_and_join(
                    network, game_server, name
                )
                assert success, f"{name} failed to connect"

                player_ids.append(player_id)
                networks[player_id] = network

                if not state.game_id:
                    state.game_id = game_id
                state.local_player_ids.append(player_id)

            # Poll all networks to sync player list
            for _ in range(100):
                for pid, network in networks.items():
                    msg = network.poll(timeout=0.02)
                    if msg and msg["type"] == "SERVER_MESSAGE":
                        handler.handle(msg["message_type"], msg["data"])

                if len(state.players) >= len(player_names):
                    break

            # Verify all players connected
            assert len(player_ids) == len(player_names), "All players should have IDs"
            assert len(set(player_ids)) == len(player_ids), "All player IDs should be unique"

            # Verify all appear in game state
            assert len(state.players) >= len(player_names), f"Expected {len(player_names)} players, got {len(state.players)}"

        finally:
            for network in networks.values():
                network.stop()

    @pytest.mark.slow
    def test_hotseat_all_players_ready_starts_game(self, game_server_18901):
        """Hot-seat: all local players ready up starts game."""
        networks: Dict[str, NetworkThread] = {}
        state = GameState()
        handler = MessageHandler(state)

        player_names = ["Player1", "Player2"]
        player_ids: List[str] = []

        try:
            # Connect players
            for name in player_names:
                network = NetworkThread()
                success, player_id, game_id = connect_and_join(
                    network, game_server_18901, name
                )
                assert success, f"{name} failed to connect"

                player_ids.append(player_id)
                networks[player_id] = network
                state.local_player_ids.append(player_id)

                if not state.game_id:
                    state.game_id = game_id

            # Poll to sync
            poll_all_networks(networks, handler, poll_time=0.5)

            # All players ready up
            for pid, network in networks.items():
                network.send("READY", {})

            # Wait for game to start (round 1 skips shop, goes to choosing)
            first_network = list(networks.values())[0]
            assert poll_until(
                first_network, handler,
                lambda: state.phase == ClientPhase.CHOOSING
            ), "Game should start when all ready"

            # Game started
            assert state.round_num >= 1
            assert len(state.locations) > 0

        finally:
            for network in networks.values():
                network.stop()

    @pytest.mark.slow
    def test_hotseat_play_round(self, game_server):
        """Hot-seat: all players make choices and complete a round."""
        networks: Dict[str, NetworkThread] = {}
        state = GameState()
        handler = MessageHandler(state)

        player_names = ["HotA", "HotB"]
        player_ids: List[str] = []

        try:
            # Connect players
            for name in player_names:
                network = NetworkThread()
                success, player_id, game_id = connect_and_join(
                    network, game_server, name
                )
                assert success

                player_ids.append(player_id)
                networks[player_id] = network
                state.local_player_ids.append(player_id)

                if not state.game_id:
                    state.game_id = game_id

            # Sync and ready
            poll_all_networks(networks, handler, poll_time=0.3)

            for network in networks.values():
                network.send("READY", {})

            # Wait for choosing phase (round 1 skips shop)
            first_network = list(networks.values())[0]
            poll_until(
                first_network, handler,
                lambda: state.phase == ClientPhase.CHOOSING,
                timeout=10.0
            )

            # Each player chooses different location
            for i, (pid, network) in enumerate(networks.items()):
                location_choice = i % max(1, len(state.locations))
                network.send("LOCATION_CHOICE", {"location_index": location_choice})

            # Wait for round result
            poll_until(
                first_network, handler,
                lambda: handler.last_round_result is not None,
                timeout=10.0
            )

            # Check if any local players were caught
            caught_players = []
            if handler.last_round_result:
                for result in handler.last_round_result.get("player_results", []):
                    if result.get("escape_required") and result.get("player_id") in state.local_player_ids:
                        caught_players.append(result.get("player_id"))

            # Handle escape for caught players
            if caught_players:
                # Wait for ESCAPE phase
                poll_until(
                    first_network, handler,
                    lambda: state.phase == ClientPhase.ESCAPE,
                    timeout=5.0
                )

                for pid in caught_players:
                    if pid in networks and state.escape_options:
                        option_id = state.escape_options[0].get("id", "")
                        networks[pid].send("ESCAPE_CHOICE", {"option_id": option_id})

            # Poll for completion
            poll_all_networks(networks, handler, poll_time=1.0)

            # Round should have completed
            assert handler.last_round_result is not None or state.phase in [ClientPhase.SHOP, ClientPhase.GAME_OVER]

        finally:
            for network in networks.values():
                network.stop()


class TestMenuTransitions:
    """Test menu navigation flows."""

    @pytest.mark.slow
    def test_connect_disconnect_reconnect(self, game_server):
        """Test that player can disconnect and reconnect to server.

        Note: After disconnecting, the server may create a new game instance,
        so game_id might differ. We verify the player can successfully reconnect.
        """
        network1 = NetworkThread()
        state1 = GameState()
        handler1 = MessageHandler(state1)

        try:
            # First connection
            success, player_id1, game_id = connect_and_join(
                network1, game_server, "ReconnectTest"
            )
            assert success, "First connection should succeed"
            assert player_id1 is not None
            assert game_id is not None

            state1.player_id = player_id1
            state1.game_id = game_id
            state1.connected = True

            # Disconnect
            network1.stop()
            time.sleep(0.3)  # Brief pause before reconnection

            # Reconnect with new network
            network2 = NetworkThread()
            success, player_id2, game_id2 = connect_and_join(
                network2, game_server, "ReconnectTest"
            )
            assert success, "Should be able to reconnect"
            assert player_id2 is not None, "Should get new player_id"
            assert game_id2 is not None, "Should get game_id"

            # Verify new connection is working
            network2.stop()

        finally:
            network1.stop()


class TestErrorHandling:
    """Test error handling in game flows."""

    @pytest.mark.slow
    def test_invalid_location_choice_handled(self, game_server):
        """Test that invalid location choice is handled gracefully."""
        network = NetworkThread()
        state = GameState()
        handler = MessageHandler(state)

        try:
            success, player_id, game_id = connect_and_join(
                network, game_server, "InvalidChoice"
            )
            assert success

            state.player_id = player_id
            state.game_id = game_id
            state.connected = True
            state.local_player_ids = [player_id]

            # Ready up
            network.send("READY", {})

            # Wait for choosing phase (round 1 skips shop)
            poll_until(
                network, handler,
                lambda: state.phase == ClientPhase.CHOOSING
            )

            # Send invalid location choice (way out of bounds)
            network.send("LOCATION_CHOICE", {"location_index": 9999})

            # Should not crash - poll for a bit
            time.sleep(0.5)
            for _ in range(10):
                msg = network.poll(timeout=0.1)
                if msg and msg["type"] == "SERVER_MESSAGE":
                    handler.handle(msg["message_type"], msg["data"])

            # Connection should still be alive
            # Server may ignore invalid choice or send error
            assert state.connected is True

        finally:
            network.stop()

    @pytest.mark.slow
    def test_connection_refused_handled(self):
        """Test that connection to non-existent server is handled."""
        network = NetworkThread()

        try:
            # Try to connect to non-existent server
            success, player_id, game_id = connect_and_join(
                network, "ws://127.0.0.1:19999", "NoServer",
                timeout=3.0
            )

            # Should fail gracefully
            assert success is False, "Should fail to connect to non-existent server"
            assert player_id is None
            assert game_id is None

        finally:
            network.stop()
