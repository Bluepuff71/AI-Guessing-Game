/**
 * API client for LOOT RUN server
 */

const API = {
    baseUrl: window.location.origin + '/api',
    token: null,

    /**
     * Set the auth token
     */
    setToken(token) {
        this.token = token;
        localStorage.setItem('lootrun_token', token);
    },

    /**
     * Load token from storage
     */
    loadToken() {
        this.token = localStorage.getItem('lootrun_token');
        return this.token;
    },

    /**
     * Clear auth token
     */
    clearToken() {
        this.token = null;
        localStorage.removeItem('lootrun_token');
    },

    /**
     * Make an API request
     */
    async request(endpoint, options = {}) {
        const url = this.baseUrl + endpoint;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Auth endpoints
    async register(email, username, password) {
        const data = await this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify({ email, username, password }),
        });
        return data;
    },

    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(this.baseUrl + '/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Login failed');
        }

        this.setToken(data.access_token);
        return data;
    },

    async getProfile() {
        return this.request('/auth/profile');
    },

    async getMe() {
        return this.request('/auth/me');
    },

    // Lobby endpoints
    async createLobby(settings = {}) {
        return this.request('/lobbies', {
            method: 'POST',
            body: JSON.stringify({ settings }),
        });
    },

    async getLobby(code) {
        return this.request(`/lobbies/${code}`);
    },

    async joinLobby(code) {
        return this.request(`/lobbies/${code}/join`, {
            method: 'POST',
        });
    },

    async leaveLobby(code) {
        return this.request(`/lobbies/${code}/leave`, {
            method: 'DELETE',
        });
    },

    async toggleReady(code) {
        return this.request(`/lobbies/${code}/ready`, {
            method: 'POST',
        });
    },

    // Game endpoints
    async getGame(gameId) {
        return this.request(`/games/${gameId}`);
    },

    async getGameHistory(gameId) {
        return this.request(`/games/${gameId}/history`);
    },
};

// Load token on startup
API.loadToken();
