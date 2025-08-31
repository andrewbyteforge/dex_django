// APP: frontend
// FILE: frontend/src/components/WalletDiscoveryPanel.jsx
import { useState, useEffect } from 'react';
import {
    Card, Row, Col, Button, Form, Badge, Alert, Spinner,
    Table, Modal, ProgressBar, InputGroup, ButtonGroup
} from 'react-bootstrap';

export function WalletDiscoveryPanel() {
    // State management
    const [discoveryStatus, setDiscoveryStatus] = useState(null);
    const [discoveredWallets, setDiscoveredWallets] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Discovery configuration
    const [discoveryConfig, setDiscoveryConfig] = useState({
        chains: ['ethereum', 'bsc'],
        limit: 20,
        min_volume_usd: 50000,
        days_back: 30,
        auto_add_threshold: 80.0
    });

    // Continuous discovery settings
    const [continuousConfig, setContinuousConfig] = useState({
        enabled: false,
        chains: ['ethereum', 'bsc'],
        interval_hours: 24,
        auto_add_enabled: false,
        auto_add_threshold: 85.0
    });

    // Manual wallet analysis
    const [manualAnalysis, setManualAnalysis] = useState({
        address: '',
        chain: 'ethereum',
        days_back: 30
    });

    // UI state
    const [activeTab, setActiveTab] = useState('discover');
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [analysisResult, setAnalysisResult] = useState(null);

    // Load discovery status on component mount
    useEffect(() => {
        loadDiscoveryStatus();
        const interval = setInterval(loadDiscoveryStatus, 30000); // Update every 30s
        return () => clearInterval(interval);
    }, []);

    const loadDiscoveryStatus = async () => {
        try {
            const response = await fetch('/api/v1/discovery/discovery-status');
            const data = await response.json();
            setDiscoveryStatus(data);
        } catch (error) {
            console.error('Failed to load discovery status:', error);
        }
    };

    const handleAutoDiscovery = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/discovery/discover-traders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(discoveryConfig)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Discovery failed');
            }

            setDiscoveredWallets(data.candidates);
            loadDiscoveryStatus(); // Refresh status

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleManualAnalysis = async () => {
        if (!manualAnalysis.address) {
            setError('Please enter a wallet address');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/discovery/analyze-wallet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(manualAnalysis)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Analysis failed');
            }

            setAnalysisResult(data);
            setShowAnalysisModal(true);

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleContinuousDiscovery = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await fetch('/api/v1/discovery/continuous-discovery', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(continuousConfig)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Configuration failed');
            }

            loadDiscoveryStatus(); // Refresh status

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAddWalletToTracking = async (wallet, copyPercentage = 2.0, maxPosition = 500) => {
        try {
            const response = await fetch(
                `/api/v1/discovery/add-discovered-wallet/${wallet.address}/${wallet.chain}?copy_percentage=${copyPercentage}&max_position_usd=${maxPosition}`,
                { method: 'POST' }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to add wallet');
            }

            // Update the wallet's status in the local state
            setDiscoveredWallets(prev =>
                prev.map(w =>
                    w.address === wallet.address ? { ...w, added_to_tracking: true } : w
                )
            );

        } catch (err) {
            setError(err.message);
        }
    };

    const getQualityBadge = (score) => {
        if (score >= 80) return { variant: 'success', text: 'Excellent' };
        if (score >= 65) return { variant: 'primary', text: 'Good' };
        if (score >= 50) return { variant: 'warning', text: 'Average' };
        return { variant: 'danger', text: 'Poor' };
    };

    const getRiskBadge = (score) => {
        if (score < 30) return { variant: 'success', text: 'Low Risk' };
        if (score < 60) return { variant: 'warning', text: 'Moderate Risk' };
        return { variant: 'danger', text: 'High Risk' };
    };

    return (
        <div>
            {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Discovery Status Overview */}
            {discoveryStatus && (
                <Row className="mb-4">
                    <Col>
                        <Card>
                            <Card.Header className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">🔍 Automated Wallet Discovery</h5>
                                <Badge bg={discoveryStatus.discovery_running ? 'success' : 'secondary'}>
                                    {discoveryStatus.discovery_running ? 'Active' : 'Inactive'}
                                </Badge>
                            </Card.Header>
                            <Card.Body>
                                <Row>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-primary">{discoveryStatus.total_discovered}</div>
                                            <div className="text-muted small">Total Discovered</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-success">{discoveryStatus.high_confidence_candidates}</div>
                                            <div className="text-muted small">High Quality</div>
                                        </div>
                                    </Col>
                                    <Col md={6}>
                                        <div className="small">
                                            <strong>By Chain:</strong>
                                            {Object.entries(discoveryStatus.discovered_by_chain).map(([chain, count]) => (
                                                <Badge key={chain} bg="secondary" className="ms-1">
                                                    {chain}: {count}
                                                </Badge>
                                            ))}
                                        </div>
                                    </Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>
            )}

            {/* Main Discovery Interface */}
            <Card>
                <Card.Header>
                    <ButtonGroup className="w-100">
                        <Button
                            variant={activeTab === 'discover' ? 'primary' : 'outline-primary'}
                            onClick={() => setActiveTab('discover')}
                        >
                            🎯 Auto Discovery
                        </Button>
                        <Button
                            variant={activeTab === 'analyze' ? 'primary' : 'outline-primary'}
                            onClick={() => setActiveTab('analyze')}
                        >
                            🔬 Manual Analysis
                        </Button>
                        <Button
                            variant={activeTab === 'continuous' ? 'primary' : 'outline-primary'}
                            onClick={() => setActiveTab('continuous')}
                        >
                            ⚙️ Continuous Mode
                        </Button>
                    </ButtonGroup>
                </Card.Header>

                <Card.Body>
                    {/* Auto Discovery Tab */}
                    {activeTab === 'discover' && (
                        <div>
                            <Row className="mb-3">
                                <Col md={6}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Chains to Search</Form.Label>
                                        {['ethereum', 'bsc', 'base', 'polygon'].map(chain => (
                                            <Form.Check
                                                key={chain}
                                                type="checkbox"
                                                label={chain.charAt(0).toUpperCase() + chain.slice(1)}
                                                checked={discoveryConfig.chains.includes(chain)}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setDiscoveryConfig(prev => ({
                                                            ...prev,
                                                            chains: [...prev.chains, chain]
                                                        }));
                                                    } else {
                                                        setDiscoveryConfig(prev => ({
                                                            ...prev,
                                                            chains: prev.chains.filter(c => c !== chain)
                                                        }));
                                                    }
                                                }}
                                            />
                                        ))}
                                    </Form.Group>
                                </Col>
                                <Col md={6}>
                                    <Row>
                                        <Col md={6}>
                                            <Form.Group className="mb-3">
                                                <Form.Label>Max Results</Form.Label>
                                                <Form.Control
                                                    type="number"
                                                    min="5"
                                                    max="100"
                                                    value={discoveryConfig.limit}
                                                    onChange={(e) => setDiscoveryConfig(prev => ({
                                                        ...prev,
                                                        limit: parseInt(e.target.value)
                                                    }))}
                                                />
                                            </Form.Group>
                                        </Col>
                                        <Col md={6}>
                                            <Form.Group className="mb-3">
                                                <Form.Label>Days Back</Form.Label>
                                                <Form.Control
                                                    type="number"
                                                    min="7"
                                                    max="90"
                                                    value={discoveryConfig.days_back}
                                                    onChange={(e) => setDiscoveryConfig(prev => ({
                                                        ...prev,
                                                        days_back: parseInt(e.target.value)
                                                    }))}
                                                />
                                            </Form.Group>
                                        </Col>
                                    </Row>

                                    <Form.Group className="mb-3">
                                        <Form.Label>Min Volume USD</Form.Label>
                                        <InputGroup>
                                            <InputGroup.Text>$</InputGroup.Text>
                                            <Form.Control
                                                type="number"
                                                min="1000"
                                                value={discoveryConfig.min_volume_usd}
                                                onChange={(e) => setDiscoveryConfig(prev => ({
                                                    ...prev,
                                                    min_volume_usd: parseFloat(e.target.value)
                                                }))}
                                            />
                                        </InputGroup>
                                    </Form.Group>
                                </Col>
                            </Row>

                            <div className="d-grid">
                                <Button
                                    variant="primary"
                                    size="lg"
                                    onClick={handleAutoDiscovery}
                                    disabled={loading || discoveryConfig.chains.length === 0}
                                >
                                    {loading ? (
                                        <>
                                            <Spinner animation="border" size="sm" className="me-2" />
                                            Discovering Traders...
                                        </>
                                    ) : (
                                        '🚀 Start Auto Discovery'
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* Manual Analysis Tab */}
                    {activeTab === 'analyze' && (
                        <div>
                            <Row>
                                <Col md={8}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Wallet Address</Form.Label>
                                        <Form.Control
                                            type="text"
                                            placeholder="0x..."
                                            value={manualAnalysis.address}
                                            onChange={(e) => setManualAnalysis(prev => ({
                                                ...prev,
                                                address: e.target.value
                                            }))}
                                        />
                                    </Form.Group>
                                </Col>
                                <Col md={2}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Chain</Form.Label>
                                        <Form.Select
                                            value={manualAnalysis.chain}
                                            onChange={(e) => setManualAnalysis(prev => ({
                                                ...prev,
                                                chain: e.target.value
                                            }))}
                                        >
                                            <option value="ethereum">Ethereum</option>
                                            <option value="bsc">BSC</option>
                                            <option value="base">Base</option>
                                            <option value="polygon">Polygon</option>
                                        </Form.Select>
                                    </Form.Group>
                                </Col>
                                <Col md={2}>
                                    <Form.Group className="mb-3">
                                        <Form.Label>Days Back</Form.Label>
                                        <Form.Control
                                            type="number"
                                            min="7"
                                            max="90"
                                            value={manualAnalysis.days_back}
                                            onChange={(e) => setManualAnalysis(prev => ({
                                                ...prev,
                                                days_back: parseInt(e.target.value)
                                            }))}
                                        />
                                    </Form.Group>
                                </Col>
                            </Row>

                            <Button
                                variant="primary"
                                onClick={handleManualAnalysis}
                                disabled={loading || !manualAnalysis.address}
                            >
                                {loading ? (
                                    <>
                                        <Spinner animation="border" size="sm" className="me-2" />
                                        Analyzing...
                                    </>
                                ) : (
                                    '🔬 Analyze Wallet'
                                )}
                            </Button>
                        </div>
                    )}

                    {/* Continuous Discovery Tab */}
                    {activeTab === 'continuous' && (
                        <div>
                            <Form.Group className="mb-3">
                                <Form.Check
                                    type="checkbox"
                                    label="Enable Continuous Discovery"
                                    checked={continuousConfig.enabled}
                                    onChange={(e) => setContinuousConfig(prev => ({
                                        ...prev,
                                        enabled: e.target.checked
                                    }))}
                                />
                                <div className="small text-muted mt-1">
                                    Automatically discover new traders periodically
                                </div>
                            </Form.Group>

                            {continuousConfig.enabled && (
                                <>
                                    <Row>
                                        <Col md={6}>
                                            <Form.Group className="mb-3">
                                                <Form.Label>Discovery Interval (hours)</Form.Label>
                                                <Form.Control
                                                    type="number"
                                                    min="6"
                                                    max="168"
                                                    value={continuousConfig.interval_hours}
                                                    onChange={(e) => setContinuousConfig(prev => ({
                                                        ...prev,
                                                        interval_hours: parseInt(e.target.value)
                                                    }))}
                                                />
                                            </Form.Group>
                                        </Col>
                                        <Col md={6}>
                                            <Form.Group className="mb-3">
                                                <Form.Check
                                                    type="checkbox"
                                                    label="Auto-add High Quality Traders"
                                                    checked={continuousConfig.auto_add_enabled}
                                                    onChange={(e) => setContinuousConfig(prev => ({
                                                        ...prev,
                                                        auto_add_enabled: e.target.checked
                                                    }))}
                                                />
                                                {continuousConfig.auto_add_enabled && (
                                                    <Form.Control
                                                        type="number"
                                                        min="75"
                                                        max="95"
                                                        step="0.1"
                                                        value={continuousConfig.auto_add_threshold}
                                                        onChange={(e) => setContinuousConfig(prev => ({
                                                            ...prev,
                                                            auto_add_threshold: parseFloat(e.target.value)
                                                        }))}
                                                        className="mt-2"
                                                        placeholder="Auto-add threshold"
                                                    />
                                                )}
                                            </Form.Group>
                                        </Col>
                                    </Row>
                                </>
                            )}

                            <Button
                                variant={continuousConfig.enabled ? 'success' : 'warning'}
                                onClick={handleContinuousDiscovery}
                                disabled={loading}
                            >
                                {continuousConfig.enabled ? 'Start Continuous Discovery' : 'Stop Continuous Discovery'}
                            </Button>
                        </div>
                    )}
                </Card.Body>
            </Card>

            {/* Discovered Wallets Results */}
            {discoveredWallets.length > 0 && (
                <Card className="mt-4">
                    <Card.Header>
                        <h5 className="mb-0">🎯 Discovered Traders ({discoveredWallets.length})</h5>
                    </Card.Header>
                    <Card.Body>
                        <Table responsive hover>
                            <thead>
                                <tr>
                                    <th>Wallet</th>
                                    <th>Quality Score</th>
                                    <th>Performance</th>
                                    <th>Risk Level</th>
                                    <th>Recommended Copy %</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {discoveredWallets.map((wallet) => {
                                    const qualityBadge = getQualityBadge(wallet.confidence_score);
                                    const riskBadge = getRiskBadge(wallet.risk_score);

                                    return (
                                        <tr key={`${wallet.chain}:${wallet.address}`}>
                                            <td>
                                                <div>
                                                    <div className="font-monospace small">
                                                        {wallet.address.slice(0, 8)}...{wallet.address.slice(-6)}
                                                    </div>
                                                    <Badge bg="secondary" className="small">
                                                        {wallet.chain}
                                                    </Badge>
                                                </div>
                                            </td>
                                            <td>
                                                <div className="d-flex align-items-center">
                                                    <ProgressBar
                                                        now={wallet.confidence_score}
                                                        variant={qualityBadge.variant}
                                                        style={{ width: '60px', height: '8px' }}
                                                        className="me-2"
                                                    />
                                                    <Badge bg={qualityBadge.variant}>
                                                        {wallet.confidence_score.toFixed(1)}
                                                    </Badge>
                                                </div>
                                                <div className="small text-muted">
                                                    {qualityBadge.text}
                                                </div>
                                            </td>
                                            <td>
                                                <div className="small">
                                                    <div>Trades: {wallet.total_trades}</div>
                                                    <div>Win Rate: {wallet.win_rate.toFixed(1)}%</div>
                                                    <div className={parseFloat(wallet.total_pnl_usd) >= 0 ? 'text-success' : 'text-danger'}>
                                                        P&L: ${parseFloat(wallet.total_pnl_usd).toFixed(2)}
                                                    </div>
                                                </div>
                                            </td>
                                            <td>
                                                <Badge bg={riskBadge.variant}>
                                                    {riskBadge.text}
                                                </Badge>
                                                <div className="small text-muted">
                                                    Score: {wallet.risk_score.toFixed(1)}
                                                </div>
                                            </td>
                                            <td>
                                                <div className="fw-bold">
                                                    {wallet.recommended_copy_percentage.toFixed(1)}%
                                                </div>
                                                <div className="small text-muted">
                                                    Max ${wallet.avg_trade_size_usd.toFixed(0)}
                                                </div>
                                            </td>
                                            <td>
                                                {wallet.added_to_tracking ? (
                                                    <Badge bg="success">Added</Badge>
                                                ) : (
                                                    <Button
                                                        size="sm"
                                                        variant="primary"
                                                        onClick={() => handleAddWalletToTracking(
                                                            wallet,
                                                            wallet.recommended_copy_percentage,
                                                            Math.min(1000, wallet.avg_trade_size_usd * 2)
                                                        )}
                                                    >
                                                        Add to Copy Trading
                                                    </Button>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </Table>
                    </Card.Body>
                </Card>
            )}

            {/* Manual Analysis Results Modal */}
            <Modal show={showAnalysisModal} onHide={() => setShowAnalysisModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>Wallet Analysis Results</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {analysisResult && (
                        <div>
                            {analysisResult.status === 'not_qualified' ? (
                                <Alert variant="warning">
                                    <Alert.Heading>Wallet Not Qualified</Alert.Heading>
                                    <p>This wallet does not meet the minimum criteria for copy trading:</p>
                                    <ul>
                                        {analysisResult.reasons.map((reason, index) => (
                                            <li key={index}>{reason}</li>
                                        ))}
                                    </ul>
                                </Alert>
                            ) : (
                                <div>
                                    <Row className="mb-3">
                                        <Col>
                                            <h5>
                                                Recommendation:
                                                <Badge
                                                    bg={
                                                        analysisResult.recommendation === 'strongly_recommended' ? 'success' :
                                                            analysisResult.recommendation === 'recommended' ? 'primary' :
                                                                analysisResult.recommendation === 'moderate' ? 'warning' : 'danger'
                                                    }
                                                    className="ms-2"
                                                >
                                                    {analysisResult.recommendation.replace('_', ' ').toUpperCase()}
                                                </Badge>
                                            </h5>
                                        </Col>
                                    </Row>

                                    <Row className="mb-3">
                                        <Col md={6}>
                                            <Card>
                                                <Card.Header>Performance Metrics</Card.Header>
                                                <Card.Body className="small">
                                                    <p><strong>Total Trades:</strong> {analysisResult.candidate.total_trades}</p>
                                                    <p><strong>Win Rate:</strong> {analysisResult.candidate.win_rate.toFixed(1)}%</p>
                                                    <p><strong>Total Volume:</strong> ${parseFloat(analysisResult.candidate.total_volume_usd).toLocaleString()}</p>
                                                    <p><strong>Total P&L:</strong>
                                                        <span className={parseFloat(analysisResult.candidate.total_pnl_usd) >= 0 ? 'text-success' : 'text-danger'}>
                                                            ${parseFloat(analysisResult.candidate.total_pnl_usd).toFixed(2)}
                                                        </span>
                                                    </p>
                                                    <p><strong>Confidence Score:</strong> {analysisResult.candidate.confidence_score.toFixed(1)}/100</p>
                                                </Card.Body>
                                            </Card>
                                        </Col>
                                        <Col md={6}>
                                            <Card>
                                                <Card.Header>Risk Analysis</Card.Header>
                                                <Card.Body className="small">
                                                    <p><strong>Risk Level:</strong>
                                                        <Badge bg={
                                                            analysisResult.analysis_summary.risk_level === 'low' ? 'success' :
                                                                analysisResult.analysis_summary.risk_level === 'moderate' ? 'warning' : 'danger'
                                                        } className="ms-1">
                                                            {analysisResult.analysis_summary.risk_level.toUpperCase()}
                                                        </Badge>
                                                    </p>
                                                    <p><strong>Max Drawdown:</strong> {analysisResult.candidate.max_drawdown_pct.toFixed(1)}%</p>
                                                    <p><strong>Risk Score:</strong> {analysisResult.candidate.risk_score.toFixed(1)}/100</p>
                                                    <p><strong>Trading Style:</strong> {analysisResult.analysis_summary.trading_style.replace('_', ' ')}</p>
                                                    <p><strong>Recommended Copy:</strong> {analysisResult.candidate.recommended_copy_percentage.toFixed(1)}%</p>
                                                </Card.Body>
                                            </Card>
                                        </Col>
                                    </Row>

                                    <Row className="mb-3">
                                        <Col md={6}>
                                            <h6 className="text-success">Strengths:</h6>
                                            <ul className="small">
                                                {analysisResult.analysis_summary.key_strengths.map((strength, index) => (
                                                    <li key={index}>{strength}</li>
                                                ))}
                                            </ul>
                                        </Col>
                                        <Col md={6}>
                                            <h6 className="text-warning">Risks:</h6>
                                            <ul className="small">
                                                {analysisResult.analysis_summary.key_risks.map((risk, index) => (
                                                    <li key={index}>{risk}</li>
                                                ))}
                                            </ul>
                                        </Col>
                                    </Row>

                                    {analysisResult.recommendation !== 'not_recommended' && (
                                        <div className="d-grid">
                                            <Button
                                                variant="primary"
                                                onClick={() => {
                                                    handleAddWalletToTracking(
                                                        {
                                                            address: analysisResult.candidate.address,
                                                            chain: analysisResult.candidate.chain
                                                        },
                                                        analysisResult.candidate.recommended_copy_percentage,
                                                        500
                                                    );
                                                    setShowAnalysisModal(false);
                                                }}
                                            >
                                                Add to Copy Trading
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowAnalysisModal(false)}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}