import { useState, useEffect, useRef, useMemo } from 'react';
import { Card, Button, Table, Badge, Alert, Spinner, Modal, Form, Row, Col, ButtonGroup, Pagination } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi';

export function LiveOpportunitiesCard() {
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [selectedOpportunity, setSelectedOpportunity] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState(null);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const refreshIntervalRef = useRef(null);

    // Filter states
    const [filters, setFilters] = useState({
        minScore: 0,
        maxScore: 30,
        minLiquidity: 0,
        maxLiquidity: 1000000,
        selectedChains: new Set(['ethereum', 'bsc', 'base', 'polygon', 'solana']),
        selectedSources: new Set(['dexscreener', 'coingecko_trending', 'jupiter'])
    });

    // Pagination states
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(20);

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

    const rawOpportunities = opportunitiesData?.opportunities || [];

    // Filter and sort opportunities (latest first, then by score)
    const filteredOpportunities = useMemo(() => {
        return rawOpportunities.filter(opp => {
            const score = opp.opportunity_score || 0;
            const liquidity = opp.estimated_liquidity_usd || 0;
            const chain = opp.chain || 'unknown';
            const source = opp.source || 'unknown';

            return (
                score >= filters.minScore &&
                score <= filters.maxScore &&
                liquidity >= filters.minLiquidity &&
                liquidity <= filters.maxLiquidity &&
                filters.selectedChains.has(chain) &&
                filters.selectedSources.has(source)
            );
        }).sort((a, b) => {
            // Sort by timestamp first (latest first), then by score (highest first)
            const timeA = new Date(a.timestamp || 0).getTime();
            const timeB = new Date(b.timestamp || 0).getTime();
            if (timeB !== timeA) {
                return timeB - timeA; // Latest first
            }
            return (b.opportunity_score || 0) - (a.opportunity_score || 0); // Then by score
        });
    }, [rawOpportunities, filters]);

    // Paginate opportunities
    const totalPages = Math.ceil(filteredOpportunities.length / itemsPerPage);
    const paginatedOpportunities = useMemo(() => {
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        return filteredOpportunities.slice(startIndex, endIndex);
    }, [filteredOpportunities, currentPage, itemsPerPage]);

    const opportunities = paginatedOpportunities;

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

    const handleFilterChange = (filterType, value) => {
        setFilters(prev => ({
            ...prev,
            [filterType]: value
        }));
    };

    const handleChainToggle = (chain) => {
        setFilters(prev => {
            const newChains = new Set(prev.selectedChains);
            if (newChains.has(chain)) {
                newChains.delete(chain);
            } else {
                newChains.add(chain);
            }
            return { ...prev, selectedChains: newChains };
        });
    };

    const handleSourceToggle = (source) => {
        setFilters(prev => {
            const newSources = new Set(prev.selectedSources);
            if (newSources.has(source)) {
                newSources.delete(source);
            } else {
                newSources.add(source);
            }
            return { ...prev, selectedSources: newSources };
        });
    };

    const resetFilters = () => {
        setFilters({
            minScore: 0,
            maxScore: 30,
            minLiquidity: 0,
            maxLiquidity: 1000000,
            selectedChains: new Set(['ethereum', 'bsc', 'base', 'polygon', 'solana']),
            selectedSources: new Set(['dexscreener', 'coingecko_trending', 'jupiter'])
        });
        setCurrentPage(1); // Reset to first page when filters change
    };

    // Reset to page 1 when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [filters]);

    const handlePageChange = (page) => {
        setCurrentPage(Math.max(1, Math.min(page, totalPages)));
    };

    const handleItemsPerPageChange = (newItemsPerPage) => {
        setItemsPerPage(newItemsPerPage);
        setCurrentPage(1);
    };

    const analyzeOpportunity = async (opportunity) => {
        console.log('Analyze button clicked for:', opportunity.pair_address);
        setSelectedOpportunity(opportunity);
        setAnalyzing(true);
        setAnalysisResult(null);
        setShowAnalysisModal(true);

        try {
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

            const response = await djangoApi.post('/api/v1/opportunities/analyze', requestData);
            setAnalysisResult(response.data.analysis || response.data);
        } catch (err) {
            console.error('Analysis failed:', err);
            setAnalysisResult({
                error: err.response?.data?.error || err.message || 'Analysis failed'
            });
        } finally {
            setAnalyzing(false);
        }
    };

    const closeModal = () => {
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

    return (
        <>
            <Card className="mb-4">
                <Card.Header className="d-flex justify-content-between align-items-center">
                    <div className="d-flex align-items-center gap-2">
                        <strong>Live Opportunities</strong>
                        <Badge bg="info">
                            {opportunities.length} showing
                        </Badge>
                        {opportunities.length !== filteredOpportunities.length && (
                            <Badge bg="secondary">
                                of {filteredOpportunities.length} filtered
                            </Badge>
                        )}
                        {filteredOpportunities.length !== rawOpportunities.length && (
                            <Badge bg="outline-secondary">
                                ({rawOpportunities.length} total)
                            </Badge>
                        )}
                    </div>
                    <div className="d-flex align-items-center gap-2">
                        <small className="text-muted">
                            {lastUpdate ? formatTimeAgo(lastUpdate) : 'Never updated'}
                        </small>
                        <Form.Check
                            type="switch"
                            id="auto-refresh"
                            label="Auto"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                        />
                        <Button
                            variant="outline-primary"
                            size="sm"
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

                    {/* Filter Controls */}
                    <Card className="mb-3 bg-light">
                        <Card.Body className="py-2">
                            <div className="d-flex justify-content-between align-items-center mb-2">
                                <small className="fw-bold text-muted">FILTERS</small>
                                <Button size="sm" variant="outline-secondary" onClick={resetFilters}>
                                    Reset All
                                </Button>
                            </div>

                            <Row>
                                {/* Score Range Slider */}
                                <Col md={3}>
                                    <Form.Group>
                                        <Form.Label className="small mb-1">
                                            Score: {filters.minScore} - {filters.maxScore}
                                        </Form.Label>
                                        <div className="d-flex gap-2">
                                            <Form.Range
                                                min={0}
                                                max={30}
                                                value={filters.minScore}
                                                onChange={(e) => handleFilterChange('minScore', Number(e.target.value))}
                                                className="flex-grow-1"
                                            />
                                            <Form.Range
                                                min={0}
                                                max={30}
                                                value={filters.maxScore}
                                                onChange={(e) => handleFilterChange('maxScore', Number(e.target.value))}
                                                className="flex-grow-1"
                                            />
                                        </div>
                                    </Form.Group>
                                </Col>

                                {/* Liquidity Range Slider */}
                                <Col md={3}>
                                    <Form.Group>
                                        <Form.Label className="small mb-1">
                                            Liquidity: ${(filters.minLiquidity / 1000).toFixed(0)}K - ${(filters.maxLiquidity / 1000).toFixed(0)}K
                                        </Form.Label>
                                        <div className="d-flex gap-2">
                                            <Form.Range
                                                min={0}
                                                max={1000000}
                                                step={5000}
                                                value={filters.minLiquidity}
                                                onChange={(e) => handleFilterChange('minLiquidity', Number(e.target.value))}
                                                className="flex-grow-1"
                                            />
                                            <Form.Range
                                                min={0}
                                                max={1000000}
                                                step={5000}
                                                value={filters.maxLiquidity}
                                                onChange={(e) => handleFilterChange('maxLiquidity', Number(e.target.value))}
                                                className="flex-grow-1"
                                            />
                                        </div>
                                    </Form.Group>
                                </Col>

                                {/* Chain Filter */}
                                <Col md={3}>
                                    <Form.Label className="small mb-1">Chains</Form.Label>
                                    <div className="d-flex flex-wrap gap-1">
                                        {['ethereum', 'bsc', 'base', 'polygon', 'solana'].map(chain => (
                                            <Badge
                                                key={chain}
                                                bg={filters.selectedChains.has(chain) ? 'primary' : 'outline-secondary'}
                                                style={{ cursor: 'pointer' }}
                                                onClick={() => handleChainToggle(chain)}
                                            >
                                                {chain.toUpperCase()}
                                            </Badge>
                                        ))}
                                    </div>
                                </Col>

                                {/* Source Filter */}
                                <Col md={3}>
                                    <Form.Label className="small mb-1">Sources</Form.Label>
                                    <div className="d-flex flex-wrap gap-1">
                                        {['dexscreener', 'coingecko_trending', 'jupiter'].map(source => (
                                            <Badge
                                                key={source}
                                                bg={filters.selectedSources.has(source) ? 'success' : 'outline-secondary'}
                                                style={{ cursor: 'pointer' }}
                                                onClick={() => handleSourceToggle(source)}
                                            >
                                                {source === 'dexscreener' ? 'DEX' :
                                                    source === 'coingecko_trending' ? 'CG' : 'JUP'}
                                            </Badge>
                                        ))}
                                    </div>
                                </Col>
                            </Row>
                        </Card.Body>
                    </Card>

                    {/* Stats Summary */}
                    {stats && (
                        <div className="row mb-3">
                            <div className="col-md-3 text-center">
                                <div className="fw-bold text-success">Showing</div>
                                <div className="fs-5">{opportunities.length}</div>
                                <small className="text-muted">of {filteredOpportunities.length} filtered</small>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">High Liquidity</div>
                                <div className="fs-5">{filteredOpportunities.filter(o => (o.estimated_liquidity_usd || 0) >= 50000).length}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Chains Active</div>
                                <div className="fs-5">{new Set(filteredOpportunities.map(o => o.chain)).size}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Avg Score</div>
                                <div className="fs-6">
                                    {filteredOpportunities.length > 0
                                        ? (filteredOpportunities.reduce((sum, o) => sum + (o.opportunity_score || 0), 0) / filteredOpportunities.length).toFixed(1)
                                        : '0.0'
                                    }
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Pagination Controls - Top */}
                    {filteredOpportunities.length > itemsPerPage && (
                        <div className="d-flex justify-content-between align-items-center mb-3 border-bottom pb-2">
                            <div className="d-flex align-items-center gap-2">
                                <small>Show:</small>
                                <Form.Select
                                    size="sm"
                                    value={itemsPerPage}
                                    onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
                                    style={{ width: 'auto' }}
                                >
                                    <option value={10}>10</option>
                                    <option value={20}>20</option>
                                    <option value={50}>50</option>
                                    <option value={100}>100</option>
                                </Form.Select>
                                <small>per page</small>
                            </div>

                            <Pagination size="sm" className="mb-0">
                                <Pagination.First
                                    disabled={currentPage === 1}
                                    onClick={() => handlePageChange(1)}
                                />
                                <Pagination.Prev
                                    disabled={currentPage === 1}
                                    onClick={() => handlePageChange(currentPage - 1)}
                                />

                                {/* Show page numbers around current page */}
                                {Array.from({ length: Math.min(7, totalPages) }, (_, i) => {
                                    let pageNum;
                                    if (totalPages <= 7) {
                                        pageNum = i + 1;
                                    } else if (currentPage <= 4) {
                                        pageNum = i + 1;
                                    } else if (currentPage >= totalPages - 3) {
                                        pageNum = totalPages - 6 + i;
                                    } else {
                                        pageNum = currentPage - 3 + i;
                                    }

                                    return (
                                        <Pagination.Item
                                            key={pageNum}
                                            active={pageNum === currentPage}
                                            onClick={() => handlePageChange(pageNum)}
                                        >
                                            {pageNum}
                                        </Pagination.Item>
                                    );
                                })}

                                <Pagination.Next
                                    disabled={currentPage === totalPages}
                                    onClick={() => handlePageChange(currentPage + 1)}
                                />
                                <Pagination.Last
                                    disabled={currentPage === totalPages}
                                    onClick={() => handlePageChange(totalPages)}
                                />
                            </Pagination>

                            <small className="text-muted">
                                {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, filteredOpportunities.length)}
                                of {filteredOpportunities.length}
                            </small>
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
                                        <th>Time</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {opportunities.map((opp, index) => (
                                        <tr key={`${opp.pair_address}-${index}`}>
                                            <td>
                                                <strong>{opp.base_symbol || 'TOKEN'}</strong>
                                                <span className="text-muted">/</span>
                                                <span>{opp.quote_symbol || 'WETH'}</span>
                                                <div className="small text-muted font-monospace">
                                                    {opp.address?.slice(0, 8)}...
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
                                                    (opp.liquidity_usd || 0) >= 100000 ? 'text-success fw-bold' :
                                                        (opp.liquidity_usd || 0) >= 50000 ? 'text-warning' :
                                                            'text-danger'
                                                }>
                                                    ${(opp.liquidity_usd || 0).toLocaleString()}
                                                </span>
                                            </td>
                                            <td>
                                                <Badge
                                                    bg={opp.source === 'dexscreener' ? 'success' :
                                                        opp.source === 'coingecko_trending' ? 'warning' :
                                                            opp.source === 'jupiter' ? 'primary' : 'secondary'}
                                                >
                                                    {opp.source || 'unknown'}
                                                </Badge>
                                            </td>
                                            <td>
                                                <Badge bg={
                                                    (opp.score || 0) >= 8 ? 'success' :
                                                        (opp.score || 0) >= 6 ? 'warning' : 'secondary'
                                                }>
                                                    {opp.score ? opp.score.toFixed(1) : 'N/A'}
                                                </Badge>
                                            </td>
                                            <td>
                                                <small className="text-muted">
                                                    {formatTimeAgo(opp.created_at)}
                                                </small>
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
                                {rawOpportunities.length === 0
                                    ? "No opportunities found. The system is scanning for new trading opportunities..."
                                    : "No opportunities match your current filters. Try adjusting the filter settings above."
                                }
                            </Alert>
                        )
                    )}

                    {/* Pagination Controls - Bottom */}
                    {filteredOpportunities.length > itemsPerPage && (
                        <div className="d-flex justify-content-center mt-3 border-top pt-3">
                            <Pagination>
                                <Pagination.First
                                    disabled={currentPage === 1}
                                    onClick={() => handlePageChange(1)}
                                />
                                <Pagination.Prev
                                    disabled={currentPage === 1}
                                    onClick={() => handlePageChange(currentPage - 1)}
                                />

                                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                                    let pageNum;
                                    if (totalPages <= 5) {
                                        pageNum = i + 1;
                                    } else if (currentPage <= 3) {
                                        pageNum = i + 1;
                                    } else if (currentPage >= totalPages - 2) {
                                        pageNum = totalPages - 4 + i;
                                    } else {
                                        pageNum = currentPage - 2 + i;
                                    }

                                    return (
                                        <Pagination.Item
                                            key={pageNum}
                                            active={pageNum === currentPage}
                                            onClick={() => handlePageChange(pageNum)}
                                        >
                                            {pageNum}
                                        </Pagination.Item>
                                    );
                                })}

                                <Pagination.Next
                                    disabled={currentPage === totalPages}
                                    onClick={() => handlePageChange(currentPage + 1)}
                                />
                                <Pagination.Last
                                    disabled={currentPage === totalPages}
                                    onClick={() => handlePageChange(totalPages)}
                                />
                            </Pagination>
                        </div>
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
                                <div className="mt-2">Analyzing opportunity...</div>
                            </div>
                        ) : analysisResult ? (
                            analysisResult.error ? (
                                <Alert variant="danger">
                                    <strong>Analysis Error:</strong> {analysisResult.error}
                                </Alert>
                            ) : (
                                <div>
                                    <div className="row mb-3">
                                        <div className="col-md-6">
                                            <strong>Risk Score:</strong> {analysisResult.risk_score || 'N/A'}
                                        </div>
                                        <div className="col-md-6">
                                            <strong>Recommendation:</strong>
                                            <Badge bg={
                                                analysisResult.recommendation === 'buy' ? 'success' :
                                                    analysisResult.recommendation === 'hold' ? 'warning' : 'danger'
                                            } className="ms-2">
                                                {analysisResult.recommendation || 'N/A'}
                                            </Badge>
                                        </div>
                                    </div>

                                    {analysisResult.liquidity_risk && (
                                        <div className="mb-2">
                                            <strong>Liquidity Risk:</strong> {analysisResult.liquidity_risk}
                                        </div>
                                    )}

                                    {analysisResult.tax_analysis && (
                                        <div className="mb-2">
                                            <strong>Tax Analysis:</strong> Buy {(analysisResult.tax_analysis.buy_tax * 100).toFixed(1)}% /
                                            Sell {(analysisResult.tax_analysis.sell_tax * 100).toFixed(1)}%
                                        </div>
                                    )}

                                    {analysisResult.confidence && (
                                        <div className="mb-2">
                                            <strong>Confidence:</strong> {(analysisResult.confidence * 100).toFixed(1)}%
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