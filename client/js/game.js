/**
 * Game logic and state management for LOOT RUN
 */

const Game = {
    // Current state
    state: {
        inGame: false,
        gameId: null,
        roundNum: 0,
        phase: 'waiting', // waiting, choosing, resolving, escape
        players: [],
        locations: [],
        selectedLocation: null,
        timer: null,
        timerValue: 0,
    },

    // DOM Elements
    elements: {
        roundNumber: null,
        timer: null,
        timerValue: null,
        phaseInfo: null,
        standingsList: null,
        locationGrid: null,
        lastAiSearch: null,
        gameMessages: null,
        escapeModal: null,
        escapeOptions: null,
        escapeTimerValue: null,
        resultModal: null,
        resultTitle: null,
        resultContent: null,
        gameoverModal: null,
        gameoverTitle: null,
        gameoverContent: null,
    },

    /**
     * Initialize game elements
     */
    init() {
        this.elements.roundNumber = document.getElementById('round-number');
        this.elements.timer = document.getElementById('timer');
        this.elements.timerValue = document.getElementById('timer-value');
        this.elements.phaseInfo = document.getElementById('phase-info');
        this.elements.standingsList = document.getElementById('standings-list');
        this.elements.locationGrid = document.getElementById('location-grid');
        this.elements.lastAiSearch = document.getElementById('last-ai-search');
        this.elements.gameMessages = document.getElementById('game-messages');
        this.elements.escapeModal = document.getElementById('escape-modal');
        this.elements.escapeOptions = document.getElementById('escape-options');
        this.elements.escapeTimerValue = document.getElementById('escape-timer-value');
        this.elements.resultModal = document.getElementById('result-modal');
        this.elements.resultTitle = document.getElementById('result-title');
        this.elements.resultContent = document.getElementById('result-content');
        this.elements.gameoverModal = document.getElementById('gameover-modal');
        this.elements.gameoverTitle = document.getElementById('gameover-title');
        this.elements.gameoverContent = document.getElementById('gameover-content');

        // Register WebSocket handlers
        this.registerHandlers();
    },

    /**
     * Register WebSocket message handlers
     */
    registerHandlers() {
        gameSocket.on('GAME_STARTED', (data) => this.onGameStarted(data));
        gameSocket.on('ROUND_START', (data) => this.onRoundStart(data));
        gameSocket.on('TIMER_SYNC', (data) => this.onTimerSync(data));
        gameSocket.on('PLAYER_SUBMITTED', (data) => this.onPlayerSubmitted(data));
        gameSocket.on('ALL_CHOICES_LOCKED', (data) => this.onChoicesLocked(data));
        gameSocket.on('AI_ANALYZING', (data) => this.onAiAnalyzing(data));
        gameSocket.on('ROUND_RESULT', (data) => this.onRoundResult(data));
        gameSocket.on('ESCAPE_PHASE', (data) => this.onEscapePhase(data));
        gameSocket.on('ESCAPE_RESULT', (data) => this.onEscapeResult(data));
        gameSocket.on('PLAYER_ELIMINATED', (data) => this.onPlayerEliminated(data));
        gameSocket.on('GAME_OVER', (data) => this.onGameOver(data));
    },

    /**
     * Handle game started
     */
    onGameStarted(data) {
        this.state.inGame = true;
        this.state.gameId = data.game_id;
        this.state.players = data.players;
        this.state.locations = data.locations;

        // Render locations
        this.renderLocations();

        // Show game screen
        App.showScreen('game-screen');

        this.addMessage('info', `Game started! ${data.players.length} players. AI: ${data.ai_status.ml_active ? 'ML Active' : 'Baseline'}`);
    },

    /**
     * Handle round start
     */
    onRoundStart(data) {
        this.state.roundNum = data.round_num;
        this.state.phase = 'choosing';
        this.state.selectedLocation = null;

        // Update UI
        this.elements.roundNumber.textContent = data.round_num;
        this.elements.phaseInfo.textContent = 'Choose your location';

        // Update standings
        this.updateStandings(data.standings);

        // Handle new events
        if (data.new_events && data.new_events.length > 0) {
            data.new_events.forEach(event => {
                this.addMessage('warning', `New event: ${event.name} at ${event.location}`);
            });
        }

        // Update last AI search
        if (data.previous_ai_location) {
            this.elements.lastAiSearch.innerHTML = `Last round AI searched: <span class="location-name">${data.previous_ai_location}</span>`;
        } else {
            this.elements.lastAiSearch.textContent = '';
        }

        // Start timer
        this.startTimer(data.timer_seconds);

        // Enable location selection
        this.enableLocationSelection();

        // Clear any modals
        this.hideAllModals();
    },

    /**
     * Handle timer sync
     */
    onTimerSync(data) {
        this.state.timerValue = data.remaining_seconds;
        this.elements.timerValue.textContent = data.remaining_seconds;

        if (data.remaining_seconds <= 10) {
            this.elements.timer.classList.add('urgent');
        }
    },

    /**
     * Handle player submitted
     */
    onPlayerSubmitted(data) {
        this.addMessage('info', `${data.username} has made their choice`);
        this.updatePlayerStatus(data.user_id, 'submitted');
    },

    /**
     * Handle all choices locked
     */
    onChoicesLocked(data) {
        this.state.phase = 'resolving';
        this.elements.phaseInfo.textContent = 'All choices locked!';
        this.stopTimer();
        this.disableLocationSelection();
    },

    /**
     * Handle AI analyzing
     */
    onAiAnalyzing(data) {
        this.elements.phaseInfo.innerHTML = '<span class="animate-pulse">AI is analyzing...</span>';
    },

    /**
     * Handle round result
     */
    onRoundResult(data) {
        // Update standings
        this.updateStandings(data.standings);

        // Show results
        let html = `<p>AI searched: <strong>${data.ai_search_emoji} ${data.ai_search_location}</strong></p>`;
        html += '<div class="results-list">';

        data.player_results.forEach(result => {
            const outcomeClass = result.caught ? 'caught' : 'safe';
            const outcomeText = result.caught ? 'CAUGHT!' : `+${result.points_earned} pts`;

            html += `
                <div class="result-item">
                    <div class="player-info">
                        <span class="name">${result.username}</span>
                        <span class="location">${result.location_emoji} ${result.location}</span>
                    </div>
                    <div class="outcome ${outcomeClass}">${outcomeText}</div>
                </div>
            `;
        });

        html += '</div>';

        this.elements.resultTitle.textContent = `Round ${data.round_num} Result`;
        this.elements.resultContent.innerHTML = html;
        this.showModal('result-modal');
    },

    /**
     * Handle escape phase
     */
    onEscapePhase(data) {
        // Check if this is for the current user
        const currentUserId = App.state.user?.id;
        if (data.user_id !== currentUserId) {
            this.addMessage('warning', `${data.username} is trying to escape!`);
            return;
        }

        this.state.phase = 'escape';

        // Render escape options
        let html = '';
        data.escape_options.forEach(option => {
            html += `
                <div class="escape-option" data-option-id="${option.id}">
                    <span class="emoji">${option.emoji}</span>
                    <div class="info">
                        <div class="name">${option.name}</div>
                        <div class="type">${option.type.toUpperCase()}</div>
                    </div>
                </div>
            `;
        });

        this.elements.escapeOptions.innerHTML = html;

        // Add click handlers
        this.elements.escapeOptions.querySelectorAll('.escape-option').forEach(el => {
            el.addEventListener('click', () => {
                const optionId = el.dataset.optionId;
                gameSocket.submitEscapeChoice(optionId);
                this.disableEscapeOptions();
            });
        });

        // Start escape timer
        this.startEscapeTimer(data.timer_seconds);

        // Show modal
        this.showModal('escape-modal');
    },

    /**
     * Handle escape result
     */
    onEscapeResult(data) {
        this.hideModal('escape-modal');

        const result = data.escaped ? 'ESCAPED!' : 'CAUGHT!';
        const color = data.escaped ? 'success' : 'danger';

        this.addMessage(color, `${data.username} chose ${data.player_choice}. AI predicted ${data.ai_prediction}. ${result}`);

        if (data.escaped && data.points_awarded > 0) {
            this.addMessage('success', `${data.username} keeps ${data.points_awarded} points!`);
        }
    },

    /**
     * Handle player eliminated
     */
    onPlayerEliminated(data) {
        this.addMessage('danger', `${data.username} has been eliminated! Final score: ${data.final_score}`);
        this.updatePlayerEliminated(data.user_id);
    },

    /**
     * Handle game over
     */
    onGameOver(data) {
        this.state.inGame = false;
        this.state.phase = 'finished';
        this.stopTimer();

        let html = '';

        if (data.ai_wins) {
            this.elements.gameoverTitle.textContent = 'AI Wins!';
            html += '<p class="ai-victory">The AI caught everyone!</p>';
        } else {
            this.elements.gameoverTitle.textContent = 'Game Over!';
            html += `<div class="winner-display">Winner: <span class="winner-name">${data.winner.username}</span> with ${data.winner.score} points!</div>`;
        }

        html += '<div class="final-standings"><h3>Final Standings</h3>';
        data.final_standings.forEach((player, index) => {
            const isWinner = data.winner && player.user_id === data.winner.user_id;
            html += `
                <div class="final-standing-item ${isWinner ? 'winner' : ''}">
                    <span>${index + 1}. ${player.username}</span>
                    <span>${player.points} pts ${!player.alive ? '(eliminated)' : ''}</span>
                </div>
            `;
        });
        html += '</div>';

        html += `<p class="game-stats">Rounds played: ${data.rounds_played} | Duration: ${Math.floor(data.game_duration_seconds / 60)}m ${data.game_duration_seconds % 60}s</p>`;

        this.elements.gameoverContent.innerHTML = html;
        this.showModal('gameover-modal');
    },

    /**
     * Render location cards
     */
    renderLocations() {
        let html = '';
        this.state.locations.forEach((loc, index) => {
            html += `
                <div class="location-card" data-index="${index}">
                    <div class="emoji">${loc.emoji}</div>
                    <div class="name">${loc.name}</div>
                    <div class="range">${loc.min_points}-${loc.max_points} pts</div>
                </div>
            `;
        });
        this.elements.locationGrid.innerHTML = html;

        // Add click handlers
        this.elements.locationGrid.querySelectorAll('.location-card').forEach(card => {
            card.addEventListener('click', () => {
                if (this.state.phase !== 'choosing') return;
                if (card.classList.contains('disabled')) return;

                // Deselect previous
                this.elements.locationGrid.querySelectorAll('.location-card').forEach(c => {
                    c.classList.remove('selected');
                });

                // Select this one
                card.classList.add('selected');
                this.state.selectedLocation = parseInt(card.dataset.index);

                // Submit choice
                gameSocket.submitLocationChoice(this.state.selectedLocation);
                this.disableLocationSelection();

                this.addMessage('info', 'Choice submitted!');
            });
        });
    },

    /**
     * Update standings display
     */
    updateStandings(standings) {
        this.state.players = standings;

        let html = '';
        standings.forEach((player, index) => {
            const eliminated = !player.alive ? 'eliminated' : '';
            html += `
                <div class="standing-item ${eliminated}" data-user-id="${player.user_id}">
                    <span class="rank">#${index + 1}</span>
                    <span class="name">${player.username}</span>
                    <span class="points">${player.points} pts</span>
                    <span class="status-icon">${!player.alive ? '💀' : (player.connected ? '' : '📴')}</span>
                </div>
            `;
        });
        this.elements.standingsList.innerHTML = html;
    },

    /**
     * Enable location selection
     */
    enableLocationSelection() {
        this.elements.locationGrid.querySelectorAll('.location-card').forEach(card => {
            card.classList.remove('disabled', 'selected');
        });
    },

    /**
     * Disable location selection
     */
    disableLocationSelection() {
        this.elements.locationGrid.querySelectorAll('.location-card').forEach(card => {
            if (!card.classList.contains('selected')) {
                card.classList.add('disabled');
            }
        });
    },

    /**
     * Disable escape options
     */
    disableEscapeOptions() {
        this.elements.escapeOptions.querySelectorAll('.escape-option').forEach(el => {
            el.style.pointerEvents = 'none';
            el.style.opacity = '0.5';
        });
    },

    /**
     * Start the turn timer
     */
    startTimer(seconds) {
        this.state.timerValue = seconds;
        this.elements.timerValue.textContent = seconds;
        this.elements.timer.classList.remove('urgent');

        if (this.state.timer) {
            clearInterval(this.state.timer);
        }

        this.state.timer = setInterval(() => {
            this.state.timerValue--;
            this.elements.timerValue.textContent = this.state.timerValue;

            if (this.state.timerValue <= 10) {
                this.elements.timer.classList.add('urgent');
            }

            if (this.state.timerValue <= 0) {
                this.stopTimer();
            }
        }, 1000);
    },

    /**
     * Stop the timer
     */
    stopTimer() {
        if (this.state.timer) {
            clearInterval(this.state.timer);
            this.state.timer = null;
        }
    },

    /**
     * Start escape timer
     */
    startEscapeTimer(seconds) {
        let remaining = seconds;
        this.elements.escapeTimerValue.textContent = remaining;

        const interval = setInterval(() => {
            remaining--;
            this.elements.escapeTimerValue.textContent = remaining;

            if (remaining <= 0) {
                clearInterval(interval);
            }
        }, 1000);
    },

    /**
     * Add a message to the game log
     */
    addMessage(type, text) {
        const msg = document.createElement('div');
        msg.className = `game-message ${type}`;
        msg.textContent = text;
        this.elements.gameMessages.appendChild(msg);
        this.elements.gameMessages.scrollTop = this.elements.gameMessages.scrollHeight;
    },

    /**
     * Show a modal
     */
    showModal(id) {
        document.getElementById(id).classList.add('active');
    },

    /**
     * Hide a modal
     */
    hideModal(id) {
        document.getElementById(id).classList.remove('active');
    },

    /**
     * Hide all modals
     */
    hideAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            modal.classList.remove('active');
        });
    },

    /**
     * Update player status in standings
     */
    updatePlayerStatus(userId, status) {
        const item = this.elements.standingsList.querySelector(`[data-user-id="${userId}"]`);
        if (item) {
            const statusIcon = item.querySelector('.status-icon');
            if (status === 'submitted') {
                statusIcon.textContent = '✓';
            }
        }
    },

    /**
     * Update player as eliminated
     */
    updatePlayerEliminated(userId) {
        const item = this.elements.standingsList.querySelector(`[data-user-id="${userId}"]`);
        if (item) {
            item.classList.add('eliminated');
            const statusIcon = item.querySelector('.status-icon');
            statusIcon.textContent = '💀';
        }
    },
};
