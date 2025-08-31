import { useState, useEffect, useRef, useCallback } from 'react';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000';

export function useWebSocket(endpoint) {
    const [connected, setConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState(null);
    const [error, setError] = useState(null);

    const wsRef = useRef(null);
    const reconnectTimeoutRef = useRef(null);
    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 5;
    const baseReconnectDelay = 1000; // 1 second

    const connect = useCallback(() => {
        try {
            const wsUrl = `${WS_BASE_URL}${endpoint}`;
            console.debug(`Connecting to WebSocket: ${wsUrl}`);

            wsRef.current = new WebSocket(wsUrl);

            wsRef.current.onopen = () => {
                console.debug(`WebSocket connected: ${endpoint}`);
                setConnected(true);
                setError(null);
                reconnectAttempts.current = 0;
            };

            wsRef.current.onmessage = (event) => {
                console.debug(`WebSocket message received on ${endpoint}:`, event.data);
                setLastMessage(event);
            };

            wsRef.current.onclose = (event) => {
                console.debug(`WebSocket closed: ${endpoint}`, event.code, event.reason);
                setConnected(false);

                // Attempt reconnection if not a normal closure
                if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
                    const delay = Math.min(
                        baseReconnectDelay * Math.pow(2, reconnectAttempts.current),
                        30000 // Max 30 seconds
                    );

                    console.debug(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1})`);

                    reconnectTimeoutRef.current = setTimeout(() => {
                        reconnectAttempts.current++;
                        connect();
                    }, delay);
                }
            };

            wsRef.current.onerror = (event) => {
                console.error(`WebSocket error on ${endpoint}:`, event);
                setError(new Error(`WebSocket error: ${event.type}`));
            };

        } catch (err) {
            console.error(`Failed to create WebSocket connection to ${endpoint}:`, err);
            setError(err);
        }
    }, [endpoint]);

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }

        if (wsRef.current) {
            wsRef.current.close(1000, 'Component unmounting');
            wsRef.current = null;
        }

        setConnected(false);
        reconnectAttempts.current = 0;
    }, []);

    const sendMessage = useCallback((message) => {
        if (wsRef.current && connected) {
            const payload = typeof message === 'string' ? message : JSON.stringify(message);
            wsRef.current.send(payload);
            return true;
        }
        console.warn(`Cannot send message: WebSocket not connected to ${endpoint}`);
        return false;
    }, [endpoint, connected]);

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        connect();
        return disconnect;
    }, [connect, disconnect]);

    // Heartbeat to detect connection issues
    useEffect(() => {
        if (!connected) return;

        const heartbeatInterval = setInterval(() => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                // Send ping to Django Channels consumer
                wsRef.current.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // 30 seconds

        return () => clearInterval(heartbeatInterval);
    }, [connected]);

    return {
        connected,
        lastMessage,
        error,
        sendMessage,
        reconnect: connect,
        disconnect,
    };
}