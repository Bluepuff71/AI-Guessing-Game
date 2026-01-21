"""Tests for client/network_thread.py module - NetworkThread functionality."""

import queue
import threading
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from client.network_thread import NetworkThread, WEBSOCKETS_AVAILABLE
from server.protocol import Message


class TestNetworkThreadInitialization:
    """Tests for NetworkThread initialization."""

    def test_init_creates_queues(self):
        """Test that initialization creates incoming and outgoing queues."""
        thread = NetworkThread()

        assert isinstance(thread.incoming_queue, queue.Queue)
        assert isinstance(thread.outgoing_queue, queue.Queue)

    def test_init_thread_not_running(self):
        """Test that thread is not running after initialization."""
        thread = NetworkThread()

        assert thread.is_running is False
        assert thread._thread is None

    def test_init_no_event_loop(self):
        """Test that no event loop exists after initialization."""
        thread = NetworkThread()

        assert thread._loop is None


class TestNetworkThreadStart:
    """Tests for NetworkThread.start() method."""

    def test_start_sets_running_flag(self):
        """Test that start() clears the stop event (meaning running)."""
        thread = NetworkThread()

        # Mock the thread to prevent actual connection
        with patch.object(threading.Thread, 'start'):
            result = thread.start("ws://localhost:8765")

        assert result is True
        assert thread._stop_event.is_set() is False  # Not stopped = running

    def test_start_creates_daemon_thread(self):
        """Test that start() creates a daemon thread."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            thread.start("ws://localhost:8765")

        assert thread._thread is not None
        assert thread._thread.daemon is True
        assert thread._thread.name == "NetworkThread"

    def test_start_stores_url(self):
        """Test that start() stores the URL."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            thread.start("ws://example.com:9999")

        assert thread._url == "ws://example.com:9999"

    def test_start_returns_false_if_already_running(self):
        """Test that start() returns False if thread is already running."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            with patch.object(threading.Thread, 'is_alive', return_value=True):
                thread.start("ws://localhost:8765")
                result = thread.start("ws://localhost:8766")

        assert result is False

    @pytest.mark.skipif(WEBSOCKETS_AVAILABLE, reason="Only runs when websockets unavailable")
    def test_start_fails_without_websockets(self):
        """Test that start() fails gracefully without websockets library."""
        thread = NetworkThread()

        with patch('client.network_thread.WEBSOCKETS_AVAILABLE', False):
            result = thread.start("ws://localhost:8765")

        assert result is False


class TestNetworkThreadStop:
    """Tests for NetworkThread.stop() method."""

    def test_stop_sets_stop_event(self):
        """Test that stop() sets the stop event."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            with patch.object(threading.Thread, 'is_alive', return_value=True):
                thread.start("ws://localhost:8765")
                # Mock join to prevent blocking, keep is_alive True so stop() proceeds
                with patch.object(threading.Thread, 'join'):
                    thread.stop()

        assert thread._stop_event.is_set() is True

    def test_stop_queues_disconnect_message(self):
        """Test that stop() queues a DISCONNECT message."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            with patch.object(threading.Thread, 'is_alive', return_value=True):
                thread.start("ws://localhost:8765")
                with patch.object(threading.Thread, 'join'):
                    thread.stop()

        # Check that disconnect was queued
        msg = thread.outgoing_queue.get_nowait()
        assert msg["type"] == "DISCONNECT"

    def test_stop_when_not_running_is_safe(self):
        """Test that stop() is safe to call when not running."""
        thread = NetworkThread()

        # Should not raise
        thread.stop()

        assert thread._stop_event.is_set() is False  # Still not set since we never started


class TestNetworkThreadSend:
    """Tests for NetworkThread.send() method."""

    def test_send_queues_message(self):
        """Test that send() puts a message in the outgoing queue."""
        thread = NetworkThread()

        thread.send("LOCATION_CHOICE", {"location_index": 2})

        msg = thread.outgoing_queue.get_nowait()
        assert msg["type"] == "SEND"
        assert msg["message_type"] == "LOCATION_CHOICE"
        assert msg["data"] == {"location_index": 2}

    def test_send_multiple_messages(self):
        """Test that multiple send() calls queue multiple messages."""
        thread = NetworkThread()

        thread.send("READY", {})
        thread.send("LOCATION_CHOICE", {"location_index": 0})
        thread.send("SKIP_SHOP", {})

        msg1 = thread.outgoing_queue.get_nowait()
        msg2 = thread.outgoing_queue.get_nowait()
        msg3 = thread.outgoing_queue.get_nowait()

        assert msg1["message_type"] == "READY"
        assert msg2["message_type"] == "LOCATION_CHOICE"
        assert msg3["message_type"] == "SKIP_SHOP"


class TestNetworkThreadPoll:
    """Tests for NetworkThread.poll() method."""

    def test_poll_returns_message_when_available(self):
        """Test that poll() returns a message when one is available."""
        thread = NetworkThread()

        # Put a message in the incoming queue
        thread.incoming_queue.put({"type": "CONNECTED"})

        result = thread.poll(timeout=0.1)

        assert result == {"type": "CONNECTED"}

    def test_poll_returns_none_on_timeout(self):
        """Test that poll() returns None when timeout elapses."""
        thread = NetworkThread()

        result = thread.poll(timeout=0.01)

        assert result is None

    def test_poll_returns_server_message(self):
        """Test that poll() returns server messages correctly."""
        thread = NetworkThread()

        thread.incoming_queue.put({
            "type": "SERVER_MESSAGE",
            "message_type": "GAME_STATE",
            "data": {"round_num": 1}
        })

        result = thread.poll()

        assert result["type"] == "SERVER_MESSAGE"
        assert result["message_type"] == "GAME_STATE"
        assert result["data"]["round_num"] == 1


class TestNetworkThreadQueueFormats:
    """Tests for queue message format compliance."""

    def test_outgoing_send_format(self):
        """Test that outgoing SEND messages have correct format."""
        thread = NetworkThread()

        thread.send("JOIN", {"username": "Player1", "version": "v1.0"})

        msg = thread.outgoing_queue.get_nowait()
        assert "type" in msg
        assert "message_type" in msg
        assert "data" in msg
        assert msg["type"] == "SEND"

    def test_incoming_connected_format(self):
        """Test CONNECTED message format."""
        thread = NetworkThread()

        # Simulate what the thread would put in the queue
        connected_msg = {"type": "CONNECTED"}
        thread.incoming_queue.put(connected_msg)

        result = thread.poll()
        assert result["type"] == "CONNECTED"

    def test_incoming_server_message_format(self):
        """Test SERVER_MESSAGE format."""
        thread = NetworkThread()

        server_msg = {
            "type": "SERVER_MESSAGE",
            "message_type": "LOBBY_STATE",
            "data": {"players": []}
        }
        thread.incoming_queue.put(server_msg)

        result = thread.poll()
        assert result["type"] == "SERVER_MESSAGE"
        assert "message_type" in result
        assert "data" in result

    def test_incoming_connection_lost_format(self):
        """Test CONNECTION_LOST message format."""
        thread = NetworkThread()

        lost_msg = {
            "type": "CONNECTION_LOST",
            "error": "Connection refused"
        }
        thread.incoming_queue.put(lost_msg)

        result = thread.poll()
        assert result["type"] == "CONNECTION_LOST"
        assert "error" in result


class TestNetworkThreadIntegration:
    """Integration tests for NetworkThread with actual asyncio."""

    @pytest.mark.asyncio
    async def test_receive_loop_parses_messages(self):
        """Test that _receive_loop correctly parses server messages."""
        thread = NetworkThread()
        # _stop_event is not set by default, so the loop will run

        # Create a mock websocket that yields one message then closes
        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: self
        messages = [Message(type="WELCOME", data={"player_id": "123"}).to_json()]
        mock_ws.__anext__ = AsyncMock(side_effect=messages + [StopAsyncIteration])

        # Run the receive loop with the mock
        with patch('client.network_thread.ConnectionClosed', Exception):
            try:
                await thread._receive_loop(mock_ws)
            except StopAsyncIteration:
                pass

        # Check that the message was put in the queue
        msg = thread.incoming_queue.get_nowait()
        assert msg["type"] == "SERVER_MESSAGE"
        assert msg["message_type"] == "WELCOME"
        assert msg["data"]["player_id"] == "123"

    @pytest.mark.asyncio
    async def test_send_loop_sends_messages(self):
        """Test that _send_loop sends queued messages."""
        thread = NetworkThread()
        # _stop_event is not set by default, so the loop will run

        # Queue a message to send, then a disconnect
        thread.outgoing_queue.put({
            "type": "SEND",
            "message_type": "READY",
            "data": {}
        })
        thread.outgoing_queue.put({"type": "DISCONNECT"})

        # Create mock websocket
        mock_ws = AsyncMock()
        sent_messages = []
        mock_ws.send = AsyncMock(side_effect=lambda m: sent_messages.append(m))

        # Run the send loop
        await thread._send_loop(mock_ws)

        # Check that message was sent
        assert len(sent_messages) == 1
        parsed = Message.from_json(sent_messages[0])
        assert parsed.type == "READY"


class TestNetworkThreadDaemonBehavior:
    """Tests for daemon thread behavior."""

    def test_thread_is_daemon(self):
        """Test that the thread is marked as daemon."""
        thread = NetworkThread()

        with patch.object(threading.Thread, 'start'):
            thread.start("ws://localhost:8765")

        assert thread._thread.daemon is True


class TestNetworkThreadConstants:
    """Tests for NetworkThread constants."""

    def test_queue_poll_interval_is_reasonable(self):
        """Test that queue poll interval is a reasonable value."""
        assert NetworkThread.QUEUE_POLL_INTERVAL > 0
        assert NetworkThread.QUEUE_POLL_INTERVAL <= 0.1

    def test_stop_timeout_is_reasonable(self):
        """Test that stop timeout is a reasonable value."""
        assert NetworkThread.STOP_TIMEOUT >= 1.0
        assert NetworkThread.STOP_TIMEOUT <= 30.0
