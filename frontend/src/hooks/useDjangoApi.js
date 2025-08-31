import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// Django runs on port 8000 by default
const DJANGO_API_BASE = import.meta.env.VITE_DJANGO_API_BASE || 'http://127.0.0.1:8000';

// Create Django API client
const djangoApi = axios.create({
    baseURL: DJANGO_API_BASE,
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json',
        // Add X-API-Key header if needed for Django auth
        // 'X-API-Key': 'your-api-key-here'
    },
});

// Response interceptor for Django API
djangoApi.interceptors.response.use(
    (response) => {
        console.debug(`Django API Response: ${response.status} ${response.config.url}`);
        return response;
    },
    (error) => {
        console.error('Django API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

export function useDjangoApi() {
    return djangoApi;
}

// Hook for fetching paginated data from Django REST API
export function useDjangoData(endpoint, dependencies = []) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);

    const fetchData = useCallback(async (pageNum = 1) => {
        setLoading(true);
        setError(null);

        try {
            const response = await djangoApi.get(`${endpoint}?page=${pageNum}`);
            setData(response.data);
            setPage(pageNum);
        } catch (err) {
            setError(err);
            console.error(`Failed to fetch ${endpoint}:`, err);
        } finally {
            setLoading(false);
        }
    }, [endpoint]);

    useEffect(() => {
        fetchData(1);
    }, [fetchData, ...dependencies]);

    const nextPage = useCallback(() => {
        if (data?.next) {
            fetchData(page + 1);
        }
    }, [fetchData, page, data?.next]);

    const prevPage = useCallback(() => {
        if (data?.previous) {
            fetchData(page - 1);
        }
    }, [fetchData, page, data?.previous]);

    const refresh = useCallback(() => {
        fetchData(page);
    }, [fetchData, page]);

    return {
        data,
        loading,
        error,
        page,
        hasNext: !!data?.next,
        hasPrev: !!data?.previous,
        nextPage,
        prevPage,
        refresh,
        refetch: fetchData,
    };
}

// Hook for bot control (start/stop/status)
export function useBotControl() {
    const [botStatus, setBotStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchStatus = useCallback(async () => {
        setLoading(true);
        try {
            const response = await djangoApi.get('/api/v1/bot/status');
            setBotStatus(response.data);
            setError(null);
        } catch (err) {
            setError(err);
        } finally {
            setLoading(false);
        }
    }, []);

    const startBot = useCallback(async () => {
        setLoading(true);
        try {
            const response = await djangoApi.post('/api/v1/bot/start');
            setBotStatus(response.data);
            setError(null);
            return response.data;
        } catch (err) {
            setError(err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    const stopBot = useCallback(async () => {
        setLoading(true);
        try {
            const response = await djangoApi.post('/api/v1/bot/stop');
            setBotStatus(response.data);
            setError(null);
            return response.data;
        } catch (err) {
            setError(err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    const getSettings = useCallback(async () => {
        try {
            const response = await djangoApi.get('/api/v1/bot/settings');
            return response.data;
        } catch (err) {
            setError(err);
            throw err;
        }
    }, []);

    const updateSettings = useCallback(async (settings) => {
        try {
            const response = await djangoApi.put('/api/v1/bot/settings', settings);
            return response.data;
        } catch (err) {
            setError(err);
            throw err;
        }
    }, []);

    // Fetch status on mount
    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    return {
        botStatus,
        loading,
        error,
        startBot,
        stopBot,
        fetchStatus,
        getSettings,
        updateSettings,
    };
}

// Hook for creating/updating records
export function useDjangoMutations(endpoint) {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const create = useCallback(async (data) => {
        setLoading(true);
        setError(null);
        try {
            const response = await djangoApi.post(endpoint, data);
            return response.data;
        } catch (err) {
            console.error('Create error:', err.response?.data || err.message);
            setError(err.response?.data || err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [endpoint]);

    const update = useCallback(async (id, data) => {
        setLoading(true);
        setError(null);
        try {
            const response = await djangoApi.put(`${endpoint}${id}/`, data);
            return response.data;
        } catch (err) {
            setError(err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [endpoint]);

    const remove = useCallback(async (id) => {
        setLoading(true);
        setError(null);
        try {
            const response = await djangoApi.delete(`${endpoint}${id}/`);
            return true;
        } catch (err) {
            console.error('Delete error:', err.response?.data || err.message);
            setError(err.response?.data || err);
            throw err;
        } finally {
            setLoading(false);
        }
    }, [endpoint]);

    return {
        loading,
        error,
        create,
        update,
        remove,
    };
}