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
        selectedDexes: new Set(['quickswap', 'jupiter', '1inch', 'uniswap_v3', 'pancakeswap'])
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
        const filtered = rawOpportunities.filter(opp => {
            // Backend already returns correct field names - use them directly
            const score = opp.score || 0;
            const liquidity = opp.liquidity_usd || 0;
            const chain = opp.chain || 'unknown';
            const dex = opp.dex || 'unknown';

            return (
                score >= filters.minScore &&
                score <= filters.maxScore &&
                liquidity >= filters.minLiquidity &&
                liquidity <= filters.maxLiquidity &&
                filters.selectedChains.has(chain) &&
                filters.selectedDexes.has(dex)
            );
        }).sort((a, b) => {
            // Sort by timestamp first (latest first), then by score (highest first)
            const timeA = new Date(a.timestamp || a.created_at || 0).getTime();
            const timeB = new Date(b.timestamp || b.created_at || 0).getTime();
            if (timeB !== timeA) {
                return timeB - timeA; // Latest first
            }
            const scoreA = a.score || 0;
            const scoreB = b.score || 0;
            return scoreB - scoreA; // Then by score (highest first)
        });

        console.log('Filtered count:', filtered.length, 'Items per page:', itemsPerPage);
        return filtered;
    }, [rawOpportunities, filters, itemsPerPage]);

    // DEBUG: Force pagination to show for testing
    const shouldShowPagination = true; // Change this to test pagination
    // const shouldShowPagination = filteredOpportunities.length > itemsPerPage;

    console.log('=== PAGINATION DEBUG ===');
    console.log('Raw opportunities:', rawOpportunities.length);
    console.log('Filtered opportunities:', filteredOpportunities.length);
    console.log('Items per page:', itemsPerPage);
    console.log('Total pages:', Math.ceil(filteredOpportunities.length / itemsPerPage));
    console.log('Should show pagination:', shouldShowPagination);
    console.log('========================');

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

    const handleDexToggle = (dex) => {
        setFilters(prev => {
            const newDexes = new Set(prev.selectedDexes);
            if (newDexes.has(dex)) {
                newDexes.delete(dex);
            } else {
                newDexes.add(dex);
            }
            return { ...prev, selectedDexes: newDexes };
        });
    };

    const resetFilters = () => {
        setFilters({
            minScore: 0,
            maxScore: 30,
            minLiquidity: 0,
            maxLiquidity: 1000000,
            selectedChains: new Set(['ethereum', 'bsc', 'base', 'polygon', 'solana']),
            selectedDexes: new Set(['quickswap', 'jupiter', '1inch', 'uniswap_v3', 'pancakeswap'])
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
                token0_symbol: opportunity.token0_symbol || opportunity.base_symbol || opportunity.symbol?.split('/')[0] || 'TOKEN0',
                token1_symbol: opportunity.token1_symbol || opportunity.quote_symbol || opportunity.symbol?.split('/')[1] || 'TOKEN1',
                estimated_liquidity_usd: opportunity.estimated_liquidity_usd || opportunity.liquidity_usd || 0,
                timestamp: opportunity.timestamp || opportunity.created_at || new Date().toISOString(),
                source: opportunity.source || opportunity.dex || 'unknown',
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

                                {/* DEX Filter - Updated to use dexes */}
                                <Col md={3}>
                                    <Form.Label className="small mb-1">DEXes</Form.Label>
                                    <div className="d-flex flex-wrap gap-1">
                                        {[
                                            { key: 'quickswap', label: 'QUICK' },
                                            { key: 'jupiter', label: 'JUP' },
                                            { key: '1inch', label: '1INCH' },
                                            { key: 'uniswap_v3', label: 'UNI' },
                                            { key: 'pancakeswap', label: 'CAKE' }
                                        ].map(({ key, label }) => (
                                            <Badge
                                                key={key}
                                                bg={filters.selectedDexes.has(key) ? 'success' : 'outline-secondary'}
                                                style={{ cursor: 'pointer' }}
                                                onClick={() => handleDexToggle(key)}
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
                                    const liquidity = o.liquidity_usd || 0;
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
                                            const score = o.score || 0;
                                            return sum + score;
                                        }, 0) / filteredOpportunities.length).toFixed(1)
                                        : '0.0'
                                    }
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ===========================================
                        PAGINATION CONTROLS - TOP (Always show for debugging)
                        =========================================== */}
                    {shouldShowPagination && (
                        <Card className="mb-3 bg-primary bg-opacity-10 border-primary">
                            <Card.Body className="py-2">
                                <div className="d-flex justify-content-between align-items-center">
                                    <div className="d-flex align-items-center gap-3">
                                        <div className="d-flex align-items-center gap-2">
                                            <small><strong>Show:</strong></small>
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
                                        <div className="text-muted small">
                                            <strong>Page {currentPage} of {totalPages}</strong>
                                            <span className="mx-2">•</span>
                                            Showing {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, filteredOpportunities.length)} of {filteredOpportunities.length} opportunities
                                        </div>
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
                                </div>
                            </Card.Body>
                        </Card>
                    )}

                    {/* ===========================================
                        QUICK JUMP TO PAGES (For large datasets)
                        =========================================== */}
                    {totalPages > 10 && (
                        <div className="d-flex justify-content-center mb-3">
                            <div className="d-flex align-items-center gap-2">
                                <small className="text-muted">Quick jump to page:</small>
                                <Form.Control
                                    type="number"
                                    size="sm"
                                    min={1}
                                    max={totalPages}
                                    value={currentPage}
                                    onChange={(e) => {
                                        const page = Number(e.target.value);
                                        if (page >= 1 && page <= totalPages) {
                                            handlePageChange(page);
                                        }
                                    }}
                                    style={{ width: '70px' }}
                                />
                                <small className="text-muted">of {totalPages}</small>
                                <Button
                                    size="sm"
                                    variant="outline-primary"
                                    onClick={() => handlePageChange(totalPages)}
                                >
                                    Go to Last
                                </Button>
                            </div>
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
                                        <th>Volume 24h</th>
                                        <th>Score</th>
                                        <th>Risk</th>
                                        <th>Time</th>
                                        <th>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {opportunities.map((opp, index) => {
                                        // Extract symbol components if available
                                        const symbol = opp.symbol || '';
                                        const [baseSymbol, quoteSymbol] = symbol.includes('/')
                                            ? symbol.split('/')
                                            : [symbol || 'TOKEN', 'UNKNOWN'];

                                        const address = opp.address || opp.id || '';
                                        const chain = opp.chain || 'unknown';
                                        const dex = opp.dex || 'unknown';
                                        const liquidity = opp.liquidity_usd || 0;
                                        const volume24h = opp.volume_24h_usd || 0;
                                        const score = opp.score || 0;
                                        const riskLevel = opp.risk_level || 'unknown';
                                        const timestamp = opp.timestamp || opp.created_at;

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

                                                {/* Volume 24h Column */}
                                                <td>
                                                    <span className={
                                                        volume24h >= 500000 ? 'text-success' :
                                                            volume24h >= 100000 ? 'text-warning' :
                                                                'text-muted'
                                                    }>
                                                        ${volume24h.toLocaleString()}
                                                    </span>
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

                                                {/* Risk Level Column */}
                                                <td>
                                                    <Badge bg={
                                                        riskLevel === 'low' ? 'success' :
                                                            riskLevel === 'medium' ? 'warning' :
                                                                riskLevel === 'high' ? 'danger' : 'secondary'
                                                    }>
                                                        {riskLevel}
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
                        PAGINATION CONTROLS - BOTTOM (Always show for debugging)
                        =========================================== */}
                    {shouldShowPagination && (
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
        ENHANCED ANALYSIS MODAL - DISPLAYS ALL BACKEND DATA
        =========================================== */}
            <Modal
                show={showAnalysisModal}
                onHide={closeModal}
                size="xl"  // Changed to extra large for more data
                backdrop="static"
                keyboard={false}
            >
                <Modal.Header closeButton>
                    <Modal.Title>
                        Detailed Analysis - {selectedOpportunity ?
                            `${selectedOpportunity.symbol || getFieldValue(selectedOpportunity, 'token0_symbol', 'base_symbol', 'TOKEN0')}/${getFieldValue(selectedOpportunity, 'token1_symbol', 'quote_symbol', 'TOKEN1')}` :
                            'Loading...'}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <div style={{ maxHeight: '80vh', overflowY: 'auto' }}>
                        {analyzing ? (
                            <div className="text-center py-4">
                                <Spinner animation="border" />
                                <div className="mt-2">Analyzing opportunity...</div>
                            </div>
                        ) : analysisResult ? (
                            analysisResult.error ? (
                                <Alert variant="danger">
                                    <strong>Analysis Error:</strong> {analysisResult.error}
                                    {analysisResult.details && (
                                        <div className="mt-2 small">
                                            <strong>Status:</strong> {analysisResult.details.status_code}<br />
                                            <strong>URL:</strong> {analysisResult.details.url}<br />
                                            <strong>Trace ID:</strong> {analysisResult.details.trace_id}
                                        </div>
                                    )}
                                </Alert>
                            ) : (
                                <div>
                                    {/* ===========================================
                                EXECUTIVE SUMMARY
                                =========================================== */}
                                    <Card className="mb-3 border-primary">
                                        <Card.Header className="bg-primary text-white">
                                            <h5 className="mb-0">Executive Summary</h5>
                                        </Card.Header>
                                        <Card.Body>
                                            <Row>
                                                <Col md={3}>
                                                    <div className="text-center">
                                                        <div className="fw-bold">Action</div>
                                                        <Badge
                                                            bg={
                                                                analysisResult.recommendation?.action === 'BUY' ? 'success' :
                                                                    analysisResult.recommendation?.action === 'CONSIDER' ? 'warning' :
                                                                        analysisResult.recommendation?.action === 'MONITOR' ? 'info' : 'danger'
                                                            }
                                                            className="fs-6"
                                                        >
                                                            {analysisResult.recommendation?.action || 'N/A'}
                                                        </Badge>
                                                    </div>
                                                </Col>
                                                <Col md={3}>
                                                    <div className="text-center">
                                                        <div className="fw-bold">Confidence</div>
                                                        <div className="fs-5">
                                                            {analysisResult.recommendation?.confidence ?
                                                                `${(analysisResult.recommendation.confidence * 100).toFixed(1)}%` : 'N/A'}
                                                        </div>
                                                    </div>
                                                </Col>
                                                <Col md={3}>
                                                    <div className="text-center">
                                                        <div className="fw-bold">Risk Level</div>
                                                        <Badge
                                                            bg={
                                                                analysisResult.risk_assessment?.risk_level === 'low' ? 'success' :
                                                                    analysisResult.risk_assessment?.risk_level === 'medium' ? 'warning' : 'danger'
                                                            }
                                                        >
                                                            {analysisResult.risk_assessment?.risk_level || 'N/A'}
                                                        </Badge>
                                                    </div>
                                                </Col>
                                                <Col md={3}>
                                                    <div className="text-center">
                                                        <div className="fw-bold">Position Size</div>
                                                        <Badge bg="info">
                                                            {analysisResult.recommendation?.position_size || 'N/A'}
                                                        </Badge>
                                                    </div>
                                                </Col>
                                            </Row>
                                        </Card.Body>
                                    </Card>

                                    {/* ===========================================
                                RECOMMENDATION DETAILS
                                =========================================== */}
                                    {analysisResult.recommendation && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Trading Recommendation</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    <Col md={6}>
                                                        <div><strong>Entry Strategy:</strong> {analysisResult.recommendation.entry_strategy || 'N/A'}</div>
                                                        <div><strong>Stop Loss:</strong> {analysisResult.recommendation.stop_loss ? `${(analysisResult.recommendation.stop_loss * 100).toFixed(1)}%` : 'N/A'}</div>
                                                        <div><strong>Take Profit 1:</strong> {analysisResult.recommendation.take_profit_1 ? `${(analysisResult.recommendation.take_profit_1 * 100).toFixed(1)}%` : 'N/A'}</div>
                                                    </Col>
                                                    <Col md={6}>
                                                        <div><strong>Take Profit 2:</strong> {analysisResult.recommendation.take_profit_2 ? `${(analysisResult.recommendation.take_profit_2 * 100).toFixed(1)}%` : 'N/A'}</div>
                                                        <div><strong>Max Slippage:</strong> {analysisResult.recommendation.max_slippage ? `${(analysisResult.recommendation.max_slippage * 100).toFixed(1)}%` : 'N/A'}</div>
                                                        <div><strong>Gas Priority:</strong> {analysisResult.recommendation.gas_priority || 'N/A'}</div>
                                                    </Col>
                                                </Row>
                                                {analysisResult.recommendation.rationale && (
                                                    <div className="mt-2">
                                                        <strong>Rationale:</strong>
                                                        <div className="text-muted">{analysisResult.recommendation.rationale}</div>
                                                    </div>
                                                )}
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                LIQUIDITY ANALYSIS
                                =========================================== */}
                                    {analysisResult.liquidity_analysis && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Liquidity Analysis</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    <Col md={6}>
                                                        <div><strong>Current Liquidity:</strong> ${analysisResult.liquidity_analysis.current_liquidity_usd?.toLocaleString() || 'N/A'}</div>
                                                        <div><strong>24h Volume:</strong> ${analysisResult.liquidity_analysis.volume_24h_usd?.toLocaleString() || 'N/A'}</div>
                                                        <div><strong>Volume/Liquidity Ratio:</strong> {analysisResult.liquidity_analysis.volume_to_liquidity_ratio?.toFixed(3) || 'N/A'}</div>
                                                    </Col>
                                                    <Col md={6}>
                                                        <div><strong>5% Depth:</strong> ${analysisResult.liquidity_analysis.liquidity_depth_5pct?.toLocaleString() || 'N/A'}</div>
                                                        <div><strong>10% Depth:</strong> ${analysisResult.liquidity_analysis.liquidity_depth_10pct?.toLocaleString() || 'N/A'}</div>
                                                        <div><strong>24h Stability:</strong>
                                                            <Badge
                                                                bg={analysisResult.liquidity_analysis.liquidity_stability_24h === 'stable' ? 'success' : 'warning'}
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.liquidity_analysis.liquidity_stability_24h || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                    </Col>
                                                </Row>
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                RISK ASSESSMENT
                                =========================================== */}
                                    {analysisResult.risk_assessment && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Risk Assessment</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    <Col md={6}>
                                                        <div><strong>Contract Verification:</strong>
                                                            <Badge
                                                                bg={analysisResult.risk_assessment.contract_verification === 'verified' ? 'success' : 'danger'}
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.risk_assessment.contract_verification || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                        <div><strong>Honeypot Risk:</strong>
                                                            <Badge
                                                                bg={
                                                                    analysisResult.risk_assessment.honeypot_risk === 'low' ? 'success' :
                                                                        analysisResult.risk_assessment.honeypot_risk === 'medium' ? 'warning' : 'danger'
                                                                }
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.risk_assessment.honeypot_risk || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                        <div><strong>Ownership Risk:</strong>
                                                            <Badge
                                                                bg={analysisResult.risk_assessment.ownership_risk === 'renounced' ? 'success' : 'warning'}
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.risk_assessment.ownership_risk || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                    </Col>
                                                    <Col md={6}>
                                                        <div><strong>Buy Tax:</strong> {analysisResult.risk_assessment.buy_tax ? `${(analysisResult.risk_assessment.buy_tax * 100).toFixed(1)}%` : '0.0%'}</div>
                                                        <div><strong>Sell Tax:</strong> {analysisResult.risk_assessment.sell_tax ? `${(analysisResult.risk_assessment.sell_tax * 100).toFixed(1)}%` : '0.0%'}</div>
                                                        <div><strong>Liquidity Locked:</strong>
                                                            <Badge
                                                                bg={analysisResult.risk_assessment.liquidity_locked ? 'success' : 'danger'}
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.risk_assessment.liquidity_locked ? 'Yes' : 'No'}
                                                            </Badge>
                                                        </div>
                                                    </Col>
                                                </Row>
                                                <Row className="mt-2">
                                                    <Col md={12}>
                                                        <div><strong>Risk Score:</strong>
                                                            <span className="ms-1 fw-bold">{analysisResult.risk_assessment.risk_score?.toFixed(1) || 'N/A'}/10</span>
                                                        </div>
                                                        {analysisResult.risk_assessment.lock_duration_days && (
                                                            <div><strong>Lock Duration:</strong> {analysisResult.risk_assessment.lock_duration_days} days</div>
                                                        )}
                                                    </Col>
                                                </Row>
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                TOKEN ANALYSIS
                                =========================================== */}
                                    {analysisResult.token_analysis && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Token Analysis</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    {analysisResult.token_analysis.token0 && (
                                                        <Col md={6}>
                                                            <h6 className="text-primary">{analysisResult.token_analysis.token0.symbol || 'Token 0'}</h6>
                                                            <div><strong>Total Supply:</strong> {analysisResult.token_analysis.token0.total_supply?.toLocaleString() || 'N/A'}</div>
                                                            <div><strong>Circulating:</strong> {analysisResult.token_analysis.token0.circulating_supply?.toLocaleString() || 'N/A'}</div>
                                                            <div><strong>Holders:</strong> {analysisResult.token_analysis.token0.holder_count?.toLocaleString() || 'N/A'}</div>
                                                            <div><strong>Top 10 Holders:</strong> {analysisResult.token_analysis.token0.top_10_holder_percentage?.toFixed(1) || 'N/A'}%</div>
                                                        </Col>
                                                    )}
                                                    {analysisResult.token_analysis.token1 && (
                                                        <Col md={6}>
                                                            <h6 className="text-success">{analysisResult.token_analysis.token1.symbol || 'Token 1'}</h6>
                                                            <div><strong>Type:</strong>
                                                                {analysisResult.token_analysis.token1.is_stablecoin && <Badge bg="info" className="ms-1">Stablecoin</Badge>}
                                                                {analysisResult.token_analysis.token1.is_wrapped_native && <Badge bg="success" className="ms-1">Wrapped Native</Badge>}
                                                            </div>
                                                            <div><strong>Decimals:</strong> {analysisResult.token_analysis.token1.decimals || 'N/A'}</div>
                                                            {analysisResult.token_analysis.pair_quality_score && (
                                                                <div><strong>Pair Quality Score:</strong> {analysisResult.token_analysis.pair_quality_score}/6</div>
                                                            )}
                                                        </Col>
                                                    )}
                                                </Row>
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                TRADING SIGNALS
                                =========================================== */}
                                    {analysisResult.trading_signals && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Trading Signals</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <Row>
                                                    <Col md={6}>
                                                        <div><strong>Momentum Score:</strong>
                                                            <span className="ms-1 fw-bold">{analysisResult.trading_signals.momentum_score || 'N/A'}/10</span>
                                                        </div>
                                                        <div><strong>Technical Score:</strong>
                                                            <span className="ms-1 fw-bold">{analysisResult.trading_signals.technical_score || 'N/A'}/10</span>
                                                        </div>
                                                        <div><strong>Trend Direction:</strong>
                                                            <Badge
                                                                bg={
                                                                    analysisResult.trading_signals.trend_direction === 'bullish' ? 'success' :
                                                                        analysisResult.trading_signals.trend_direction === 'bearish' ? 'danger' : 'secondary'
                                                                }
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.trading_signals.trend_direction || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                    </Col>
                                                    <Col md={6}>
                                                        <div><strong>Volume Trend:</strong> {analysisResult.trading_signals.volume_trend || 'N/A'}</div>
                                                        <div><strong>Social Sentiment:</strong>
                                                            <Badge
                                                                bg={
                                                                    analysisResult.trading_signals.social_sentiment === 'positive' ? 'success' :
                                                                        analysisResult.trading_signals.social_sentiment === 'negative' ? 'danger' : 'secondary'
                                                                }
                                                                className="ms-1"
                                                            >
                                                                {analysisResult.trading_signals.social_sentiment || 'N/A'}
                                                            </Badge>
                                                        </div>
                                                        <div><strong>Whale Activity:</strong> {analysisResult.trading_signals.whale_activity || 'N/A'}</div>
                                                    </Col>
                                                </Row>
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                METADATA & WARNINGS
                                =========================================== */}
                                    {analysisResult.metadata && (
                                        <Card className="mb-3">
                                            <Card.Header>
                                                <h6 className="mb-0">Analysis Metadata</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                {analysisResult.metadata.warnings && analysisResult.metadata.warnings.length > 0 && (
                                                    <div className="mb-3">
                                                        <strong>Warnings:</strong>
                                                        {analysisResult.metadata.warnings.map((warning, index) => (
                                                            <Alert key={index} variant="warning" className="mt-1 mb-1 py-1">
                                                                <small>{warning}</small>
                                                            </Alert>
                                                        ))}
                                                    </div>
                                                )}

                                                {analysisResult.metadata.confidence_factors && (
                                                    <div className="mb-2">
                                                        <strong>Confidence Factors:</strong>
                                                        <ul className="mb-0 mt-1">
                                                            {analysisResult.metadata.confidence_factors.map((factor, index) => (
                                                                <li key={index} className="small">{factor}</li>
                                                            ))}
                                                        </ul>
                                                    </div>
                                                )}

                                                <div className="small text-muted">
                                                    <strong>Analysis Version:</strong> {analysisResult.metadata.analysis_version || 'N/A'}<br />
                                                    <strong>Next Review:</strong> {analysisResult.metadata.next_review ? new Date(analysisResult.metadata.next_review).toLocaleString() : 'N/A'}
                                                </div>
                                            </Card.Body>
                                        </Card>
                                    )}

                                    {/* ===========================================
                                PAIR INFO
                                =========================================== */}
                                    {analysisResult.pair_info && (
                                        <Card className="mb-3 bg-light">
                                            <Card.Header>
                                                <h6 className="mb-0">Technical Details</h6>
                                            </Card.Header>
                                            <Card.Body>
                                                <div className="small">
                                                    <div><strong>Address:</strong> <code>{analysisResult.pair_info.address}</code></div>
                                                    <div><strong>Chain:</strong> {analysisResult.pair_info.chain}</div>
                                                    <div><strong>DEX:</strong> {analysisResult.pair_info.dex}</div>
                                                    <div><strong>Source:</strong> {analysisResult.pair_info.source || 'N/A'}</div>
                                                    <div><strong>Analyzed At:</strong> {analysisResult.pair_info.analyzed_at ? new Date(analysisResult.pair_info.analyzed_at).toLocaleString() : 'N/A'}</div>
                                                    {analysisResult.pair_info.trace_id && (
                                                        <div><strong>Trace ID:</strong> <code>{analysisResult.pair_info.trace_id}</code></div>
                                                    )}
                                                </div>
                                            </Card.Body>
                                        </Card>
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
                        Close Analysis
                    </Button>
                    {analysisResult && !analysisResult.error && analysisResult.recommendation?.action === 'BUY' && (
                        <Button variant="success" onClick={() => {
                            // TODO: Implement execute trade functionality
                            alert('Trade execution functionality will be implemented next');
                        }}>
                            Execute Trade
                        </Button>
                    )}
                </Modal.Footer>
            </Modal>
        </>
    );
}