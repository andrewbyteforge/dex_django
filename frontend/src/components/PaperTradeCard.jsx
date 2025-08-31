import { useState, useEffect } from 'react';
import { Card, Button, Badge, Alert, Spinner } from 'react-bootstrap';
import { useDjangoApi } from '../hooks/useDjangoApi.js';
import { useWebSocket } from '../hooks/useWebSocket.js';

export function PaperTradeCard() {
    const [paperEnabled, setPaperEnabled] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [thoughtLogs, setThoughtLogs] = useState([]);
    const [metrics, setMetrics] = useState(null);

    const api = useDjangoApi();
    const { connected, lastMessage } = useWebSocket('/ws/paper');

    // Handle WebSocket messages
    useEffect(() => {
        if (!lastMessage) return;

        try {
            const msg = JSON.parse(lastMessage.data);

            switch (msg.type) {
                case 'hello':
                    setPaperEnabled(msg.payload?.paper_enabled || false);
                    break;
                case 'status':
                    setPaperEnabled(msg.payload?.paper_enabled || false);
                    break;
                case 'thought_log':
                    setThoughtLogs(prev => [msg, ...prev].slice(0, 10)); // Keep last 10
                    break;
                case 'paper_metrics':
                    setMetrics(msg.payload);
                    break;
                default:
                    console.debug('Unhandled WS message:', msg.type);
            }
        } catch (err) {
            console.warn('Failed to parse WebSocket message:', err);
        }
    }, [lastMessage]);

    // Toggle paper trading mode
    const handleToggle = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.post('/api/v1/paper/toggle', {
                enabled: !paperEnabled
            });

            if (response.data?.status === 'ok') {
                setPaperEnabled(response.data.paper_enabled);
            }
        } catch (err) {
            setError(`Failed to toggle paper trading: ${err.response?.data?.error || err.message}`);
        } finally {
            setLoading(false);
        }
    };

    // Test thought log
    const handleTestThoughtLog = async () => {
        try {
            await api.post('/api/v1/paper/thought-log/test');
        } catch (err) {
            console.error('Failed to emit test thought log:', err);
        }
    };

    return (
        <Card className="mb-3">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>Paper Trading</strong>
                    {paperEnabled && <Badge bg="success">Active</Badge>}
                    {!connected && <Badge bg="warning">Disconnected</Badge>}
                </div>
                <div className="d-flex gap-2">
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handleTestThoughtLog}
                        disabled={!connected}
                    >
                        Test AI Log
                    </Button>
                    <Button
                        variant={paperEnabled ? "danger" : "success"}
                        size="sm"
                        onClick={handleToggle}
                        disabled={loading}
                    >
                        {loading && <Spinner size="sm" className="me-1" />}
                        {paperEnabled ? "Stop Paper" : "Start Paper"}
                    </Button>
                </div>
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" className="mb-3">
                        {error}
                    </Alert>
                )}

                {/* Connection Status */}
                <div className="mb-3">
                    <small className="text-muted">
                        WebSocket: {connected ? "Connected" : "Disconnected"}
                    </small>
                </div>

                {/* Paper Metrics */}
                {metrics && (
                    <div className="row mb-3">
                        <div className="col-md-3">
                            <div className="text-center">
                                <div className="fw-bold">Session P&L</div>
                                <div className={`fs-5 ${metrics.session_pnl_gbp >= 0 ? 'text-success' : 'text-danger'}`}>
                                    £{metrics.session_pnl_gbp?.toFixed(2) || '0.00'}
                                </div>
                            </div>
                        </div>
                        <div className="col-md-3">
                            <div className="text-center">
                                <div className="fw-bold">Trades</div>
                                <div className="fs-5">{metrics.session_trades || 0}</div>
                            </div>
                        </div>
                        <div className="col-md-3">
                            <div className="text-center">
                                <div className="fw-bold">Win Rate</div>
                                <div className="fs-5">{(metrics.win_rate * 100)?.toFixed(1) || '0.0'}%</div>
                            </div>
                        </div>
                        <div className="col-md-3">
                            <div className="text-center">
                                <div className="fw-bold">Max DD</div>
                                <div className="fs-5 text-danger">
                                    £{Math.abs(metrics.max_drawdown_gbp || 0).toFixed(2)}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* AI Thought Log */}
                <div>
                    <h6 className="mb-2">AI Thought Log</h6>
                    {thoughtLogs.length === 0 ? (
                        <div className="text-muted small">
                            No recent thoughts. Enable paper trading to see AI reasoning.
                        </div>
                    ) : (
                        <div className="thought-log-container" style={{ maxHeight: '300px', overflowY: 'auto' }}>
                            {thoughtLogs.map((log, idx) => (
                                <ThoughtLogEntry key={`${log.timestamp}-${idx}`} log={log} />
                            ))}
                        </div>
                    )}
                </div>
            </Card.Body>
        </Card>
    );
}

function ThoughtLogEntry({ log }) {
    const payload = log.payload || {};
    const opportunity = payload.opportunity || {};
    const decision = payload.decision || {};
    const riskGates = payload.risk_gates || {};

    const isPositiveDecision = decision.action?.includes('buy') || decision.action?.includes('enter');

    return (
        <div className="border rounded p-2 mb-2 bg-light">
            <div className="d-flex justify-content-between align-items-start mb-1">
                <div className="d-flex align-items-center gap-2">
                    <Badge bg={isPositiveDecision ? "success" : "secondary"}>
                        {opportunity.symbol || 'Unknown'}
                    </Badge>
                    <small className="text-muted">
                        {opportunity.chain} • {opportunity.dex}
                    </small>
                </div>
                <small className="text-muted">
                    {new Date(log.timestamp).toLocaleTimeString()}
                </small>
            </div>

            {decision.rationale && (
                <div className="small mb-1">
                    <strong>Decision:</strong> {decision.action} - {decision.rationale}
                </div>
            )}

            {payload.discovery_signals && (
                <div className="small text-muted">
                    Liq: ${payload.discovery_signals.liquidity_usd?.toLocaleString()} •
                    Trend: {(payload.discovery_signals.trend_score * 100)?.toFixed(0)}%
                </div>
            )}

            {(riskGates.buy_tax || riskGates.sell_tax) && (
                <div className="small text-muted">
                    Tax: {(riskGates.buy_tax * 100)?.toFixed(1)}%/{(riskGates.sell_tax * 100)?.toFixed(1)}%
                </div>
            )}
        </div>
    );
}