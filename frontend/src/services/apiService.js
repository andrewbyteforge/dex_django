// APP: frontend
// FILE: frontend/src/services/apiService.js
// FUNCTION: Real API service for copy trading data integration

const API_BASE = 'http://127.0.0.1:8000';

// Error handling utility
const handleApiError = (error, context = '') => {
    console.error(`API Error ${context}:`, error);

    if (error.response) {
        // Server responded with error status
        throw new Error(`Server error: ${error.response.status} - ${error.response.data?.error || error.response.statusText}`);
    } else if (error.request) {
        // Network error
        throw new Error('Network error: Unable to connect to server');
    } else {
        // Request setup error
        throw new Error(`Request error: ${error.message}`);
    }
};

// HTTP client utility
const apiClient = {
    async get(url, params = {}) {
        try {
            const searchParams = new URLSearchParams(params);
            const fullUrl = `${API_BASE}${url}${searchParams.toString() ? '?' + searchParams.toString() : ''}`;

            const response = await fetch(fullUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            handleApiError(error, `GET ${url}`);
        }
    },

    async post(url, data = {}) {
        try {
            const response = await fetch(`${API_BASE}${url}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`HTTP ${response.status}: ${errorData.error || response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            handleApiError(error, `POST ${url}`);
        }
    },

    async delete(url) {
        try {
            const response = await fetch(`${API_BASE}${url}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            handleApiError(error, `DELETE ${url}`);
        }
    }
};

// Copy Trading API Service
export const copyTradingApi = {
    // Get system status with real metrics
    async getStatus() {
        return await apiClient.get('/api/v1/copy/status');
    },

    // Get all followed traders with performance data
    async getTraders() {
        return await apiClient.get('/api/v1/copy/traders');
    },

    // Add a new trader to follow
    async addTrader(traderData) {
        return await apiClient.post('/api/v1/copy/traders', traderData);
    },

    // Remove a followed trader
    async removeTrader(traderId) {
        return await apiClient.delete(`/api/v1/copy/traders/${traderId}`);
    },

    // Update trader settings
    async updateTrader(traderId, updates) {
        return await apiClient.post(`/api/v1/copy/traders/${traderId}`, updates);
    },

    // Get copy trade history
    async getTrades(filters = {}) {
        return await apiClient.get('/api/v1/copy/trades', filters);
    }
};

// Discovery API Service
export const discoveryApi = {
    // Get discovery system status
    async getStatus() {
        return await apiClient.get('/api/v1/copy/discovery/status');
    },

    // Start auto discovery
    async discoverTraders(config) {
        return await apiClient.post('/api/v1/copy/discovery/discover-traders', config);
    },

    // Analyze a specific wallet
    async analyzeWallet(walletData) {
        return await apiClient.post('/api/v1/copy/discovery/analyze-wallet', walletData);
    }
};

// Health Check API Service
export const healthApi = {
    // Basic health check
    async getHealth() {
        return await apiClient.get('/health');
    },

    // Copy trading specific health
    async getCopyTradingHealth() {
        return await apiClient.get('/health/copy-trading');
    }
};

// Frontend-specific API wrappers (for backward compatibility)
export const frontendApi = {
    // Copy Trading
    async getCopyTradingStatus() {
        return await apiClient.get('/api/v1/frontend/copy-trading/status');
    },

    async getFollowedTraders() {
        return await apiClient.get('/api/v1/frontend/copy-trading/traders');
    },

    async getCopyTrades(status = null, limit = 50) {
        const params = { limit };
        if (status) params.status = status;
        return await apiClient.get('/api/v1/frontend/copy-trading/trades', params);
    },

    async addTrader(traderData) {
        return await apiClient.post('/api/v1/frontend/copy-trading/add-trader', traderData);
    },

    // Discovery
    async getDiscoveryStatus() {
        return await apiClient.get('/api/v1/frontend/discovery/status');
    },

    async discoverTraders(config) {
        return await apiClient.post('/api/v1/frontend/discovery/discover-traders', config);
    },

    async analyzeWallet(walletData) {
        return await apiClient.post('/api/v1/frontend/discovery/analyze-wallet', walletData);
    }
};

// Utility functions for data validation and transformation
export const apiUtils = {
    // Validate wallet address format
    isValidWalletAddress(address) {
        return /^0x[a-fA-F0-9]{40}$/.test(address);
    },

    // Format API response for frontend consumption
    formatTraderData(apiTrader) {
        return {
            id: apiTrader.id,
            wallet_address: apiTrader.wallet_address,
            trader_name: apiTrader.trader_name,
            description: apiTrader.description,
            chain: apiTrader.chain,
            copy_percentage: parseFloat(apiTrader.copy_percentage || 0),
            max_position_usd: parseFloat(apiTrader.max_position_usd || 0),
            status: apiTrader.status,
            quality_score: parseInt(apiTrader.quality_score || 0),
            total_pnl: parseFloat(apiTrader.total_pnl || 0),
            win_rate: parseFloat(apiTrader.win_rate || 0),
            total_trades: parseInt(apiTrader.total_trades || 0),
            avg_trade_size: parseFloat(apiTrader.avg_trade_size || 0),
            last_activity_at: apiTrader.last_activity_at,
            created_at: apiTrader.created_at
        };
    },

    // Format discovered wallet data
    formatDiscoveredWallet(apiWallet) {
        return {
            id: apiWallet.id,
            address: apiWallet.address,
            chain: apiWallet.chain,
            quality_score: parseInt(apiWallet.quality_score || 0),
            total_volume_usd: parseFloat(apiWallet.total_volume_usd || 0),
            win_rate: parseFloat(apiWallet.win_rate || 0),
            trades_count: parseInt(apiWallet.trades_count || 0),
            avg_trade_size: parseFloat(apiWallet.avg_trade_size || 0),
            last_active: apiWallet.last_active,
            recommended_copy_percentage: parseFloat(apiWallet.recommended_copy_percentage || 0),
            risk_level: apiWallet.risk_level,
            confidence: apiWallet.confidence
        };
    },

    // Format copy trade data
    formatCopyTrade(apiTrade) {
        return {
            id: apiTrade.id,
            trader_address: apiTrade.trader_address,
            trader_name: apiTrade.trader_name,
            token_symbol: apiTrade.token_symbol,
            action: apiTrade.action,
            amount_usd: parseFloat(apiTrade.amount_usd || 0),
            status: apiTrade.status,
            pnl_usd: parseFloat(apiTrade.pnl_usd || 0),
            timestamp: apiTrade.timestamp,
            chain: apiTrade.chain,
            tx_hash: apiTrade.tx_hash
        };
    },

    // Handle API errors gracefully
    handleApiResponse(response, context = '') {
        if (response.status === 'error') {
            throw new Error(response.error || `API error in ${context}`);
        }
        return response;
    }
};

// Connection testing utility
export const connectionTest = {
    async testConnection() {
        try {
            const response = await apiClient.get('/health');
            return {
                connected: true,
                data: response
            };
        } catch (error) {
            return {
                connected: false,
                error: error.message
            };
        }
    },

    async testCopyTradingApi() {
        try {
            const response = await copyTradingApi.getStatus();
            return {
                available: true,
                data: response
            };
        } catch (error) {
            return {
                available: false,
                error: error.message
            };
        }
    }
};

// Export default API service
export default {
    copyTrading: copyTradingApi,
    discovery: discoveryApi,
    health: healthApi,
    frontend: frontendApi,
    utils: apiUtils,
    test: connectionTest
};