import { useState, useEffect, useRef } from 'react';
import { Card, Button, Table, Badge, Alert, Spinner } from 'react-bootstrap';
import { useDjangoData } from '../hooks/useDjangoApi';

export function LiveOpportunitiesCard() {
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [lastUpdate, setLastUpdate] = useState(null);
    const refreshIntervalRef = useRef(null);

    const {
        data: opportunities,
        loading,
        error,
        refresh
    } = useDjangoData('/api/v1/opportunities/live', []);

    const {
        data: stats,
        refresh: refreshStats
    } = useDjangoData('/api/v1/opportunities/stats', {});

    // Auto-refresh mechanism
    useEffect(() => {
        if (autoRefresh) {
            // Refresh every 15 seconds instead of 60
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

    const formatTimeAgo = (timestamp) => {
        if (!timestamp) return 'Never';
        const now = new Date();
        const then = new Date(timestamp);
        const diffMs = now - then;
        const diffSeconds = Math.floor(diffMs / 1000);

        if (diffSeconds < 60) return `${diffSeconds}s ago`;
        if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
        return `${Math.floor(diffSeconds / 3600)}h ago`;
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>🔴 Live Opportunities</strong>
                    {stats && (
                        <Badge bg="info">
                            {stats.total_opportunities || 0} found
                        </Badge>
                    )}
                </div>
                <div className="d-flex align-items-center gap-2">
                    <small className="text-muted">
                        {lastUpdate ? `Updated ${formatTimeAgo(lastUpdate)}` : 'No updates yet'}
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
                                Refreshing...
                            </>
                        ) : (
                            '🔄 Refresh'
                        )}
                    </Button>
                </div>
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" className="mb-3">
                        <strong>Error:</strong> {error.message || error}
                    </Alert>
                )}

                {/* Stats Summary */}
                {stats && (
                    <div className="row mb-3">
                        <div className="col-md-3 text-center">
                            <div className="fw-bold text-success">Total Opportunities</div>
                            <div className="fs-5">{stats.total_opportunities || 0}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold">High Liquidity</div>
                            <div className="fs-5">{stats.high_liquidity_opportunities || 0}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold">Active Chains</div>
                            <div className="fs-5">{stats.chains_active || 0}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold">Avg Liquidity</div>
                            <div className="fs-5">${(stats.average_liquidity_usd || 0).toLocaleString()}</div>
                        </div>
                    </div>
                )}

                {/* Opportunities Table */}
                {loading && !opportunities?.length && (
                    <div className="text-center py-4">
                        <Spinner animation="border" />
                        <div className="mt-2">Loading fresh opportunities...</div>
                    </div>
                )}

                {opportunities?.length > 0 ? (
                    <div className="table-responsive">
                        <Table striped hover size="sm">
                            <thead>
                                <tr>
                                    <th>Token Pair</th>
                                    <th>Chain</th>
                                    <th>DEX</th>
                                    <th>Liquidity</th>
                                    <th>Age</th>
                                    <th>Source</th>
                                    <th>Score</th>
                                </tr>
                            </thead>
                            <tbody>
                                {opportunities.slice(0, 10).map((opp, index) => (
                                    <tr key={`${opp.pair_address}-${index}`}>
                                        <td>
                                            <strong>{opp.token0_symbol || 'TOKEN'}</strong>
                                            <span className="text-muted">/</span>
                                            <span>{opp.token1_symbol || 'WETH'}</span>
                                        </td>
                                        <td>
                                            <Badge bg="secondary">{opp.chain}</Badge>
                                        </td>
                                        <td>
                                            <Badge bg="info">{opp.dex}</Badge>
                                        </td>
                                        <td>
                                            <span className={
                                                opp.estimated_liquidity_usd >= 100000 ? 'text-success fw-bold' :
                                                    opp.estimated_liquidity_usd >= 50000 ? 'text-warning' :
                                                        'text-danger'
                                            }>
                                                ${opp.estimated_liquidity_usd?.toLocaleString() || '0'}
                                            </span>
                                        </td>
                                        <td>
                                            <small>{formatTimeAgo(opp.timestamp)}</small>
                                        </td>
                                        <td>
                                            <Badge
                                                bg={opp.source === 'dexscreener' ? 'success' :
                                                    opp.source === 'mock' ? 'warning' : 'secondary'}
                                            >
                                                {opp.source}
                                            </Badge>
                                        </td>
                                        <td>
                                            <Badge bg={
                                                opp.opportunity_score >= 8 ? 'success' :
                                                    opp.opportunity_score >= 6 ? 'warning' : 'secondary'
                                            }>
                                                {opp.opportunity_score?.toFixed(1) || 'N/A'}
                                            </Badge>
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
    );
}