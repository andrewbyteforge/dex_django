import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

const djangoApi = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
});

// Response interceptor
djangoApi.interceptors.response.use(
    (response) => {
        console.log(`Django API Response: ${response.status} ${response.config.url}`);
        return response;
    },
    (error) => {
        console.error('Django API Error:', error.response?.data || error.message);
        return Promise.reject(error);
    }
);

export function useDjangoData(endpoint, initialData = []) {
    const [data, setData] = useState(initialData);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchData = useCallback(async () => {
        if (!endpoint) return;

        setLoading(true);
        setError(null);

        try {
            const response = await djangoApi.get(endpoint);
            setData(response.data);
        } catch (err) {
            console.error(`Failed to fetch ${endpoint}:`, err);
            setError(err);

            // Don't clear existing data on error, keep stale data visible
            if (!data || (Array.isArray(data) && data.length === 0)) {
                setData(initialData);
            }
        } finally {
            setLoading(false);
        }
    }, [endpoint]); // Fixed: removed data from dependencies to prevent infinite loops

    const refresh = useCallback(() => {
        return fetchData();
    }, [fetchData]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return { data, loading, error, refresh };
}

export function useBotControl() {
    const [botStatus, setBotStatus] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchStatus = useCallback(async () => {
        try {
            const response = await djangoApi.get('/api/v1/bot/status');
            setBotStatus(response.data);
            setError(null);
        } catch (err) {
            setError(err);
            console.error('Failed to fetch bot status:', err);
        }
    }, []);

    useEffect(() => {
        fetchStatus();
    }, [fetchStatus]);

    const startBot = useCallback(async () => {
        setLoading(true);
        try {
            await djangoApi.post('/api/v1/bot/start');
            await fetchStatus();
        } catch (err) {
            setError(err);
        } finally {
            setLoading(false);
        }
    }, [fetchStatus]);

    const stopBot = useCallback(async () => {
        setLoading(true);
        try {
            await djangoApi.post('/api/v1/bot/stop');
            await fetchStatus();
        } catch (err) {
            setError(err);
        } finally {
            setLoading(false);
        }
    }, [fetchStatus]);

    return { botStatus, loading, startBot, stopBot, error };
}

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
            await djangoApi.delete(`${endpoint}${id}/`);
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

export { djangoApi };