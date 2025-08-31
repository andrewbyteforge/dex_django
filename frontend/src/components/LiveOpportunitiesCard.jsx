import { useState, useEffect } from 'react';
import { Card, Button, Badge, Alert, Spinner, Table } from 'react-bootstrap';
import axios from 'axios';

export function LiveOpportunitiesCard() {
    const [opportunities, setOpportunities] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lastUpdated, setLastUpdated] = useState(null);

    const api = axios.create({
        baseURL: 'http://127.0.0.1:8000',
        timeout: 10000
    });

    const fetchOpportunities = async () => {
        setLoading(true);
        setError(null);

        try {
            console.log('Fetching live opportunities...');
            const [opportunitiesResponse, statsResponse] = await Promise.all([
                api.get('/api/v1/opportunities/live'),
                api.get('/api/v1/opportunities/stats')
            ]);

            console.log('Opportunities response:', opportunitiesResponse.data);
            console.log('Stats response:', statsResponse.data);

            if (opportunitiesResponse.data?.status === 'ok') {
                setOpportunities(opportunitiesResponse.data.opportunities || []);
                setLastUpdated(opportunitiesResponse.data.last_updated);
            }

            if (statsResponse.data?.status === 'ok') {
                setStats(statsResponse.data.stats);
            }
        } catch (err) {
            console.error('Failed to fetch live opportunities:', err);
            setError(err.response?.data?.error || err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleRefresh = async () => {
        try {
            console.log('Force refreshing opportunities...');
            const response = await api.post('/api/v1/opportunities/refresh');
            console.log('Refresh response:', response.data);

            if (response.data?.status === 'ok') {
                setOpportunities(response.data.opportunities || []);
                // Refresh stats too
                await fetchStats();
            }
        } catch (err) {
            console.error('Failed to refresh opportunities:', err);
            setError(err.response?.data?.error || err.message);
        }
    };

    const fetchStats = async () => {
        try {
            const response = await api.get('/api/v1/opportunities/stats');
            if (response.data?.status === 'ok') {
                setStats(response.data.stats);
            }
        } catch (err) {
            console.error('Failed to fetch stats:', err);
        }
    };

    useEffect(() => {
        fetchOpportunities();
        const interval = setInterval(fetchOpportunities, 60000);
        return () => clearInterval(interval);
    }, []);

    const formatTimeAgo = (timestamp) => {
        if (!timestamp) return 'Unknown';
        const diff = Date.now() - new Date(timestamp).getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) return `${hours}h ${minutes % 60}m ago`;
        if (minutes > 0) return `${minutes}m ago`;
        return 'Just now';
    };

    const getOpportunityBadge = (opportunity) => {
        const score = opportunity.opportunity_score || 0;
        const liquidity = opportunity.estimated_liquidity_usd || 0;

        if (score >= 15 && liquidity >= 100000) return { bg: 'success', text: 'HIGH' };
        if (score >= 10 && liquidity >= 50000) return { bg: 'warning', text: 'MED' };
        if (score >= 5) return { bg: 'info', text: 'LOW' };
        return { bg: 'secondary', text: 'MIN' };
    };

    const getChainColor = (chain) => {
        const colors = {
            ethereum: 'primary',
            bsc: 'warning',
            polygon: 'success',
            base: 'info'
        };
        return colors[chain] || 'secondary';
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>Live Opportunities</strong>
                    <Badge bg="success">LIVE</Badge>
                </div>
                <div className="d-flex gap-2">
                    <Button
                        variant="outline-primary"
                        size="sm"
                        onClick={handleRefresh}
                        disabled={loading}
                    >
                        {loading ? <Spinner size="sm" /> : 'Refresh'}
                    </Button>
                </div>
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" dismissible onClose={() => setError(null)}>
                        <strong>Error:</strong> {error}
                    </Alert>
                )}

                {/* Debug Info */}
                <div className="mb-3 small text-muted">
                    Loading: {loading ? 'Yes' : 'No'} |
                    Opportunities: {opportunities.length} |
                    Last Updated: {lastUpdated || 'Never'}
                </div>

                {/* Stats Summary */}
                {stats && (
                    <div className="row mb-4">
                        <div className="col-md-3 text-center">
                            <div className="fw-bold text-primary">Total Found</div>
                            <div className="fs-5">{stats.total_opportunities}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold text-success">High Liquidity</div>
                            <div className="fs-5">{stats.high_liquidity_opportunities}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold text-info">Active Chains</div>
                            <div className="fs-5">{stats.chains_active}</div>
                        </div>
                        <div className="col-md-3 text-center">
                            <div className="fw-bold text-secondary">Avg Liquidity</div>
                            <div className="fs-6">${stats.average_liquidity_usd?.toLocaleString()}</div>
                        </div>
                    </div>
                )}

                {/* Opportunities Table */}
                {loading && opportunities.length === 0 && (
                    <div className="text-center py-4">
                        <Spinner />
                        <div className="mt-2">Scanning live DEX data...</div>
                    </div>
                )}

                {opportunities.length === 0 && !loading ? (
                    <div className="text-center py-4 text-muted">
                        No live opportunities detected. Click Refresh to fetch from DexScreener API.
                    </div>
                ) : (
                    <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
                        <Table striped hover size="sm">
                            <thead className="table-dark sticky-top">
                                <tr>
                                    <th>Score</th>
                                    <th>Chain</th>
                                    <th>DEX</th>
                                    <th>Token Pair</th>
                                    <th>Liquidity</th>
                                    <th>Age</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {opportunities.map((opp, idx) => {
                                    const badge = getOpportunityBadge(opp);
                                    return (
                                        <tr key={`${opp.pair_address}-${idx}`}>
                                            <td>
                                                <Badge bg={badge.bg}>
                                                    {badge.text}
                                                </Badge>
                                                <div className="small text-muted">
                                                    {opp.opportunity_score?.toFixed(1)}
                                                </div>
                                            </td>
                                            <td>
                                                <Badge bg={getChainColor(opp.chain)}>
                                                    {opp.chain?.toUpperCase()}
                                                </Badge>
                                            </td>
                                            <td>
                                                <Badge bg="secondary" className="text-uppercase">
                                                    {opp.dex?.replace('_', ' ')}
                                                </Badge>
                                            </td>
                                            <td>
                                                <div>
                                                    <strong>
                                                        {opp.token0_symbol}/
                                                        <span className="text-primary">{opp.token1_symbol}</span>
                                                    </strong>
                                                </div>
                                                <div className="small text-muted">
                                                    {opp.pair_address?.slice(0, 8)}...
                                                </div>
                                            </td>
                                            <td>
                                                <div className={
                                                    opp.estimated_liquidity_usd >= 100000 ? 'text-success fw-bold' :
                                                        opp.estimated_liquidity_usd >= 50000 ? 'text-warning fw-bold' :
                                                            opp.estimated_liquidity_usd >= 10000 ? 'text-info' : 'text-muted'
                                                }>
                                                    ${opp.estimated_liquidity_usd?.toLocaleString()}
                                                </div>
                                            </td>
                                            <td className="small">
                                                <div>
                                                    {formatTimeAgo(opp.timestamp)}
                                                </div>
                                            </td>
                                            <td>
                                                <Button
                                                    size="sm"
                                                    variant="outline-success"
                                                    onClick={() => {
                                                        console.log('Analyze opportunity:', opp);
                                                    }}
                                                >
                                                    Analyze
                                                </Button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </Table>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
}