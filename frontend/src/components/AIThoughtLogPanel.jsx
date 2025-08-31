import { useState, useEffect, useRef } from 'react';
import { Card, Badge, Button, Alert, Spinner } from 'react-bootstrap';
import { useWebSocket } from '../hooks/useWebSocket';

const formatCurrency = (value, currency = 'USD') => {
    if (typeof value !== 'number') return value;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
};

const formatPercentage = (value) => {
    if (typeof value !== 'number') return value;
    return `${(value * 100).toFixed(2)}%`;
};

const ThoughtFrame = ({ frame }) => {
    const getActionBadgeVariant = (action) => {
        switch (action) {
            case 'paper_buy': return 'success';
            case 'paper_sell': return 'danger';
            case 'skip': return 'secondary';
            case 'wait': return 'warning';
            default: return 'primary';
        }
    };

    const getConfidenceColor = (confidence) => {
        if (confidence >= 0.8) return 'text-success';
        if (confidence >= 0.6) return 'text-warning';
        return 'text-danger';
    };

    const getRiskColor = (check) => {
        switch (check) {
            case 'pass': return 'text-success';
            case 'warning': return 'text-warning';
            case 'fail': return 'text-danger';
            default: return 'text-muted';
        }
    };

    return (
        <Card className="mb-3 border-start border-primary border-3">
            <Card.Header className="d-flex justify-content-between align-items-center py-2">
                <div className="d-flex align-items-center gap-2">
                    <Badge bg="primary" className="font-monospace">
                        {frame.frame_id}
                    </Badge>
                    <small className="text-muted">
                        {new Date(frame.timestamp).toLocaleTimeString()}
                    </small>
                </div>
                <Badge bg={frame.log_type === 'decision' ? 'info' : 'secondary'}>
                    {frame.log_type.replace('_', ' ').toUpperCase()}
                </Badge>
            </Card.Header>

            <Card.Body className="py-3">
                {/* Opportunity Section */}
                {frame.opportunity && (
                    <div className="mb-3">
                        <h6 className="text-primary mb-2">🎯 Opportunity Detected</h6>
                        <div className="row g-2 small">
                            <div className="col-md-6">
                                <strong>Pair:</strong> {frame.opportunity.symbol}
                            </div>
                            <div className="col-md-6">
                                <strong>DEX:</strong> {frame.opportunity.dex}
                            </div>
                            <div className="col-md-6">
                                <strong>Chain:</strong> {frame.opportunity.chain.toUpperCase()}
                            </div>
                            <div className="col-md-6">
                                <strong>Liquidity:</strong> {formatCurrency(frame.opportunity.liquidity_usd)}
                            </div>
                            {frame.opportunity.trend_score && (
                                <div className="col-md-6">
                                    <strong>Trend Score:</strong>
                                    <span className={frame.opportunity.trend_score > 0.6 ? 'text-success' : 'text-warning'}>
                                        {frame.opportunity.trend_score.toFixed(2)}
                                    </span>
                                </div>
                            )}
                            {frame.opportunity.volume_24h && (
                                <div className="col-md-6">
                                    <strong>24h Volume:</strong> {formatCurrency(frame.opportunity.volume_24h)}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Risk Assessment Section */}
                {frame.risk_assessment && (
                    <div className="mb-3">
                        <h6 className="text-warning mb-2">⚠️ Risk Analysis</h6>
                        <div className="row g-2 small">
                            <div className="col-md-6">
                                <strong>Liquidity Check:</strong>
                                <span className={`ms-1 ${getRiskColor(frame.risk_assessment.liquidity_check)}`}>
                                    {frame.risk_assessment.liquidity_check.toUpperCase()}
                                </span>
                            </div>
                            <div className="col-md-6">
                                <strong>Owner Controls:</strong>
                                <span className={`ms-1 ${getRiskColor(frame.risk_assessment.owner_controls)}`}>
                                    {frame.risk_assessment.owner_controls.toUpperCase()}
                                </span>
                            </div>
                            {frame.risk_assessment.buy_tax_pct !== null && (
                                <div className="col-md-6">
                                    <strong>Buy Tax:</strong> {formatPercentage(frame.risk_assessment.buy_tax_pct)}
                                </div>
                            )}
                            {frame.risk_assessment.sell_tax_pct !== null && (
                                <div className="col-md-6">
                                    <strong>Sell Tax:</strong> {formatPercentage(frame.risk_assessment.sell_tax_pct)}
                                </div>
                            )}
                            <div className="col-md-6">
                                <strong>Blacklist:</strong>
                                <span className={`ms-1 ${getRiskColor(frame.risk_assessment.blacklist_check)}`}>
                                    {frame.risk_assessment.blacklist_check.toUpperCase()}
                                </span>
                            </div>
                            <div className="col-md-6">
                                <strong>Honeypot Risk:</strong>
                                <span className={`ms-1 ${frame.risk_assessment.honeypot_risk === 'low' ? 'text-success' : 'text-danger'}`}>
                                    {frame.risk_assessment.honeypot_risk.toUpperCase()}
                                </span>
                            </div>
                        </div>
                    </div>
                )}

                {/* Pricing Section */}
                {frame.pricing && (
                    <div className="mb-3">
                        <h6 className="text-info mb-2">💰 Pricing Analysis</h6>
                        <div className="row g-2 small">
                            <div className="col-md-6">
                                <strong>Quote In:</strong> {frame.pricing.quote_in}
                            </div>
                            <div className="col-md-6">
                                <strong>Expected Out:</strong> {frame.pricing.expected_out}
                            </div>
                            <div className="col-md-6">
                                <strong>Slippage:</strong> {(frame.pricing.expected_slippage_bps / 100).toFixed(2)}%
                            </div>
                            {frame.pricing.gas_estimate_gwei && (
                                <div className="col-md-6">
                                    <strong>Gas:</strong> {frame.pricing.gas_estimate_gwei.toFixed(1)} gwei
                                </div>
                            )}
                            {frame.pricing.price_impact_bps && (
                                <div className="col-md-6">
                                    <strong>Price Impact:</strong> {(frame.pricing.price_impact_bps / 100).toFixed(2)}%
                                </div>
                            )}
                            {frame.pricing.best_dex && (
                                <div className="col-md-6">
                                    <strong>Best Route:</strong> {frame.pricing.best_dex}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Decision Section */}
                {frame.decision && (
                    <div className="mb-3">
                        <h6 className="text-success mb-2">🤖 AI Decision</h6>
                        <div className="d-flex align-items-center gap-3 mb-2">
                            <Badge bg={getActionBadgeVariant(frame.decision.action)} className="fs-6">
                                {frame.decision.action.replace('_', ' ').toUpperCase()}
                            </Badge>
                            <span className="small">
                                <strong>Confidence:</strong>
                                <span className={`ms-1 ${getConfidenceColor(frame.decision.confidence)}`}>
                                    {formatPercentage(frame.decision.confidence)}
                                </span>
                            </span>
                        </div>

                        <div className="alert alert-light p-2 mb-2">
                            <strong>Rationale:</strong> {frame.decision.rationale}
                        </div>

                        {frame.decision.position_size_pct && (
                            <div className="row g-2 small">
                                <div className="col-md-4">
                                    <strong>Position:</strong> {frame.decision.position_size_pct}%
                                </div>
                                {frame.decision.stop_loss_pct && (
                                    <div className="col-md-4">
                                        <strong>Stop Loss:</strong> {frame.decision.stop_loss_pct}%
                                    </div>
                                )}
                                {frame.decision.take_profit_pct && (
                                    <div className="col-md-4">
                                        <strong>Take Profit:</strong> {frame.decision.take_profit_pct}%
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Execution Section */}
                {frame.execution && (
                    <div className="mb-3">
                        <h6 className="text-dark mb-2">⚡ Execution</h6>
                        <div className="row g-2 small">
                            <div className="col-md-6">
                                <strong>Status:</strong>
                                <Badge bg={frame.execution.status === 'confirmed' ? 'success' : 'warning'} className="ms-1">
                                    {frame.execution.status.toUpperCase()}
                                </Badge>
                            </div>
                            {frame.execution.tx_hash && (
                                <div className="col-md-6">
                                    <strong>Tx Hash:</strong>
                                    <code className="ms-1">{frame.execution.tx_hash.slice(0, 10)}...</code>
                                </div>
                            )}
                            {frame.execution.realized_slippage_bps && (
                                <div className="col-md-6">
                                    <strong>Realized Slippage:</strong> {(frame.execution.realized_slippage_bps / 100).toFixed(2)}%
                                </div>
                            )}
                            {frame.execution.execution_time_ms && (
                                <div className="col-md-6">
                                    <strong>Execution Time:</strong> {frame.execution.execution_time_ms}ms
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Notes */}
                {frame.notes && (
                    <div className="alert alert-info p-2 mb-0">
                        <small><strong>Notes:</strong> {frame.notes}</small>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
};

export function AIThoughtLogPanel() {
    const [thoughtFrames, setThoughtFrames] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState('connecting');
    const [error, setError] = useState(null);
    const scrollRef = useRef(null);

    // WebSocket connection for real-time thought log
    const { lastMessage, connectionState } = useWebSocket('/ws/paper');

    useEffect(() => {
        setConnectionStatus(connectionState);
    }, [connectionState]);

    useEffect(() => {
        if (lastMessage) {
            try {
                const data = JSON.parse(lastMessage.data);

                if (data.type === 'thought_log') {
                    setThoughtFrames(prev => [data.payload, ...prev].slice(0, 50)); // Keep last 50 frames
                    setError(null);

                    // Auto-scroll to top when new frame arrives
                    setTimeout(() => {
                        if (scrollRef.current) {
                            scrollRef.current.scrollTop = 0;
                        }
                    }, 100);
                }

                if (data.type === 'hello') {
                    setError(null);
                }

            } catch (err) {
                console.error('Failed to parse thought log message:', err);
                setError('Failed to parse incoming message');
            }
        }
    }, [lastMessage]);

    const clearThoughts = () => {
        setThoughtFrames([]);
    };

    const getConnectionBadge = () => {
        switch (connectionStatus) {
            case 'open':
                return <Badge bg="success">🟢 Connected</Badge>;
            case 'connecting':
                return <Badge bg="warning">🟡 Connecting...</Badge>;
            case 'closed':
                return <Badge bg="danger">🔴 Disconnected</Badge>;
            default:
                return <Badge bg="secondary">⚪ Unknown</Badge>;
        }
    };

    return (
        <Card className="h-100">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>🧠 AI Thought Log</strong>
                    {getConnectionBadge()}
                </div>
                <div className="d-flex align-items-center gap-2">
                    <Badge bg="info">{thoughtFrames.length} frames</Badge>
                    <Button
                        size="sm"
                        variant="outline-secondary"
                        onClick={clearThoughts}
                        disabled={thoughtFrames.length === 0}
                    >
                        Clear
                    </Button>
                </div>
            </Card.Header>

            <Card.Body className="p-0" style={{ height: '600px', overflowY: 'auto' }} ref={scrollRef}>
                {error && (
                    <Alert variant="danger" className="m-3">
                        <strong>Error:</strong> {error}
                    </Alert>
                )}

                {connectionStatus === 'connecting' && (
                    <div className="text-center p-4">
                        <Spinner animation="border" size="sm" className="me-2" />
                        Connecting to AI thought stream...
                    </div>
                )}

                {connectionStatus === 'closed' && (
                    <Alert variant="warning" className="m-3">
                        <strong>Connection Lost:</strong> Unable to receive real-time AI thoughts.
                        The connection will automatically retry.
                    </Alert>
                )}

                {thoughtFrames.length === 0 && connectionStatus === 'open' && !error && (
                    <div className="text-center text-muted p-4">
                        <div className="mb-2">🤖</div>
                        <div>No AI thoughts yet...</div>
                        <small>AI reasoning will appear here as decisions are made</small>
                        <div className="mt-3">
                            <small className="text-info">
                                💡 Tip: Use the "Test AI Thought Log" button in Paper Trading to see sample reasoning
                            </small>
                        </div>
                    </div>
                )}

                {/* Debug info for development */}
                {process.env.NODE_ENV === 'development' && (
                    <div className="m-3 p-2 bg-light border rounded">
                        <small className="text-muted">
                            <strong>Debug:</strong> WS Status: {connectionStatus} | Frames: {thoughtFrames.length} |
                            Last Message: {lastMessage ? new Date(lastMessage.timeStamp).toLocaleTimeString() : 'None'}
                        </small>
                    </div>
                )}

                <div className="p-3">
                    {thoughtFrames.map((frame, index) => (
                        <ThoughtFrame key={`${frame.frame_id}-${index}`} frame={frame} />
                    ))}
                </div>
            </Card.Body>
        </Card>
    );
}