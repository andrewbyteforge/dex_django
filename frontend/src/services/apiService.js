// APP: frontend
// FILE: frontend/src/services/apiService.js
// FUNCTION: Clean API service with only working endpoints

const API_BASE = 'http://127.0.0.1:8000';

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
            console.error(`API Error GET ${url}:`, error);
            throw error;
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
            console.error(`API Error POST ${url}:`, error);
            throw error;
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
            console.error(`API Error DELETE ${url}:`, error);
            throw error;
        }
    }
};

// Copy Trading API Service - Core endpoints only
export const copyTradingApi = {
    // Get system status
    async getStatus() {
        return await apiClient.get('/api/v1/copy/status');
    },

    // Get all followed traders
    async getTraders() {
        return await apiClient.get('/api/v1/copy/traders');
    },

    // Get copy trade history
    async getTrades(filters = {}) {
        return await apiClient.get('/api/v1/copy/trades', filters);
    }
};

// Discovery API Service - Core endpoints only
export const discoveryApi = {
    // Get discovery system status
    async getStatus() {
        return await apiClient.get('/api/v1/copy/discovery/status');
    },

    // Start auto discovery
    async discoverTraders(config) {
        return await apiClient.post('/api/v1/copy/discovery/discover-traders', config);
    }
};

// Health Check API Service
export const healthApi = {
    // Basic health check
    async getHealth() {
        return await apiClient.get('/health');
    }
};

// Utility functions - Essential only
export const apiUtils = {
    // Validate wallet address format
    isValidWalletAddress(address) {
        return /^0x[a-fA-F0-9]{40}$/.test(address);
    },

    // Format trader data for frontend
    formatTraderData(apiTrader) {
        return {
            id: apiTrader.id,
            wallet_address: apiTrader.wallet_address,
            trader_name: apiTrader.trader_name,
            chain: apiTrader.chain,
            copy_percentage: parseFloat(apiTrader.copy_percentage || 0),
            max_position_usd: parseFloat(apiTrader.max_position_usd || 0),
            status: apiTrader.status,
            quality_score: parseInt(apiTrader.quality_score || 0),
            total_pnl: parseFloat(apiTrader.total_pnl || 0),
            win_rate: parseFloat(apiTrader.win_rate || 0),
            total_trades: parseInt(apiTrader.total_trades || 0)
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
            recommended_copy_percentage: parseFloat(apiWallet.recommended_copy_percentage || 0)
        };
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
    }
};

// Export default API service
export default {
    copyTrading: copyTradingApi,
    discovery: discoveryApi,
    health: healthApi,
    utils: apiUtils,
    test: connectionTest
};