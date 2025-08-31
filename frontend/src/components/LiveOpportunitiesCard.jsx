import { useState, useEffect, useRef } from 'react';
import { Card, Button, Table, Badge, Alert, Spinner, Modal } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi';

export function LiveOpportunitiesCard() {
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [selectedOpportunity, setSelectedOpportunity] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState(null);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const refreshIntervalRef = useRef(null);

    const {
        data: opportunitiesData,
        loading,
        error,
        refresh
    } = useDjangoData('/api/v1/opportunities/live', { opportunities: [], count: 0 });

    const {
        data: stats,
        refresh: refreshStats
    } = useDjangoData('/api/v1/opportunities/stats', {});

    const opportunities = opportunitiesData?.opportunities || [];

    // Auto-refresh mechanism
    useEffect(() => {
        if (autoRefresh) {
            refreshIntervalRef.current = setInterval(() => {
                console.log('Auto-refreshing opportunities...');
                refresh();
                refreshStats();
                setLastUpdate(new Date());
            }, 15000);
        } else {
            if (refreshIntervalRef.current) {
                clearInterval(refreshIntervalRef.current);
            }
        }

        return () => {
            if (refreshIntervalRef.current) {
                clearInterval(refreshIntervalRef.current);
            }
        };
    }, [autoRefresh, refresh, refreshStats]);

    const handleManualRefresh = async () => {
        setLastUpdate(new Date());
        await Promise.all([refresh(), refreshStats()]);
    };

    const analyzeOpportunity = async (opportunity) => {
        console.log('Analyze button clicked for:', opportunity.pair_address);

        // Set state immediately to show modal
        setSelectedOpportunity(opportunity);
        setAnalyzing(true);
        setAnalysisResult(null);
        setShowAnalysisModal(true);

        console.log('Modal should be visible now, showAnalysisModal:', true);

        try {
            console.log('Making analysis request with opportunity:', opportunity);

            // Ensure all required fields are present
            const requestData = {
                pair_address: opportunity.pair_address || '',
                chain: opportunity.chain || 'ethereum',
                dex: opportunity.dex || 'unknown',
                token0_symbol: opportunity.token0_symbol || 'TOKEN0',
                token1_symbol: opportunity.token1_symbol || 'TOKEN1',
                estimated_liquidity_usd: opportunity.estimated_liquidity_usd || 0,
                timestamp: opportunity.timestamp || new Date().toISOString(),
                source: opportunity.source || 'unknown',
                opportunity_score: opportunity.opportunity_score || 0,
                trade_amount_eth: 0.1
            };

            console.log('Sending request data:', requestData);

            const response = await djangoApi.post('/api/v1/opportunities/analyze', requestData);

            console.log('Analysis response:', response.data);
            setAnalysisResult(response.data.analysis || response.data);
        } catch (err) {
            console.error('Analysis failed:', err);
            console.error('Error response:', err.response?.data);
            setAnalysisResult({
                error: err.response?.data?.error || err.message || 'Analysis failed'
            });
        } finally {
            setAnalyzing(false);
        }
    };

    const closeModal = () => {
        console.log('Closing modal');
        setShowAnalysisModal(false);
        setSelectedOpportunity(null);
        setAnalysisResult(null);
        setAnalyzing(false);
    };

    const formatTimeAgo = (timestamp) => {
        if (!timestamp) return 'Never';
        try {
            const now = new Date();
            const then = new Date(timestamp);
            const diffMs = now - then;
            const diffSeconds = Math.floor(diffMs / 1000);

            if (diffSeconds < 60) return `${diffSeconds}s ago`;
            if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
            return `${Math.floor(diffSeconds / 3600)}h ago`;
        } catch (e) {
            return 'Unknown';
        }
    };

    // Debug: Log modal state changes
    useEffect(() => {
        console.log('Modal state changed:', {
            showAnalysisModal,
            selectedOpportunity: selectedOpportunity?.pair_address,
            analyzing,
            hasResult: !!analysisResult
        });
    }, [showAnalysisModal, selectedOpportunity, analyzing, analysisResult]);

    return (
        <>
            <Card className="mb-4">
                <Card.Header className="d-flex justify-content-between align-items-center">
                    <div className="d-flex align-items-center gap-2">
                        <strong>Live Opportunities</strong>
                        <Badge bg="info">
                            {opportunities.length || 0} found
                        </Badge>
                    </div>
                    <div className="d-flex align-items-center gap-2">
                        <small className="text-muted">
                            {lastUpdate ? `Updated ${formatTimeAgo(lastUpdate)}` : 'Loading...'}
                        </small>
                        <div className="form-check form-switch">
                            <input
                                className="form-check-input"
                                type="checkbox"
                                id="autoRefresh"
                                checked={autoRefresh}
                                onChange={(e) => setAutoRefresh(e.target.checked)}
                            />
                            <label className="form-check-label small" htmlFor="autoRefresh">
                                Auto-refresh
                            </label>
                        </div>
                        <Button
                            size="sm"
                            variant="outline-primary"
                            onClick={handleManualRefresh}
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <span className="spinner-border spinner-border-sm me-1" />
                                    Loading...
                                </>
                            ) : (
                                'Refresh'
                            )}
                        </Button>
                    </div>
                </Card.Header>

                <Card.Body>
                    {error && (
                        <Alert variant="danger" className="mb-3">
                            <strong>Error:</strong> {error.message || error}
                            <div className="mt-1">
                                <Button size="sm" variant="outline-danger" onClick={handleManualRefresh}>
                                    Retry
                                </Button>
                            </div>
                        </Alert>
                    )}

                    {/* Stats Summary */}
                    {stats && (
                        <div className="row mb-3">
                            <div className="col-md-3 text-center">
                                <div className="fw-bold text-success">Total</div>
                                <div className="fs-5">{stats.total_opportunities || 0}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">High Liquidity</div>
                                <div className="fs-5">{stats.high_liquidity_opportunities || 0}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Chains</div>
                                <div className="fs-5">{stats.chains_active || 0}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Avg Liquidity</div>
                                <div className="fs-6">${(stats.average_liquidity_usd || 0).toLocaleString()}</div>
                            </div>
                        </div>
                    )}

                    {/* Loading State */}
                    {loading && opportunities.length === 0 && (
                        <div className="text-center py-4">
                            <Spinner animation="border" />
                            <div className="mt-2">Loading opportunities...</div>
                        </div>
                    )}

                    {/* Opportunities Table */}
                    {opportunities.length > 0 ? (
                        <div className="table-responsive">
                            <Table striped hover size="sm">
                                <thead>
                                    <tr>
                                        <th>Token Pair</th>
                                        <th>Chain</th>
                                        <th>DEX</th>
                                        <th>Liquidity</th>
                                        <th>Source</th>
                                        <th>Score</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {opportunities.slice(0, 10).map((opp, index) => (
                                        <tr key={`${opp.pair_address}-${index}`}>
                                            <td>
                                                <strong>{opp.token0_symbol || 'TOKEN'}</strong>
                                                <span className="text-muted">/</span>
                                                <span>{opp.token1_symbol || 'WETH'}</span>
                                                <div className="small text-muted font-monospace">
                                                    {opp.pair_address?.slice(0, 8)}...
                                                </div>
                                            </td>
                                            <td>
                                                <Badge bg="secondary">{opp.chain || 'unknown'}</Badge>
                                            </td>
                                            <td>
                                                <Badge bg="info">{opp.dex || 'unknown'}</Badge>
                                            </td>
                                            <td>
                                                <span className={
                                                    (opp.estimated_liquidity_usd || 0) >= 100000 ? 'text-success fw-bold' :
                                                        (opp.estimated_liquidity_usd || 0) >= 50000 ? 'text-warning' :
                                                            'text-danger'
                                                }>
                                                    ${(opp.estimated_liquidity_usd || 0).toLocaleString()}
                                                </span>
                                            </td>
                                            <td>
                                                <Badge
                                                    bg={opp.source === 'dexscreener' ? 'success' :
                                                        opp.source === 'mock' ? 'warning' : 'secondary'}
                                                >
                                                    {opp.source || 'unknown'}
                                                </Badge>
                                            </td>
                                            <td>
                                                <Badge bg={
                                                    (opp.opportunity_score || 0) >= 8 ? 'success' :
                                                        (opp.opportunity_score || 0) >= 6 ? 'warning' : 'secondary'
                                                }>
                                                    {opp.opportunity_score ? opp.opportunity_score.toFixed(1) : 'N/A'}
                                                </Badge>
                                            </td>
                                            <td>
                                                <Button
                                                    size="sm"
                                                    variant="outline-primary"
                                                    onClick={() => analyzeOpportunity(opp)}
                                                    disabled={analyzing}
                                                >
                                                    {analyzing ? 'Analyzing...' : 'Analyze'}
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </Table>
                        </div>
                    ) : (
                        !loading && (
                            <Alert variant="info">
                                No opportunities found. The system is scanning for new trading opportunities...
                            </Alert>
                        )
                    )}
                </Card.Body>
            </Card>

            {/* Analysis Modal */}
            <Modal
                show={showAnalysisModal}
                onHide={closeModal}
                size="lg"
                backdrop="static"
                keyboard={false}
            >
                <Modal.Header closeButton>
                    <Modal.Title>
                        AI Analysis - {selectedOpportunity ?
                            `${selectedOpportunity.token0_symbol}/${selectedOpportunity.token1_symbol}` :
                            'Loading...'}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                        {analyzing ? (
                            <div className="text-center py-4">
                                <Spinner animation="border" />
                                <div className="mt-2">Analyzing with AI intelligence...</div>
                            </div>
                        ) : analysisResult ? (
                            analysisResult.error ? (
                                <Alert variant="danger">
                                    <strong>Analysis Error:</strong> {analysisResult.error}
                                </Alert>
                            ) : (
                                <div>
                                    {/* Recommendation Summary */}
                                    {analysisResult.recommendation && (
                                        <Alert variant={
                                            analysisResult.recommendation.action === 'ENTER' ? 'success' :
                                                analysisResult.recommendation.action === 'HOLD' ? 'warning' : 'danger'
                                        } className="mb-3">
                                            <div className="d-flex justify-content-between align-items-center mb-2">
                                                <strong>Recommendation: {analysisResult.recommendation.action}</strong>
                                                <Badge bg="secondary">{(analysisResult.recommendation.confidence * 100).toFixed(0)}% confidence</Badge>
                                            </div>
                                            <small>{analysisResult.recommendation.rationale}</small>
                                        </Alert>
                                    )}

                                    {/* Key Metrics Row */}
                                    <div className="row mb-3">
                                        <div className="col-md-3 text-center">
                                            <div className="fw-bold">Risk Score</div>
                                            <Badge bg={
                                                (analysisResult.risk_assessment?.risk_score || 0) <= 3 ? 'success' :
                                                    (analysisResult.risk_assessment?.risk_score || 0) <= 6 ? 'warning' : 'danger'
                                            }>
                                                {analysisResult.risk_assessment?.risk_score || 'N/A'}/10
                                            </Badge>
                                        </div>
                                        <div className="col-md-3 text-center">
                                            <div className="fw-bold">Momentum</div>
                                            <div className="fs-5">{analysisResult.trading_signals?.momentum_score || 'N/A'}/10</div>
                                        </div>
                                        <div className="col-md-3 text-center">
                                            <div className="fw-bold">Technical Score</div>
                                            <div className="fs-5">{analysisResult.trading_signals?.technical_score || 'N/A'}/10</div>
                                        </div>
                                        <div className="col-md-3 text-center">
                                            <div className="fw-bold">Position Size</div>
                                            <Badge bg="info">{analysisResult.recommendation?.position_size || 'N/A'}</Badge>
                                        </div>
                                    </div>

                                    {/* Trading Strategy */}
                                    {analysisResult.recommendation && (
                                        <div className="mb-3">
                                            <h6>Trading Strategy</h6>
                                            <div className="row small">
                                                <div className="col-md-6">
                                                    <div>Entry: <Badge bg="primary">{analysisResult.recommendation.entry_strategy}</Badge></div>
                                                    <div>Stop Loss: <span className="text-danger">{(analysisResult.recommendation.stop_loss * 100 - 100).toFixed(1)}%</span></div>
                                                </div>
                                                <div className="col-md-6">
                                                    <div>Take Profit 1: <span className="text-success">+{(analysisResult.recommendation.take_profit_1 * 100 - 100).toFixed(1)}%</span></div>
                                                    <div>Take Profit 2: <span className="text-success">+{(analysisResult.recommendation.take_profit_2 * 100 - 100).toFixed(1)}%</span></div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Risk Assessment */}
                                    {analysisResult.risk_assessment && (
                                        <div className="mb-3">
                                            <h6>Risk Assessment</h6>
                                            <div className="row small">
                                                <div className="col-md-6">
                                                    <div>Contract: <Badge bg={analysisResult.risk_assessment.contract_verification === 'verified' ? 'success' : 'danger'}>
                                                        {analysisResult.risk_assessment.contract_verification}
                                                    </Badge></div>
                                                    <div>Honeypot Risk: <Badge bg={
                                                        analysisResult.risk_assessment.honeypot_risk === 'low' ? 'success' :
                                                            analysisResult.risk_assessment.honeypot_risk === 'medium' ? 'warning' : 'danger'
                                                    }>
                                                        {analysisResult.risk_assessment.honeypot_risk}
                                                    </Badge></div>
                                                    <div>Ownership: <Badge bg={analysisResult.risk_assessment.ownership_risk === 'renounced' ? 'success' : 'warning'}>
                                                        {analysisResult.risk_assessment.ownership_risk}
                                                    </Badge></div>
                                                </div>
                                                <div className="col-md-6">
                                                    <div>Buy Tax: {analysisResult.risk_assessment.buy_tax}%</div>
                                                    <div>Sell Tax: {analysisResult.risk_assessment.sell_tax}%</div>
                                                    <div>Liquidity Locked: {analysisResult.risk_assessment.liquidity_locked ? 'Yes' : 'No'}
                                                        {analysisResult.risk_assessment.lock_duration_days && ` (${analysisResult.risk_assessment.lock_duration_days} days)`}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Liquidity Analysis */}
                                    {analysisResult.liquidity_analysis && (
                                        <div className="mb-3">
                                            <h6>Liquidity Analysis</h6>
                                            <div className="row small">
                                                <div className="col-md-6">
                                                    <div>Current Liquidity: ${analysisResult.liquidity_analysis.current_liquidity_usd?.toLocaleString()}</div>
                                                    <div>24h Volume: ${analysisResult.liquidity_analysis.volume_24h_usd?.toLocaleString()}</div>
                                                    <div>Volume/Liquidity: {(analysisResult.liquidity_analysis.volume_to_liquidity_ratio * 100).toFixed(1)}%</div>
                                                </div>
                                                <div className="col-md-6">
                                                    <div>Depth 5%: ${analysisResult.liquidity_analysis.liquidity_depth_5pct?.toLocaleString()}</div>
                                                    <div>Depth 10%: ${analysisResult.liquidity_analysis.liquidity_depth_10pct?.toLocaleString()}</div>
                                                    <div>Stability: <Badge bg={
                                                        analysisResult.liquidity_analysis.liquidity_stability_24h === 'stable' ? 'success' : 'warning'
                                                    }>
                                                        {analysisResult.liquidity_analysis.liquidity_stability_24h}
                                                    </Badge></div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Token Information */}
                                    {analysisResult.token_analysis && (
                                        <div className="mb-3">
                                            <h6>Token Information</h6>
                                            {analysisResult.token_analysis.token0 && (
                                                <div className="small">
                                                    <div className="fw-bold">{analysisResult.token_analysis.token0.symbol}</div>
                                                    <div className="row">
                                                        <div className="col-md-6">
                                                            <div>Total Supply: {(analysisResult.token_analysis.token0.total_supply / 1000000).toFixed(1)}M</div>
                                                            <div>Circulating: {(analysisResult.token_analysis.token0.circulating_supply / 1000000).toFixed(1)}M</div>
                                                        </div>
                                                        <div className="col-md-6">
                                                            <div>Holders: {analysisResult.token_analysis.token0.holder_count?.toLocaleString()}</div>
                                                            <div>Top 10 Hold: {analysisResult.token_analysis.token0.top_10_holder_percentage}%</div>
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Trading Signals */}
                                    {analysisResult.trading_signals && (
                                        <div className="mb-3">
                                            <h6>Market Signals</h6>
                                            <div className="row small">
                                                <div className="col-md-6">
                                                    <div>Trend: <Badge bg={
                                                        analysisResult.trading_signals.trend_direction === 'bullish' ? 'success' :
                                                            analysisResult.trading_signals.trend_direction === 'bearish' ? 'danger' : 'secondary'
                                                    }>
                                                        {analysisResult.trading_signals.trend_direction}
                                                    </Badge></div>
                                                    <div>Volume Trend: <Badge bg={
                                                        analysisResult.trading_signals.volume_trend === 'increasing' ? 'success' : 'warning'
                                                    }>
                                                        {analysisResult.trading_signals.volume_trend}
                                                    </Badge></div>
                                                </div>
                                                <div className="col-md-6">
                                                    <div>Social Sentiment: <Badge bg="info">{analysisResult.trading_signals.social_sentiment}</Badge></div>
                                                    <div>Whale Activity: <Badge bg={
                                                        analysisResult.trading_signals.whale_activity === 'accumulating' ? 'success' : 'secondary'
                                                    }>
                                                        {analysisResult.trading_signals.whale_activity}
                                                    </Badge></div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Execution Parameters */}
                                    {analysisResult.recommendation && (
                                        <div className="mb-3">
                                            <h6>Execution Settings</h6>
                                            <div className="small">
                                                <div>Max Slippage: {(analysisResult.recommendation.max_slippage * 100).toFixed(1)}%</div>
                                                <div>Gas Priority: <Badge bg="secondary">{analysisResult.recommendation.gas_priority}</Badge></div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Analysis Metadata */}
                                    {analysisResult.pair_info && (
                                        <div className="text-muted small">
                                            <div>Analyzed: {new Date(analysisResult.pair_info.analyzed_at).toLocaleString()}</div>
                                            <div>Chain: {analysisResult.pair_info.chain} | DEX: {analysisResult.pair_info.dex}</div>
                                        </div>
                                    )}
                                </div>
                            )
                        ) : (
                            <Alert variant="warning">
                                No analysis data available
                            </Alert>
                        )}
                    </div>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={closeModal}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}