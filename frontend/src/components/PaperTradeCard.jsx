import { useState, useEffect } from 'react';
import { Card, Button, Alert, Badge, Form, Row, Col } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi';
import { useWebSocket } from '../hooks/useWebSocket';

export function PaperTradeCard() {
    const [paperEnabled, setPaperEnabled] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [wsStatus, setWsStatus] = useState('disconnected');

    // Use useDjangoData for paper metrics
    const {
        data: paperMetrics,
        refresh: refreshMetrics,
        loading: metricsLoading
    } = useDjangoData('/api/v1/metrics/paper', {
        total_trades: 0,
        winning_trades: 0,
        total_pnl_usd: 0.0,
        win_rate_pct: 0.0,
        session_start: null
    });

    // WebSocket for real-time updates
    const { lastMessage, connectionState } = useWebSocket('/ws/paper');

    // Update WebSocket status
    useEffect(() => {
        setWsStatus(connectionState);
    }, [connectionState]);

    // Handle WebSocket messages
    useEffect(() => {
        if (lastMessage) {
            try {
                const data = JSON.parse(lastMessage.data);

                if (data.type === 'hello') {
                    // Initial connection - could get paper_enabled status from server
                    console.log('Connected to paper trading WebSocket');
                }

                if (data.type === 'status') {
                    // Paper trading status update
                    if (data.payload && typeof data.payload.paper_enabled === 'boolean') {
                        setPaperEnabled(data.payload.paper_enabled);
                    }
                }

                if (data.type === 'paper_metrics') {
                    // Real-time metrics update
                    if (data.payload) {
                        // Refresh metrics to get latest data
                        refreshMetrics();
                    }
                }

                if (data.type === 'thought_log') {
                    // AI thought log received - metrics might have changed
                    setTimeout(refreshMetrics, 1000);
                }

            } catch (err) {
                console.error('Failed to parse WebSocket message:', err);
            }
        }
    }, [lastMessage, refreshMetrics]);

    const togglePaper = async () => {
        console.log('📝 Paper trading toggle clicked');  // Debug log
        setLoading(true);
        setError(null);

        try {
            const apiUrl = 'http://127.0.0.1:8000/api/v1/paper/toggle';  // Fixed URL
            console.log('📝 Sending POST request to:', apiUrl);  // Debug log

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ enabled: !paperEnabled })
            });

            console.log('📝 Toggle response status:', response.status);  // Debug log

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('📝 Toggle response data:', data);  // Debug log

            if (data.status === 'ok') {
                setPaperEnabled(data.paper_enabled);
                refreshMetrics(); // Refresh metrics after toggle
                console.log('✅ Paper trading toggled successfully:', data.paper_enabled);
            } else {
                throw new Error(data.message || 'Toggle failed');
            }

        } catch (err) {
            console.error('❌ Paper trading toggle failed:', err);  // Debug log
            setError(`Failed to toggle paper trading: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const testThoughtLog = async () => {
        console.log('🧠 Test AI Thought Log button clicked');  // Debug log
        setLoading(true);
        setError(null);

        try {
            const apiUrl = 'http://127.0.0.1:8000/api/v1/paper/thought-log/test';  // Fixed URL
            console.log('🧠 Sending POST request to:', apiUrl);  // Debug log

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            console.log('🧠 Response status:', response.status);  // Debug log

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('🧠 Response data:', data);  // Debug log

            if (data.status === 'ok') {
                // Success - the thought log should appear in the WebSocket stream
                console.log('✅ Test thought log emitted:', data.frame_id);
                console.log('🔌 WebSocket connections:', data.connections);
            } else {
                throw new Error(data.message || 'Thought log test failed');
            }

        } catch (err) {
            console.error('❌ Thought log test failed:', err);  // Debug log
            setError(`Thought log test failed: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const getConnectionBadge = () => {
        switch (wsStatus) {
            case 'open':
                return <Badge bg="success" className="ms-2">🟢</Badge>;
            case 'connecting':
                return <Badge bg="warning" className="ms-2">🟡</Badge>;
            case 'closed':
                return <Badge bg="danger" className="ms-2">🔴</Badge>;
            default:
                return <Badge bg="secondary" className="ms-2">⚪</Badge>;
        }
    };

    const formatCurrency = (value) => {
        if (typeof value !== 'number') return '$0.00';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(value);
    };

    const formatPercentage = (value) => {
        if (typeof value !== 'number') return '0.0%';
        return `${value.toFixed(1)}%`;
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center">
                    <strong>📝 Paper Trading</strong>
                    {getConnectionBadge()}
                    <Badge bg={paperEnabled ? 'success' : 'secondary'} className="ms-2">
                        {paperEnabled ? 'ENABLED' : 'DISABLED'}
                    </Badge>
                </div>
                <Form.Check
                    type="switch"
                    id="paper-trading-switch"
                    checked={paperEnabled}
                    onChange={togglePaper}
                    disabled={loading}
                />
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" className="mb-3">
                        <strong>Error:</strong> {error}
                    </Alert>
                )}

                {/* Paper Trading Metrics */}
                <Row className="text-center mb-3">
                    <Col xs={6} md={3}>
                        <div className="fw-bold text-muted small">TOTAL TRADES</div>
                        <div className="fs-5">
                            {metricsLoading ? '...' : paperMetrics.total_trades || 0}
                        </div>
                    </Col>
                    <Col xs={6} md={3}>
                        <div className="fw-bold text-muted small">WINNING</div>
                        <div className="fs-5 text-success">
                            {metricsLoading ? '...' : paperMetrics.winning_trades || 0}
                        </div>
                    </Col>
                    <Col xs={6} md={3}>
                        <div className="fw-bold text-muted small">WIN RATE</div>
                        <div className="fs-5">
                            {metricsLoading ? '...' : formatPercentage(paperMetrics.win_rate_pct)}
                        </div>
                    </Col>
                    <Col xs={6} md={3}>
                        <div className="fw-bold text-muted small">TOTAL P&L</div>
                        <div className={`fs-5 ${(paperMetrics.total_pnl_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                            {metricsLoading ? '...' : formatCurrency(paperMetrics.total_pnl_usd)}
                        </div>
                    </Col>
                </Row>

                {/* Action Buttons */}
                <div className="d-flex gap-2 justify-content-center flex-wrap">
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={testThoughtLog}
                        disabled={loading || !paperEnabled || wsStatus !== 'open'}
                        className="d-flex align-items-center gap-1"
                    >
                        {loading ? (
                            <>
                                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                                Testing...
                            </>
                        ) : (
                            <>
                                🧠 Test AI Thought Log
                            </>
                        )}
                    </Button>

                    <Button
                        variant="outline-secondary"
                        size="sm"
                        onClick={refreshMetrics}
                        disabled={metricsLoading}
                    >
                        {metricsLoading ? 'Refreshing...' : '🔄 Refresh Metrics'}
                    </Button>
                </div>

                {/* Status Messages */}
                {!paperEnabled && (
                    <div className="text-center text-muted mt-3">
                        <small>
                            📊 Enable paper trading to practice with virtual funds and see AI reasoning
                        </small>
                    </div>
                )}

                {paperEnabled && wsStatus !== 'open' && (
                    <Alert variant="warning" className="mt-3 mb-0">
                        <small>
                            <strong>WebSocket Disconnected:</strong> Real-time updates unavailable.
                            AI Thought Log will not stream until reconnected.
                        </small>
                    </Alert>
                )}

                {paperEnabled && wsStatus === 'open' && (
                    <div className="text-center text-success mt-3">
                        <small>
                            ✅ Paper trading active • WebSocket connected • Ready for AI thoughts
                        </small>
                    </div>
                )}

                {/* Session Info */}
                {paperMetrics.session_start && (
                    <div className="text-center text-muted mt-2">
                        <small>
                            Session started: {new Date(paperMetrics.session_start).toLocaleString()}
                        </small>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
}