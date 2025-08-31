import { useMemo } from 'react';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export function useApi() {
    const api = useMemo(() => {
        const instance = axios.create({
            baseURL: API_BASE_URL,
            timeout: 10000,
            headers: {
                'Content-Type': 'application/json',
            },
        });

        // Request interceptor for debugging
        instance.interceptors.request.use(
            (config) => {
                console.debug(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
                return config;
            },
            (error) => {
                console.error('API Request Error:', error);
                return Promise.reject(error);
            }
        );

        // Response interceptor for error handling
        instance.interceptors.response.use(
            (response) => {
                console.debug(`API Response: ${response.status} ${response.config.url}`);
                return response;
            },
            (error) => {
                console.error('API Response Error:', error.response?.data || error.message);

                // Extract error details
                const errorData = error.response?.data;
                const traceId = error.response?.headers?.['x-trace-id'];

                // Enhanced error object
                const enhancedError = new Error(
                    errorData?.message || error.message || 'Unknown API error'
                );
                enhancedError.response = error.response;
                enhancedError.traceId = traceId;
                enhancedError.details = errorData?.details;

                return Promise.reject(enhancedError);
            }
        );

        return instance;
    }, []);

    return api;
}