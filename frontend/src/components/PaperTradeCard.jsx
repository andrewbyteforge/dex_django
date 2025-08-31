import { useState, useEffect } from 'react';
import { Card, Button, Alert, Badge, Form } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi';
import { useWebSocket } from '../hooks/useWebSocket';

export function PaperTradeCard() {
    const [paperEnabled, setPaperEnabled] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Use useDjangoData instead of useDjangoApi
    const {
        data: paperMetrics,
        refresh: refreshMetrics
    } = useDjangoData('/api/v1/metrics/paper', {
        total_trades: 0,
        winning_trades: 0,
        total_pnl: 0,
        win_rate: 0
    });

    // WebSocket for real-time updates
    const { lastMessage } = useWebSocket('/ws/paper');

    useEffect(() => {
        if (lastMessage) {
            const data = JSON.parse(lastMessage.data);
            if (data.type === 'hello') {
                setPaperEnabled(data.payload.paper_enabled);
            }
        }
    }, [lastMessage]);

    const togglePaper = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await djangoApi.post('/api/v1/paper/toggle');
            setPaperEnabled(response.data.enabled);
            refreshMetrics(); // Refresh metrics after toggle
        } catch (err) {
            setError(err.response?.data?.error || 'Failed to toggle paper trading');
            console.error('Paper trading toggle failed:', err);
        } finally {
            setLoading(false);
        }
    };

    const testThoughtLog = async () => {
        setLoading(true);
        setError(null);

        try {
            await djangoApi.post('/api/v1/paper/thought-log/test');
            refreshMetrics();
        } catch (err) {
            setError(err.response?.data?.error || 'Thought log test failed');
            console.error('Thought log test failed:', err);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>📝 Paper Trading</strong>
                    <Badge bg={paperEnabled ? 'success' : 'secondary'}>
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

                <div className="row text-center mb-3">
                    <div className="col-6 col-md-3">
                        <div className="fw-bold">Total Trades</div>
                        <div className="fs-5">{paperMetrics.total_trades || 0}</div>
                    </div>
                    <div className="col-6 col-md-3">
                        <div className="fw-bold">Winning</div>
                        <div className="fs-5 text-success">{paperMetrics.winning_trades || 0}</div>
                    </div>
                    <div className="col-6 col-md-3">
                        <div className="fw-bold">Win Rate</div>
                        <div className="fs-5">{(paperMetrics.win_rate || 0).toFixed(1)}%</div>
                    </div>
                    <div className="col-6 col-md-3">
                        <div className="fw-bold">Total P&L</div>
                        <div className={`fs-5 ${(paperMetrics.total_pnl || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                            ${(paperMetrics.total_pnl || 0).toFixed(2)}
                        </div>
                    </div>
                </div>

                <div className="d-flex gap-2 justify-content-center">
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={testThoughtLog}
                        disabled={loading || !paperEnabled}
                    >
                        {loading ? 'Testing...' : 'Test AI Thought Log'}
                    </Button>
                </div>

                {!paperEnabled && (
                    <div className="text-center text-muted mt-3">
                        <small>Enable paper trading to practice with virtual funds</small>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
}