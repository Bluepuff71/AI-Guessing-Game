/**
 * WebSocket client for LOOT RUN real-time communication
 */

class GameSocket {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
        this.handlers = {};
        this.pingInterval = null;
    }

    /**
     * Connect to the game WebSocket
     */
    connect(token) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/game?token=${token}`;

        try {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.connected = true;
                this.reconnectAttempts = 0;
                this.startPing();
                this.emit('connected');
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                this.connected = false;
                this.stopPing();
                this.emit('disconnected', { code: event.code, reason: event.reason });
                this.attemptReconnect(token);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.emit('error', error);
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };
        } catch (error) {
            console.error('Failed to connect:', error);
            this.attemptReconnect(token);
        }
    }

    /**
     * Disconnect from the server
     */
    disconnect() {
        this.stopPing();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect(token) {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnect attempts reached');
            this.emit('reconnectFailed');
            return;
        }

        this.reconnectAttempts++;
        console.log(`Reconnecting (attempt ${this.reconnectAttempts})...`);

        setTimeout(() => {
            this.connect(token);
        }, this.reconnectDelay * this.reconnectAttempts);
    }

    /**
     * Send a message to the server
     */
    send(type, payload = {}) {
        if (!this.connected) {
            console.warn('Not connected, cannot send:', type);
            return false;
        }

        try {
            this.ws.send(JSON.stringify({ type, payload }));
            return true;
        } catch (error) {
            console.error('Failed to send message:', error);
            return false;
        }
    }

    /**
     * Handle incoming messages
     */
    handleMessage(message) {
        const { type, payload } = message;
        console.log('Received:', type, payload);

        // Call registered handlers
        if (this.handlers[type]) {
            this.handlers[type].forEach(handler => handler(payload));
        }

        // Also emit as event
        this.emit(type, payload);
    }

    /**
     * Register a message handler
     */
    on(type, handler) {
        if (!this.handlers[type]) {
            this.handlers[type] = [];
        }
        this.handlers[type].push(handler);
    }

    /**
     * Remove a message handler
     */
    off(type, handler) {
        if (this.handlers[type]) {
            this.handlers[type] = this.handlers[type].filter(h => h !== handler);
        }
    }

    /**
     * Emit an event to all handlers
     */
    emit(type, data = {}) {
        if (this.handlers[type]) {
            this.handlers[type].forEach(handler => handler(data));
        }
    }

    /**
     * Start ping to keep connection alive
     */
    startPing() {
        this.pingInterval = setInterval(() => {
            this.send('PING', { timestamp: Date.now() });
        }, 30000);
    }

    /**
     * Stop ping interval
     */
    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    // Convenience methods for common messages

    joinLobby(lobbyCode) {
        return this.send('JOIN_LOBBY', { lobby_code: lobbyCode });
    }

    setReady(ready) {
        return this.send('PLAYER_READY', { ready });
    }

    startGame() {
        return this.send('START_GAME', {});
    }

    submitLocationChoice(locationIndex) {
        return this.send('LOCATION_CHOICE', { location_index: locationIndex });
    }

    submitEscapeChoice(optionId) {
        return this.send('ESCAPE_CHOICE', { option_id: optionId });
    }

    sendChat(message) {
        return this.send('CHAT', { message });
    }
}

// Create global instance
const gameSocket = new GameSocket();
