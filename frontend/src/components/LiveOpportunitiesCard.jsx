import { useState, useEffect, useRef, useMemo } from 'react';
import { Card, Button, Table, Badge, Alert, Spinner, Modal, Form, Row, Col, ButtonGroup, Pagination } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi';

export function LiveOpportunitiesCard() {
    // ===========================================
    // STATE MANAGEMENT
    // ===========================================
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [selectedOpportunity, setSelectedOpportunity] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState(null);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const refreshIntervalRef = useRef(null);

    // Filter states - controls which opportunities to show
    const [filters, setFilters] = useState({
        minScore: 0,
        maxScore: 30,
        minLiquidity: 0,
        maxLiquidity: 1000000,
        selectedChains: new Set(['ethereum', 'bsc', 'base', 'polygon', 'solana']),
        selectedSources: new Set(['dexscreener', 'coingecko_trending', 'jupiter', '1inch', 'uniswap_v3', 'pancakeswap'])
    });

    // Pagination states - controls table display
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(20);

    // ===========================================
    // DATA FETCHING HOOKS
    // ===========================================
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

    // Extract raw opportunities from API response
    const rawOpportunities = opportunitiesData?.opportunities || [];

    // DEBUG: Log first opportunity to see actual field structure
    useEffect(() => {
        if (rawOpportunities.length > 0) {
            console.log('Backend opportunity data structure:', rawOpportunities[0]);
            console.log('Available fields:', Object.keys(rawOpportunities[0]));
        }
    }, [rawOpportunities]);

    // ===========================================
    // DATA PROCESSING & FILTERING
    // ===========================================

    // Filter and sort opportunities based on user selections
    const filteredOpportunities = useMemo(() => {
        return rawOpportunities.filter(opp => {
            // Map backend fields to frontend expectations with fallbacks
            const score = opp.opportunity_score || opp.score || 0;
            const liquidity = opp.estimated_liquidity_usd || opp.liquidity_usd || opp.liquidity || 0;
            const chain = opp.chain || 'unknown';
            const source = opp.source || 'unknown';

            // Apply all filter criteria
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
            const timeA = new Date(a.timestamp || a.created_at || 0).getTime();
            const timeB = new Date(b.timestamp || b.created_at || 0).getTime();
            if (timeB !== timeA) {
                return timeB - timeA; // Latest first
            }
            const scoreA = a.opportunity_score || a.score || 0;
            const scoreB = b.opportunity_score || b.score || 0;
            return scoreB - scoreA; // Then by score (highest first)
        });
    }, [rawOpportunities, filters]);

    // Paginate filtered opportunities for table display
    const totalPages = Math.ceil(filteredOpportunities.length / itemsPerPage);
    const paginatedOpportunities = useMemo(() => {
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        return filteredOpportunities.slice(startIndex, endIndex);
    }, [filteredOpportunities, currentPage, itemsPerPage]);

    const opportunities = paginatedOpportunities;

    // ===========================================
    // AUTO-REFRESH MECHANISM
    // ===========================================

    useEffect(() => {
        if (autoRefresh) {
            refreshIntervalRef.current = setInterval(() => {
                console.log('Auto-refreshing opportunities...');
                refresh();
                refreshStats();
                setLastUpdate(new Date());
            }, 15000); // Refresh every 15 seconds
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

    // ===========================================
    // EVENT HANDLERS
    // ===========================================

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
            selectedSources: new Set(['dexscreener', 'coingecko_trending', 'jupiter', '1inch', 'uniswap_v3', 'pancakeswap'])
        });
        setCurrentPage(1);
    };

    // Reset to page 1 when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [filters]);

    // ===========================================
    // PAGINATION HANDLERS
    // ===========================================

    const handlePageChange = (page) => {
        setCurrentPage(Math.max(1, Math.min(page, totalPages)));
    };

    const handleItemsPerPageChange = (newItemsPerPage) => {
        setItemsPerPage(newItemsPerPage);
        setCurrentPage(1);
    };

    // ===========================================
    // OPPORTUNITY ANALYSIS
    // ===========================================

    const analyzeOpportunity = async (opportunity) => {
        console.log('Analyze button clicked for:', opportunity.pair_address || opportunity.address);
        setSelectedOpportunity(opportunity);
        setAnalyzing(true);
        setAnalysisResult(null);
        setShowAnalysisModal(true);

        try {
            // Map opportunity fields with fallbacks for API request
            const requestData = {
                pair_address: opportunity.pair_address || opportunity.address || '',
                chain: opportunity.chain || 'ethereum',
                dex: opportunity.dex || 'unknown',
                token0_symbol: opportunity.token0_symbol || opportunity.base_symbol || 'TOKEN0',
                token1_symbol: opportunity.token1_symbol || opportunity.quote_symbol || 'TOKEN1',
                estimated_liquidity_usd: opportunity.estimated_liquidity_usd || opportunity.liquidity_usd || 0,
                timestamp: opportunity.timestamp || opportunity.created_at || new Date().toISOString(),
                source: opportunity.source || 'unknown',
                opportunity_score: opportunity.opportunity_score || opportunity.score || 0,
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

    // ===========================================
    // UTILITY FUNCTIONS
    // ===========================================

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

    // Helper function to safely get field values with fallbacks
    const getFieldValue = (opp, primaryField, fallbackField, defaultValue = '') => {
        return opp[primaryField] || opp[fallbackField] || defaultValue;
    };

    // ===========================================
    // COMPONENT RENDER
    // ===========================================

    return (
        <>
            <Card className="mb-4">
                {/* ===========================================
                    CARD HEADER - Title, Counts, Controls
                    =========================================== */}
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
                    {/* ===========================================
                        ERROR DISPLAY
                        =========================================== */}
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

                    {/* ===========================================
                        FILTER CONTROLS
                        =========================================== */}
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

                                {/* Source Filter - Updated with all sources */}
                                <Col md={3}>
                                    <Form.Label className="small mb-1">Sources</Form.Label>
                                    <div className="d-flex flex-wrap gap-1">
                                        {[
                                            { key: 'dexscreener', label: 'DEX' },
                                            { key: 'coingecko_trending', label: 'CG' },
                                            { key: 'jupiter', label: 'JUP' },
                                            { key: '1inch', label: '1INCH' },
                                            { key: 'uniswap_v3', label: 'UNI' },
                                            { key: 'pancakeswap', label: 'CAKE' }
                                        ].map(({ key, label }) => (
                                            <Badge
                                                key={key}
                                                bg={filters.selectedSources.has(key) ? 'success' : 'outline-secondary'}
                                                style={{ cursor: 'pointer' }}
                                                onClick={() => handleSourceToggle(key)}
                                            >
                                                {label}
                                            </Badge>
                                        ))}
                                    </div>
                                </Col>
                            </Row>
                        </Card.Body>
                    </Card>

                    {/* ===========================================
                        STATS SUMMARY
                        =========================================== */}
                    {stats && (
                        <div className="row mb-3">
                            <div className="col-md-3 text-center">
                                <div className="fw-bold text-success">Showing</div>
                                <div className="fs-5">{opportunities.length}</div>
                                <small className="text-muted">of {filteredOpportunities.length} filtered</small>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">High Liquidity</div>
                                <div className="fs-5">{filteredOpportunities.filter(o => {
                                    const liquidity = o.estimated_liquidity_usd || o.liquidity_usd || 0;
                                    return liquidity >= 50000;
                                }).length}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Chains Active</div>
                                <div className="fs-5">{new Set(filteredOpportunities.map(o => o.chain)).size}</div>
                            </div>
                            <div className="col-md-3 text-center">
                                <div className="fw-bold">Avg Score</div>
                                <div className="fs-6">
                                    {filteredOpportunities.length > 0
                                        ? (filteredOpportunities.reduce((sum, o) => {
                                            const score = o.opportunity_score || o.score || 0;
                                            return sum + score;
                                        }, 0) / filteredOpportunities.length).toFixed(1)
                                        : '0.0'
                                    }
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ===========================================
                        PAGINATION CONTROLS - TOP
                        =========================================== */}
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

                    {/* ===========================================
                        LOADING STATE
                        =========================================== */}
                    {loading && opportunities.length === 0 && (
                        <div className="text-center py-4">
                            <Spinner animation="border" />
                            <div className="mt-2">Loading opportunities...</div>
                        </div>
                    )}

                    {/* ===========================================
                        OPPORTUNITIES TABLE - MAIN DATA DISPLAY
                        =========================================== */}
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
                                    {opportunities.map((opp, index) => {
                                        // Map fields with multiple fallback options
                                        const baseSymbol = getFieldValue(opp, 'base_symbol', 'token0_symbol', 'TOKEN');
                                        const quoteSymbol = getFieldValue(opp, 'quote_symbol', 'token1_symbol', 'WETH');
                                        const address = getFieldValue(opp, 'address', 'pair_address', '');
                                        const chain = getFieldValue(opp, 'chain', '', 'unknown');
                                        const dex = getFieldValue(opp, 'dex', '', 'unknown');
                                        const liquidity = opp.liquidity_usd || opp.estimated_liquidity_usd || 0;
                                        const source = getFieldValue(opp, 'source', '', 'unknown');
                                        const score = opp.score || opp.opportunity_score || 0;
                                        const timestamp = opp.created_at || opp.timestamp;

                                        return (
                                            <tr key={`${address}-${index}`}>
                                                {/* Token Pair Column */}
                                                <td>
                                                    <strong>{baseSymbol}</strong>
                                                    <span className="text-muted">/</span>
                                                    <span>{quoteSymbol}</span>
                                                    {address && (
                                                        <div className="small text-muted font-monospace">
                                                            {address.slice(0, 8)}...
                                                        </div>
                                                    )}
                                                </td>

                                                {/* Chain Column */}
                                                <td>
                                                    <Badge bg="secondary">{chain}</Badge>
                                                </td>

                                                {/* DEX Column */}
                                                <td>
                                                    <Badge bg="info">{dex}</Badge>
                                                </td>

                                                {/* Liquidity Column - Color coded by amount */}
                                                <td>
                                                    <span className={
                                                        liquidity >= 100000 ? 'text-success fw-bold' :
                                                            liquidity >= 50000 ? 'text-warning' :
                                                                'text-danger'
                                                    }>
                                                        ${liquidity.toLocaleString()}
                                                    </span>
                                                </td>

                                                {/* Source Column - Color coded by source type */}
                                                <td>
                                                    <Badge
                                                        bg={source === 'dexscreener' ? 'success' :
                                                            source === 'coingecko_trending' ? 'warning' :
                                                                source === 'jupiter' ? 'primary' :
                                                                    source === '1inch' ? 'info' :
                                                                        source === 'uniswap_v3' ? 'success' :
                                                                            source === 'pancakeswap' ? 'warning' : 'secondary'}
                                                    >
                                                        {source}
                                                    </Badge>
                                                </td>

                                                {/* Score Column - Color coded by score value */}
                                                <td>
                                                    <Badge bg={
                                                        score >= 8 ? 'success' :
                                                            score >= 6 ? 'warning' : 'secondary'
                                                    }>
                                                        {score ? score.toFixed(1) : 'N/A'}
                                                    </Badge>
                                                </td>

                                                {/* Time Column */}
                                                <td>
                                                    <small className="text-muted">
                                                        {formatTimeAgo(timestamp)}
                                                    </small>
                                                </td>

                                                {/* Actions Column */}
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
                                        );
                                    })}
                                </tbody>
                            </Table>
                        </div>
                    ) : (
                        /* ===========================================
                            NO DATA STATE
                            =========================================== */
                        !loading && (
                            <Alert variant="info">
                                {rawOpportunities.length === 0
                                    ? "No opportunities found. The system is scanning for new trading opportunities..."
                                    : "No opportunities match your current filters. Try adjusting the filter settings above."
                                }
                            </Alert>
                        )
                    )}

                    {/* ===========================================
                        PAGINATION CONTROLS - BOTTOM
                        =========================================== */}
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

            {/* ===========================================
                ANALYSIS MODAL - DETAILED OPPORTUNITY ANALYSIS
                =========================================== */}
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
                            `${getFieldValue(selectedOpportunity, 'token0_symbol', 'base_symbol', 'TOKEN0')}/${getFieldValue(selectedOpportunity, 'token1_symbol', 'quote_symbol', 'TOKEN1')}` :
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