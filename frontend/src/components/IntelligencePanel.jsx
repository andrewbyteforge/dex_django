import { useState, useEffect } from 'react';
import { Card, Button, Badge, Alert, Table, ProgressBar, Accordion } from 'react-bootstrap';
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

export function IntelligencePanel({ opportunities = [], userBalance = 1000 }) {
    const [signals, setSignals] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [riskMode, setRiskMode] = useState('moderate');
    const [intelligenceStatus, setIntelligenceStatus] = useState(null);

    useEffect(() => {
        loadIntelligenceStatus();
    }, []);

    useEffect(() => {
        if (opportunities.length > 0) {
            analyzeOpportunities();
        }
    }, [opportunities, riskMode]);

    const loadIntelligenceStatus = async () => {
        try {
            const response = await axios.get(`${API_BASE}/api/v1/intelligence/status`);
            setIntelligenceStatus(response.data.intelligence);
        } catch (err) {
            console.error('Failed to load intelligence status:', err);
        }
    };

    const analyzeOpportunities = async () => {
        if (opportunities.length === 0) return;

        setLoading(true);
        setError(null);

        try {
            const response = await axios.post(`${API_BASE}/api/v1/intelligence/analyze`, {
                opportunities: opportunities,
                balance_usd: userBalance,
                risk_mode: riskMode
            });

            setSignals(response.data.signals || []);
        } catch (err) {
            setError(err.response?.data?.error || 'Analysis failed');
            console.error('Intelligence analysis failed:', err);
        } finally {
            setLoading(false);
        }
    };

    const getUrgencyColor = (urgency) => {
        const colors = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'secondary'
        };
        return colors[urgency] || 'secondary';
    };

    const getActionColor = (action) => {
        const colors = {
            'BUY': 'success',
            'STRONG_BUY': 'success',
            'MODERATE_BUY': 'primary',
            'HOLD': 'secondary',
            'AVOID': 'danger'
        };
        return colors[action] || 'secondary';
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div>
                    <strong>🤖 AI Trading Intelligence</strong>
                    {intelligenceStatus && (
                        <Badge bg="success" className="ms-2">
                            {intelligenceStatus.system_health.toUpperCase()}
                        </Badge>
                    )}
                </div>
                <div className="d-flex align-items-center gap-2">
                    <select
                        className="form-select form-select-sm"
                        value={riskMode}
                        onChange={(e) => setRiskMode(e.target.value)}
                        style={{ width: 'auto' }}
                    >
                        <option value="conservative">🛡️ Conservative</option>
                        <option value="moderate">⚖️ Moderate</option>
                        <option value="aggressive">🚀 Aggressive</option>
                    </select>
                    <Button
                        size="sm"
                        variant="outline-primary"
                        onClick={analyzeOpportunities}
                        disabled={loading || opportunities.length === 0}
                    >
                        {loading ? 'Analyzing...' : 'Refresh Analysis'}
                    </Button>
                </div>
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" className="mb-3">
                        <strong>Analysis Error:</strong> {error}
                    </Alert>
                )}

                {loading && (
                    <div className="text-center py-3">
                        <div className="spinner-border text-primary me-2" role="status" />
                        Analyzing opportunities with AI intelligence...
                    </div>
                )}

                {!loading && signals.length === 0 && !error && (
                    <Alert variant="info">
                        No trading signals generated. Try adjusting risk settings or check for new opportunities.
                    </Alert>
                )}

                {signals.length > 0 && (
                    <>
                        <div className="mb-3">
                            <small className="text-muted">
                                Generated {signals.length} AI-powered trading signal{signals.length !== 1 ? 's' : ''}
                                in {riskMode} risk mode
                            </small>
                        </div>

                        <Accordion defaultActiveKey="0">
                            {signals.map((signal, index) => (
                                <Accordion.Item eventKey={index.toString()} key={index}>
                                    <Accordion.Header>
                                        <div className="d-flex justify-content-between align-items-center w-100 pe-3">
                                            <div className="d-flex align-items-center gap-2">
                                                <Badge bg={getActionColor(signal.action)}>
                                                    {signal.action}
                                                </Badge>
                                                <span className="font-monospace small">
                                                    {signal.pair_address?.slice(0, 8)}...
                                                </span>
                                                <Badge bg="secondary">{signal.chain}</Badge>
                                            </div>
                                            <div className="d-flex align-items-center gap-2">
                                                <Badge bg={getUrgencyColor(signal.urgency)}>
                                                    {signal.urgency}
                                                </Badge>
                                                <span className="small text-muted">
                                                    {(signal.confidence * 100).toFixed(0)}% confidence
                                                </span>
                                            </div>
                                        </div>
                                    </Accordion.Header>
                                    <Accordion.Body>
                                        <div className="row">
                                            <div className="col-md-8">
                                                <h6>🧠 AI Reasoning</h6>
                                                <ul className="list-unstyled">
                                                    {signal.reasoning.map((reason, idx) => (
                                                        <li key={idx} className="small mb-1">
                                                            {reason}
                                                        </li>
                                                    ))}
                                                </ul>

                                                {signal.risk_warnings.length > 0 && (
                                                    <>
                                                        <h6 className="text-warning mt-3">⚠️ Risk Warnings</h6>
                                                        <ul className="list-unstyled">
                                                            {signal.risk_warnings.map((warning, idx) => (
                                                                <li key={idx} className="small text-warning mb-1">
                                                                    • {warning}
                                                                </li>
                                                            ))}
                                                        </ul>
                                                    </>
                                                )}
                                            </div>
                                            <div className="col-md-4">
                                                {signal.position_sizing && (
                                                    <>
                                                        <h6>💰 Position Sizing</h6>
                                                        <Table size="sm" className="small">
                                                            <tbody>
                                                                <tr>
                                                                    <td>Recommended:</td>
                                                                    <td className="fw-bold">
                                                                        ${signal.position_sizing.recommended_amount_usd.toFixed(2)}
                                                                    </td>
                                                                </tr>
                                                                <tr>
                                                                    <td>Stop Loss:</td>
                                                                    <td>${signal.position_sizing.stop_loss_price.toFixed(4)}</td>
                                                                </tr>
                                                                <tr>
                                                                    <td>Take Profit:</td>
                                                                    <td>${signal.position_sizing.take_profit_price.toFixed(4)}</td>
                                                                </tr>
                                                                <tr>
                                                                    <td>Max Slippage:</td>
                                                                    <td>{signal.position_sizing.max_acceptable_slippage.toFixed(1)}%</td>
                                                                </tr>
                                                            </tbody>
                                                        </Table>
                                                    </>
                                                )}

                                                <div className="mt-3">
                                                    <h6>⏰ Timing</h6>
                                                    <div className="small">
                                                        <div>Strategy: <Badge bg="info">{signal.strategy_type}</Badge></div>
                                                        <div>Deadline: {new Date(signal.execution_deadline).toLocaleTimeString()}</div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </Accordion.Body>
                                </Accordion.Item>
                            ))}
                        </Accordion>
                    </>
                )}
            </Card.Body>
        </Card>
    );
}