/**
 * Main application controller for LOOT RUN
 */

const App = {
    state: {
        user: null,
        currentLobby: null,
        isHost: false,
    },

    /**
     * Initialize the application
     */
    async init() {
        // Initialize game module
        Game.init();

        // Set up event listeners
        this.setupAuthListeners();
        this.setupLobbyListeners();
        this.setupGameListeners();

        // Check for existing session
        if (API.loadToken()) {
            try {
                const user = await API.getMe();
                this.state.user = user;
                this.showScreen('lobby-screen');
                document.getElementById('player-name').textContent = user.username;
            } catch (error) {
                // Token invalid
                API.clearToken();
            }
        }
    },

    /**
     * Show a screen
     */
    showScreen(screenId) {
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        document.getElementById(screenId).classList.add('active');
    },

    /**
     * Set up auth screen event listeners
     */
    setupAuthListeners() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;

                // Update active tab
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Show correct form
                document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
                document.getElementById(`${tab}-form`).classList.add('active');
            });
        });

        // Login form
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value;
            const password = document.getElementById('login-password').value;

            try {
                await API.login(username, password);
                const user = await API.getMe();
                this.state.user = user;
                document.getElementById('player-name').textContent = user.username;
                this.showScreen('lobby-screen');
                this.clearError('auth-error');
            } catch (error) {
                this.showError('auth-error', error.message);
            }
        });

        // Register form
        document.getElementById('register-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('register-email').value;
            const username = document.getElementById('register-username').value;
            const password = document.getElementById('register-password').value;

            try {
                await API.register(email, username, password);
                await API.login(username, password);
                const user = await API.getMe();
                this.state.user = user;
                document.getElementById('player-name').textContent = user.username;
                this.showScreen('lobby-screen');
                this.clearError('auth-error');
            } catch (error) {
                this.showError('auth-error', error.message);
            }
        });

        // Logout
        document.getElementById('logout-btn').addEventListener('click', () => {
            API.clearToken();
            gameSocket.disconnect();
            this.state.user = null;
            this.state.currentLobby = null;
            this.showScreen('auth-screen');
        });
    },

    /**
     * Set up lobby screen event listeners
     */
    setupLobbyListeners() {
        // Create lobby
        document.getElementById('create-lobby-btn').addEventListener('click', async () => {
            try {
                const lobby = await API.createLobby();
                this.state.currentLobby = lobby;
                this.state.isHost = true;
                this.enterWaitingRoom(lobby);
            } catch (error) {
                this.showError('lobby-error', error.message);
            }
        });

        // Join lobby
        document.getElementById('join-lobby-btn').addEventListener('click', async () => {
            const code = document.getElementById('join-code').value.toUpperCase();
            if (code.length !== 6) {
                this.showError('lobby-error', 'Lobby code must be 6 characters');
                return;
            }

            try {
                const lobby = await API.joinLobby(code);
                this.state.currentLobby = lobby;
                this.state.isHost = lobby.host_user_id === this.state.user.id;
                this.enterWaitingRoom(lobby);
            } catch (error) {
                this.showError('lobby-error', error.message);
            }
        });

        // Copy lobby code
        document.getElementById('copy-code-btn').addEventListener('click', () => {
            const code = document.getElementById('lobby-code-display').textContent;
            navigator.clipboard.writeText(code);
            document.getElementById('copy-code-btn').textContent = 'Copied!';
            setTimeout(() => {
                document.getElementById('copy-code-btn').textContent = 'Copy';
            }, 2000);
        });

        // Ready button
        document.getElementById('ready-btn').addEventListener('click', () => {
            gameSocket.setReady(true);
        });

        // Start game (host only)
        document.getElementById('start-game-btn').addEventListener('click', () => {
            gameSocket.startGame();
        });

        // Leave lobby
        document.getElementById('leave-lobby-btn').addEventListener('click', async () => {
            try {
                if (this.state.currentLobby) {
                    await API.leaveLobby(this.state.currentLobby.code);
                }
                gameSocket.disconnect();
                this.state.currentLobby = null;
                this.showScreen('lobby-screen');
            } catch (error) {
                console.error('Failed to leave lobby:', error);
                this.showScreen('lobby-screen');
            }
        });

        // WebSocket lobby handlers
        gameSocket.on('LOBBY_UPDATE', (data) => this.onLobbyUpdate(data));
        gameSocket.on('PLAYER_JOINED', (data) => this.onPlayerJoined(data));
        gameSocket.on('PLAYER_LEFT', (data) => this.onPlayerLeft(data));
    },

    /**
     * Set up game screen event listeners
     */
    setupGameListeners() {
        // Continue button in result modal
        document.getElementById('continue-btn').addEventListener('click', () => {
            Game.hideModal('result-modal');
        });

        // Back to lobby button
        document.getElementById('back-to-lobby-btn').addEventListener('click', () => {
            Game.hideModal('gameover-modal');
            this.showScreen('lobby-screen');
            this.state.currentLobby = null;
        });
    },

    /**
     * Enter waiting room
     */
    enterWaitingRoom(lobby) {
        document.getElementById('lobby-code-display').textContent = lobby.code;

        // Connect WebSocket
        gameSocket.connect(API.token);

        // Once connected, join the lobby
        gameSocket.on('connected', () => {
            gameSocket.joinLobby(lobby.code);
        });

        this.updatePlayerList(lobby.players);
        this.updateStartButton();
        this.showScreen('waiting-room-screen');
    },

    /**
     * Handle lobby update
     */
    onLobbyUpdate(data) {
        this.updatePlayerList(data.players);
        this.updateStartButton();
    },

    /**
     * Handle player joined
     */
    onPlayerJoined(data) {
        console.log('Player joined:', data);
    },

    /**
     * Handle player left
     */
    onPlayerLeft(data) {
        console.log('Player left:', data);
    },

    /**
     * Update player list in waiting room
     */
    updatePlayerList(players) {
        const list = document.getElementById('player-list');
        let html = '';

        players.forEach(player => {
            const isHost = player.is_host ? 'host' : '';
            const status = player.is_ready ? 'ready' : 'waiting';
            const statusText = player.is_ready ? 'Ready' : 'Waiting';

            html += `
                <div class="player-item ${isHost}">
                    <span class="name">${player.username}</span>
                    <span class="status ${status}">${statusText}</span>
                </div>
            `;
        });

        list.innerHTML = html;
    },

    /**
     * Update start button state
     */
    updateStartButton() {
        const startBtn = document.getElementById('start-game-btn');

        if (!this.state.isHost) {
            startBtn.style.display = 'none';
            return;
        }

        startBtn.style.display = 'inline-block';

        // Check if all players are ready and at least 2 players
        const lobby = this.state.currentLobby;
        if (!lobby) return;

        const playerList = document.querySelectorAll('#player-list .player-item');
        const allReady = Array.from(playerList).every(item =>
            item.querySelector('.status').classList.contains('ready')
        );

        startBtn.disabled = !allReady || playerList.length < 2;
    },

    /**
     * Show error message
     */
    showError(elementId, message) {
        const element = document.getElementById(elementId);
        element.textContent = message;
        element.classList.add('animate-shake');
        setTimeout(() => element.classList.remove('animate-shake'), 500);
    },

    /**
     * Clear error message
     */
    clearError(elementId) {
        document.getElementById(elementId).textContent = '';
    },
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
