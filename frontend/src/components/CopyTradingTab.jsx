// APP: frontend
// FILE: frontend/src/components/CopyTradingTab.jsx
import { useState, useEffect } from 'react';
import {
    Row, Col, Card, Table, Button, Modal, Form, Badge, Alert,
    Spinner, ProgressBar, Tabs, Tab, InputGroup, Dropdown,
    OverlayTrigger, Tooltip
} from 'react-bootstrap';
// Comment out the WalletDiscoveryPanel import temporarily
// import { WalletDiscoveryPanel } from './WalletDiscoveryPanel.jsx';

// API Configuration - Fixed to point to backend
const API_BASE = 'http://127.0.0.1:8000';

export function CopyTradingTab() {
    // State management
    const [followedTraders, setFollowedTraders] = useState([]);
    const [recentTrades, setRecentTrades] = useState([]);
    const [systemStatus, setSystemStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Modal states
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showDetailsModal, setShowDetailsModal] = useState(false);
    const [selectedTrader, setSelectedTrader] = useState(null);

    // Tab state
    const [activeTabKey, setActiveTabKey] = useState('traders');

    // Form state for adding/editing traders
    const [formData, setFormData] = useState({
        wallet_address: '',
        trader_name: '',
        description: '',
        chain: 'ethereum',
        copy_mode: 'percentage',
        copy_percentage: 3.0,
        fixed_amount_usd: 100,
        max_position_usd: 1000,
        min_trade_value_usd: 50,
        max_slippage_bps: 300,
        allowed_chains: ['ethereum'],
        copy_buy_only: false,
        copy_sell_only: false
    });

    // Load data on component mount
    useEffect(() => {
        loadCopyTradingData();
        const interval = setInterval(loadCopyTradingData, 30000); // Refresh every 30s
        return () => clearInterval(interval);
    }, []);

    const loadCopyTradingData = async () => {
        try {
            setLoading(true);

            // Load followed traders - Fixed API call
            try {
                const tradersResponse = await fetch(`${API_BASE}/api/v1/copy/traders`);
                if (tradersResponse.ok) {
                    const tradersData = await tradersResponse.json();
                    setFollowedTraders(tradersData.data || []);
                } else {
                    console.warn('Copy trading endpoints not available, using mock data');
                    setFollowedTraders([]);
                }
            } catch (err) {
                console.warn('Traders API not available:', err);
                setFollowedTraders([]);
            }

            // Load recent copy trades - Fixed API call
            try {
                const tradesResponse = await fetch(`${API_BASE}/api/v1/copy/trades`);
                if (tradesResponse.ok) {
                    const tradesData = await tradesResponse.json();
                    setRecentTrades(tradesData.data || []);
                } else {
                    setRecentTrades([]);
                }
            } catch (err) {
                console.warn('Trades API not available:', err);
                setRecentTrades([]);
            }

            // Load system status - Fixed API call
            try {
                const statusResponse = await fetch(`${API_BASE}/api/v1/copy/status`);
                if (statusResponse.ok) {
                    const statusData = await statusResponse.json();
                    setSystemStatus(statusData);
                } else {
                    // Mock status for testing
                    setSystemStatus({
                        is_enabled: false,
                        monitoring_active: false,
                        followed_traders_count: 0,
                        active_copies_today: 0,
                        total_copies: 0,
                        win_rate_pct: 0.0,
                        total_pnl_usd: "0.00"
                    });
                }
            } catch (err) {
                console.warn('Status API not available:', err);
                setSystemStatus({
                    is_enabled: false,
                    monitoring_active: false,
                    followed_traders_count: 0,
                    active_copies_today: 0,
                    total_copies: 0,
                    win_rate_pct: 0.0,
                    total_pnl_usd: "0.00"
                });
            }

            setError(null);
        } catch (err) {
            console.error('Failed to load copy trading data:', err);
            setError('Failed to load copy trading data: ' + err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAddTrader = async (e) => {
        e.preventDefault();

        try {
            // Validate required fields
            if (!formData.wallet_address || !formData.chain) {
                setError('Wallet address and chain are required');
                return;
            }

            // Validate wallet address format
            if (!formData.wallet_address.startsWith('0x') || formData.wallet_address.length !== 42) {
                setError('Invalid wallet address format. Must be 42 characters starting with 0x');
                return;
            }

            // Fixed API call with correct base URL
            const response = await fetch(`${API_BASE}/api/v1/copy/traders`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    wallet_address: formData.wallet_address.toLowerCase(),
                    trader_name: formData.trader_name || `Trader ${formData.wallet_address.slice(0, 8)}`,
                    description: formData.description || '',
                    chain: formData.chain,
                    copy_mode: formData.copy_mode,
                    copy_percentage: parseFloat(formData.copy_percentage),
                    fixed_amount_usd: formData.copy_mode === 'fixed_amount' ? parseFloat(formData.fixed_amount_usd) : null,
                    max_position_usd: parseFloat(formData.max_position_usd),
                    min_trade_value_usd: parseFloat(formData.min_trade_value_usd),
                    max_slippage_bps: parseInt(formData.max_slippage_bps),
                    allowed_chains: formData.allowed_chains,
                    copy_buy_only: formData.copy_buy_only,
                    copy_sell_only: formData.copy_sell_only
                })
            });

            let data;
            const contentType = response.headers.get("content-type");

            if (contentType && contentType.includes("application/json")) {
                data = await response.json();
            } else {
                const text = await response.text();
                console.error('Non-JSON response:', text);
                throw new Error(`Server returned non-JSON response: ${response.status} ${response.statusText}`);
            }

            if (!response.ok) {
                throw new Error(data.error || data.message || `HTTP error! status: ${response.status}`);
            }

            setShowAddModal(false);
            resetForm();
            loadCopyTradingData();
            setError(null);

        } catch (err) {
            console.error('Add trader error:', err);
            setError(err.message || 'Failed to add trader');
        }
    };

    const handleEditTrader = async (e) => {
        e.preventDefault();

        try {
            // Fixed API call with correct base URL
            const response = await fetch(`${API_BASE}/api/v1/copy/traders/${selectedTrader.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update trader');
            }

            setShowEditModal(false);
            setSelectedTrader(null);
            resetForm();
            loadCopyTradingData();
        } catch (err) {
            setError(err.message);
        }
    };

    const handleDeleteTrader = async (trader) => {
        if (!window.confirm(`Are you sure you want to stop following ${trader.trader_name || trader.wallet_address}?`)) {
            return;
        }

        try {
            // Fixed API call with correct base URL
            const response = await fetch(`${API_BASE}/api/v1/copy/traders/${trader.id}`, {
                method: 'DELETE'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to remove trader');
            }

            loadCopyTradingData();
        } catch (err) {
            setError(err.message);
        }
    };

    const handleToggleTraderStatus = async (trader, newStatus) => {
        try {
            // Fixed API call with correct base URL
            const response = await fetch(`${API_BASE}/api/v1/copy/traders/${trader.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update trader status');
            }

            loadCopyTradingData();
        } catch (err) {
            setError(err.message);
        }
    };

    const resetForm = () => {
        setFormData({
            wallet_address: '',
            trader_name: '',
            description: '',
            chain: 'ethereum',
            copy_mode: 'percentage',
            copy_percentage: 3.0,
            fixed_amount_usd: 100,
            max_position_usd: 1000,
            min_trade_value_usd: 50,
            max_slippage_bps: 300,
            allowed_chains: ['ethereum'],
            copy_buy_only: false,
            copy_sell_only: false
        });
    };

    const openEditModal = (trader) => {
        setSelectedTrader(trader);
        setFormData({
            wallet_address: trader.wallet_address,
            trader_name: trader.trader_name || '',
            description: trader.description || '',
            chain: trader.chain,
            copy_mode: trader.copy_mode,
            copy_percentage: trader.copy_percentage,
            fixed_amount_usd: trader.fixed_amount_usd || 100,
            max_position_usd: trader.max_position_usd,
            min_trade_value_usd: trader.min_trade_value_usd || 50,
            max_slippage_bps: trader.max_slippage_bps,
            allowed_chains: trader.allowed_chains,
            copy_buy_only: trader.copy_buy_only,
            copy_sell_only: trader.copy_sell_only
        });
        setShowEditModal(true);
    };

    const getTradeQualityScore = (trader) => {
        // Advanced trade quality scoring algorithm
        const winRate = trader.win_rate || 0;
        const totalTrades = trader.total_copies || 0;
        const pnl = parseFloat(trader.total_pnl_usd || 0);

        // Base score from win rate (0-40 points)
        let score = Math.min(winRate * 0.4, 40);

        // Activity bonus (0-20 points)
        if (totalTrades > 50) score += 20;
        else if (totalTrades > 20) score += 15;
        else if (totalTrades > 10) score += 10;
        else if (totalTrades > 5) score += 5;

        // Profitability bonus (0-25 points)
        if (pnl > 1000) score += 25;
        else if (pnl > 500) score += 20;
        else if (pnl > 200) score += 15;
        else if (pnl > 50) score += 10;
        else if (pnl > 0) score += 5;

        // Consistency bonus (0-15 points)
        if (winRate > 70 && totalTrades > 10) score += 15;
        else if (winRate > 60 && totalTrades > 5) score += 10;
        else if (winRate > 50) score += 5;

        return Math.min(Math.round(score), 100);
    };

    const getQualityBadge = (score) => {
        if (score >= 80) return { variant: 'success', text: 'Excellent' };
        if (score >= 60) return { variant: 'primary', text: 'Good' };
        if (score >= 40) return { variant: 'warning', text: 'Average' };
        return { variant: 'danger', text: 'Poor' };
    };

    if (loading && followedTraders.length === 0) {
        return (
            <div className="text-center py-5">
                <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading...</span>
                </Spinner>
                <div className="mt-2">Loading copy trading data...</div>
            </div>
        );
    }

    return (
        <div>
            {error && (
                <Alert variant="danger" dismissible onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* System Status */}
            {systemStatus && (
                <Row className="mb-4">
                    <Col>
                        <Card>
                            <Card.Header className="d-flex justify-content-between align-items-center">
                                <h5 className="mb-0">📈 Copy Trading System Status</h5>
                                <Badge bg={systemStatus.monitoring_active ? 'success' : 'secondary'}>
                                    {systemStatus.monitoring_active ? 'Active' : 'Inactive'}
                                </Badge>
                            </Card.Header>
                            <Card.Body>
                                <Row>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-primary">{systemStatus.followed_traders_count}</div>
                                            <div className="text-muted small">Followed Traders</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-success">{systemStatus.total_copies}</div>
                                            <div className="text-muted small">Total Copies</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-info">{(systemStatus.win_rate_pct || 0).toFixed(1)}%</div>
                                            <div className="text-muted small">Win Rate</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className={`h4 ${parseFloat(systemStatus.total_pnl_usd) >= 0 ? 'text-success' : 'text-danger'}`}>
                                                ${parseFloat(systemStatus.total_pnl_usd).toFixed(2)}
                                            </div>
                                            <div className="text-muted small">Total P&L</div>
                                        </div>
                                    </Col>
                                </Row>
                            </Card.Body>
                        </Card>
                    </Col>
                </Row>
            )}

            {/* Main Content Tabs */}
            <Tabs activeKey={activeTabKey} onSelect={(k) => setActiveTabKey(k)} className="mb-3">
                {/* Followed Traders Tab */}
                <Tab eventKey="traders" title="👥 Followed Traders">
                    <Card>
                        <Card.Header className="d-flex justify-content-between align-items-center">
                            <h5 className="mb-0">Followed Traders</h5>
                            <div className="d-flex gap-2">
                                <Button variant="success" onClick={() => setShowAddModal(true)}>
                                    ➕ Add Manually
                                </Button>
                                <Button variant="primary" onClick={() => setActiveTabKey('discovery')}>
                                    🔍 Auto Discover
                                </Button>
                            </div>
                        </Card.Header>
                        <Card.Body>
                            {followedTraders.length === 0 ? (
                                <div className="text-center py-4 text-muted">
                                    <div className="h4">🎯</div>
                                    <p>No traders being followed yet.</p>
                                    <Button variant="outline-primary" onClick={() => setShowAddModal(true)}>
                                        Add Your First Trader
                                    </Button>
                                </div>
                            ) : (
                                <Table responsive hover>
                                    <thead>
                                        <tr>
                                            <th>Trader</th>
                                            <th>Quality Score</th>
                                            <th>Performance</th>
                                            <th>Copy Settings</th>
                                            <th>Status</th>
                                            <th>Last Activity</th>
                                            <th>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {followedTraders.map((trader) => {
                                            const qualityScore = getTradeQualityScore(trader);
                                            const qualityBadge = getQualityBadge(qualityScore);

                                            return (
                                                <tr key={trader.id}>
                                                    <td>
                                                        <div>
                                                            <strong>{trader.trader_name || 'Unnamed Trader'}</strong>
                                                            <div className="small text-muted font-monospace">
                                                                {trader.wallet_address.slice(0, 8)}...{trader.wallet_address.slice(-6)}
                                                            </div>
                                                            <Badge bg="secondary" className="small">
                                                                {trader.chain}
                                                            </Badge>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <div className="d-flex align-items-center">
                                                            <ProgressBar
                                                                now={qualityScore}
                                                                variant={qualityBadge.variant}
                                                                style={{ width: '60px', height: '8px' }}
                                                                className="me-2"
                                                            />
                                                            <Badge bg={qualityBadge.variant}>
                                                                {qualityScore}/100 {qualityBadge.text}
                                                            </Badge>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <div className="small">
                                                            <div>📊 {trader.total_copies || 0} trades</div>
                                                            <div>📈 {(trader.win_rate || 0).toFixed(1)}% win rate</div>
                                                            <div className={parseFloat(trader.total_pnl_usd || 0) >= 0 ? 'text-success' : 'text-danger'}>
                                                                💰 ${parseFloat(trader.total_pnl_usd || 0).toFixed(2)}
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <div className="small">
                                                            <div>
                                                                {trader.copy_mode === 'percentage'
                                                                    ? `${trader.copy_percentage}% copy`
                                                                    : `$${trader.fixed_amount_usd} fixed`
                                                                }
                                                            </div>
                                                            <div>Max: ${trader.max_position_usd}</div>
                                                            <div>{trader.max_slippage_bps / 100}% slippage</div>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <Dropdown>
                                                            <Dropdown.Toggle
                                                                variant={trader.status === 'active' ? 'success' : 'warning'}
                                                                size="sm"
                                                            >
                                                                {trader.status}
                                                            </Dropdown.Toggle>
                                                            <Dropdown.Menu>
                                                                <Dropdown.Item
                                                                    onClick={() => handleToggleTraderStatus(trader, 'active')}
                                                                >
                                                                    ✅ Active
                                                                </Dropdown.Item>
                                                                <Dropdown.Item
                                                                    onClick={() => handleToggleTraderStatus(trader, 'paused')}
                                                                >
                                                                    ⏸️ Paused
                                                                </Dropdown.Item>
                                                                <Dropdown.Item
                                                                    onClick={() => handleToggleTraderStatus(trader, 'blacklisted')}
                                                                >
                                                                    🚫 Blacklisted
                                                                </Dropdown.Item>
                                                            </Dropdown.Menu>
                                                        </Dropdown>
                                                    </td>
                                                    <td>
                                                        <div className="small text-muted">
                                                            {trader.last_activity_at
                                                                ? new Date(trader.last_activity_at).toLocaleDateString()
                                                                : 'No activity'
                                                            }
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <div className="d-flex gap-1">
                                                            <OverlayTrigger
                                                                placement="top"
                                                                overlay={<Tooltip>View Details</Tooltip>}
                                                            >
                                                                <Button
                                                                    variant="outline-info"
                                                                    size="sm"
                                                                    onClick={() => {
                                                                        setSelectedTrader(trader);
                                                                        setShowDetailsModal(true);
                                                                    }}
                                                                >
                                                                    👁️
                                                                </Button>
                                                            </OverlayTrigger>

                                                            <OverlayTrigger
                                                                placement="top"
                                                                overlay={<Tooltip>Edit Settings</Tooltip>}
                                                            >
                                                                <Button
                                                                    variant="outline-primary"
                                                                    size="sm"
                                                                    onClick={() => openEditModal(trader)}
                                                                >
                                                                    ✏️
                                                                </Button>
                                                            </OverlayTrigger>

                                                            <OverlayTrigger
                                                                placement="top"
                                                                overlay={<Tooltip>Remove Trader</Tooltip>}
                                                            >
                                                                <Button
                                                                    variant="outline-danger"
                                                                    size="sm"
                                                                    onClick={() => handleDeleteTrader(trader)}
                                                                >
                                                                    🗑️
                                                                </Button>
                                                            </OverlayTrigger>
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </Table>
                            )}
                        </Card.Body>
                    </Card>
                </Tab>

                {/* Wallet Discovery Tab - Temporarily disabled */}
                <Tab eventKey="discovery" title="🔍 Auto Discovery">
                    <Card>
                        <Card.Body>
                            <div className="text-center py-4 text-muted">
                                <div className="h4">🔍</div>
                                <p>Wallet discovery feature coming soon...</p>
                            </div>
                        </Card.Body>
                    </Card>
                </Tab>

                {/* Recent Copy Trades Tab */}
                <Tab eventKey="trades" title="📋 Recent Trades">
                    <Card>
                        <Card.Header>
                            <h5 className="mb-0">Recent Copy Trades</h5>
                        </Card.Header>
                        <Card.Body>
                            {recentTrades.length === 0 ? (
                                <div className="text-center py-4 text-muted">
                                    <div className="h4">📈</div>
                                    <p>No copy trades executed yet.</p>
                                </div>
                            ) : (
                                <Table responsive hover>
                                    <thead>
                                        <tr>
                                            <th>Time</th>
                                            <th>Trader</th>
                                            <th>Token</th>
                                            <th>Action</th>
                                            <th>Amount</th>
                                            <th>Status</th>
                                            <th>P&L</th>
                                            <th>Delay</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {recentTrades.map((trade) => (
                                            <tr key={trade.id}>
                                                <td className="small">
                                                    {new Date(trade.created_at).toLocaleString()}
                                                </td>
                                                <td>
                                                    <div className="small">
                                                        {trade.trader_address.slice(0, 8)}...
                                                    </div>
                                                </td>
                                                <td>
                                                    <div className="d-flex align-items-center">
                                                        <Badge bg="secondary" className="me-2">
                                                            {trade.chain}
                                                        </Badge>
                                                        <strong>{trade.token_symbol}</strong>
                                                    </div>
                                                </td>
                                                <td>
                                                    <Badge bg={trade.action === 'buy' ? 'success' : 'danger'}>
                                                        {trade.action.toUpperCase()}
                                                    </Badge>
                                                </td>
                                                <td>
                                                    ${parseFloat(trade.copy_amount_usd).toFixed(2)}
                                                </td>
                                                <td>
                                                    <Badge bg={
                                                        trade.status === 'executed' ? 'success' :
                                                            trade.status === 'failed' ? 'danger' :
                                                                trade.status === 'pending' ? 'warning' : 'secondary'
                                                    }>
                                                        {trade.status}
                                                    </Badge>
                                                </td>
                                                <td>
                                                    {trade.pnl_usd ? (
                                                        <span className={parseFloat(trade.pnl_usd) >= 0 ? 'text-success' : 'text-danger'}>
                                                            ${parseFloat(trade.pnl_usd).toFixed(2)}
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted">-</span>
                                                    )}
                                                </td>
                                                <td>
                                                    {trade.execution_delay_seconds ? (
                                                        <span className="small">
                                                            {trade.execution_delay_seconds}s
                                                        </span>
                                                    ) : (
                                                        <span className="text-muted">-</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </Table>
                            )}
                        </Card.Body>
                    </Card>
                </Tab>

                {/* Analytics Tab */}
                <Tab eventKey="analytics" title="📊 Analytics">
                    <Card>
                        <Card.Header>
                            <h5 className="mb-0">Performance Analytics</h5>
                        </Card.Header>
                        <Card.Body>
                            <Row>
                                <Col md={6}>
                                    <h6>Top Performing Traders</h6>
                                    {followedTraders
                                        .sort((a, b) => getTradeQualityScore(b) - getTradeQualityScore(a))
                                        .slice(0, 5)
                                        .map(trader => {
                                            const score = getTradeQualityScore(trader);
                                            const badge = getQualityBadge(score);
                                            return (
                                                <div key={trader.id} className="d-flex justify-content-between align-items-center mb-2 p-2 border rounded">
                                                    <div>
                                                        <strong>{trader.trader_name || 'Unnamed'}</strong>
                                                        <div className="small text-muted">
                                                            {trader.total_copies} trades • {trader.win_rate.toFixed(1)}% win rate
                                                        </div>
                                                    </div>
                                                    <Badge bg={badge.variant}>
                                                        {score}/100
                                                    </Badge>
                                                </div>
                                            );
                                        })
                                    }
                                </Col>
                                <Col md={6}>
                                    <h6>Recent Performance</h6>
                                    <div className="text-muted">
                                        Performance charts and analytics will be displayed here.
                                    </div>
                                </Col>
                            </Row>
                        </Card.Body>
                    </Card>
                </Tab>
            </Tabs>

            {/* Add/Edit Trader Modal */}
            <TraderFormModal
                show={showAddModal || showEditModal}
                isEdit={showEditModal}
                formData={formData}
                setFormData={setFormData}
                onSubmit={showEditModal ? handleEditTrader : handleAddTrader}
                onHide={() => {
                    setShowAddModal(false);
                    setShowEditModal(false);
                    setSelectedTrader(null);
                    resetForm();
                }}
            />

            {/* Trader Details Modal */}
            <TraderDetailsModal
                show={showDetailsModal}
                trader={selectedTrader}
                onHide={() => {
                    setShowDetailsModal(false);
                    setSelectedTrader(null);
                }}
            />
        </div>
    );
}

// Trader Form Modal Component
function TraderFormModal({ show, isEdit, formData, setFormData, onSubmit, onHide }) {
    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>
                    {isEdit ? '✏️ Edit Trader' : '➕ Add New Trader'}
                </Modal.Title>
            </Modal.Header>
            <Form onSubmit={onSubmit}>
                <Modal.Body>
                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>Wallet Address *</Form.Label>
                                <Form.Control
                                    type="text"
                                    placeholder="0x..."
                                    value={formData.wallet_address}
                                    onChange={(e) => setFormData({ ...formData, wallet_address: e.target.value })}
                                    required
                                    disabled={isEdit}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Label>Trader Name</Form.Label>
                                <Form.Control
                                    type="text"
                                    placeholder="e.g., DeFi Alpha Hunter"
                                    value={formData.trader_name}
                                    onChange={(e) => setFormData({ ...formData, trader_name: e.target.value })}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Form.Group className="mb-3">
                        <Form.Label>Description</Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            placeholder="Optional description or notes about this trader"
                            value={formData.description}
                            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        />
                    </Form.Group>

                    <Row>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>Chain *</Form.Label>
                                <Form.Select
                                    value={formData.chain}
                                    onChange={(e) => setFormData({ ...formData, chain: e.target.value })}
                                    disabled={isEdit}
                                >
                                    <option value="ethereum">Ethereum</option>
                                    <option value="bsc">BSC</option>
                                    <option value="base">Base</option>
                                    <option value="polygon">Polygon</option>
                                    <option value="arbitrum">Arbitrum</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>Copy Mode</Form.Label>
                                <Form.Select
                                    value={formData.copy_mode}
                                    onChange={(e) => setFormData({ ...formData, copy_mode: e.target.value })}
                                >
                                    <option value="percentage">Percentage</option>
                                    <option value="fixed_amount">Fixed Amount</option>
                                    <option value="proportional">Proportional</option>
                                </Form.Select>
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>
                                    {formData.copy_mode === 'percentage' ? 'Copy %' : 'Fixed Amount USD'}
                                </Form.Label>
                                <Form.Control
                                    type="number"
                                    step="0.1"
                                    min={formData.copy_mode === 'percentage' ? '0.1' : '10'}
                                    max={formData.copy_mode === 'percentage' ? '50' : '10000'}
                                    value={formData.copy_mode === 'percentage' ? formData.copy_percentage : formData.fixed_amount_usd}
                                    onChange={(e) => {
                                        if (formData.copy_mode === 'percentage') {
                                            setFormData({ ...formData, copy_percentage: parseFloat(e.target.value) });
                                        } else {
                                            setFormData({ ...formData, fixed_amount_usd: parseFloat(e.target.value) });
                                        }
                                    }}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>Max Position USD</Form.Label>
                                <Form.Control
                                    type="number"
                                    step="50"
                                    min="50"
                                    max="50000"
                                    value={formData.max_position_usd}
                                    onChange={(e) => setFormData({ ...formData, max_position_usd: parseFloat(e.target.value) })}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>Min Trade Value USD</Form.Label>
                                <Form.Control
                                    type="number"
                                    step="10"
                                    min="10"
                                    max="5000"
                                    value={formData.min_trade_value_usd}
                                    onChange={(e) => setFormData({ ...formData, min_trade_value_usd: parseFloat(e.target.value) || 50 })}
                                />
                                <Form.Text className="text-muted">
                                    Minimum trade value to copy (default: $50)
                                </Form.Text>
                            </Form.Group>
                        </Col>
                        <Col md={4}>
                            <Form.Group className="mb-3">
                                <Form.Label>Max Slippage %</Form.Label>
                                <Form.Control
                                    type="number"
                                    step="0.1"
                                    min="0.5"
                                    max="10"
                                    value={formData.max_slippage_bps / 100}
                                    onChange={(e) => setFormData({ ...formData, max_slippage_bps: parseFloat(e.target.value) * 100 })}
                                />
                            </Form.Group>
                        </Col>
                    </Row>

                    <Row>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Check
                                    type="checkbox"
                                    label="Copy buy orders only"
                                    checked={formData.copy_buy_only}
                                    onChange={(e) => setFormData({ ...formData, copy_buy_only: e.target.checked, copy_sell_only: false })}
                                />
                            </Form.Group>
                        </Col>
                        <Col md={6}>
                            <Form.Group className="mb-3">
                                <Form.Check
                                    type="checkbox"
                                    label="Copy sell orders only"
                                    checked={formData.copy_sell_only}
                                    onChange={(e) => setFormData({ ...formData, copy_sell_only: e.target.checked, copy_buy_only: false })}
                                />
                            </Form.Group>
                        </Col>
                    </Row>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={onHide}>
                        Cancel
                    </Button>
                    <Button variant="primary" type="submit">
                        {isEdit ? 'Update Trader' : 'Add Trader'}
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
}

// Trader Details Modal Component
function TraderDetailsModal({ show, trader, onHide }) {
    if (!trader) return null;

    const qualityScore = ((trader.win_rate || 0) * 0.4 + Math.min((trader.total_copies || 0) * 0.2, 20) + Math.min(Math.max(parseFloat(trader.total_pnl_usd || 0) / 10, 0), 25));
    const badge = qualityScore >= 80 ? 'success' : qualityScore >= 60 ? 'primary' : qualityScore >= 40 ? 'warning' : 'danger';

    return (
        <Modal show={show} onHide={onHide} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>👤 Trader Details</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Row>
                    <Col md={6}>
                        <h6>Basic Information</h6>
                        <p><strong>Name:</strong> {trader.trader_name || 'Unnamed Trader'}</p>
                        <p><strong>Address:</strong> <code>{trader.wallet_address}</code></p>
                        <p><strong>Chain:</strong> <Badge bg="secondary">{trader.chain}</Badge></p>
                        <p><strong>Status:</strong> <Badge bg={trader.status === 'active' ? 'success' : 'warning'}>{trader.status}</Badge></p>
                        {trader.description && <p><strong>Description:</strong> {trader.description}</p>}
                    </Col>
                    <Col md={6}>
                        <h6>Performance Metrics</h6>
                        <p><strong>Quality Score:</strong> <Badge bg={badge}>{Math.round(qualityScore)}/100</Badge></p>
                        <p><strong>Total Trades:</strong> {trader.total_copies}</p>
                        <p><strong>Win Rate:</strong> {trader.win_rate.toFixed(1)}%</p>
                        <p><strong>Total P&L:</strong>
                            <span className={parseFloat(trader.total_pnl_usd) >= 0 ? 'text-success' : 'text-danger'}>
                                ${parseFloat(trader.total_pnl_usd).toFixed(2)}
                            </span>
                        </p>
                        <p><strong>Last Activity:</strong> {trader.last_activity_at ? new Date(trader.last_activity_at).toLocaleDateString() : 'No activity'}</p>
                    </Col>
                </Row>

                <hr />

                <Row>
                    <Col md={6}>
                        <h6>Copy Settings</h6>
                        <p><strong>Copy Mode:</strong> {trader.copy_mode}</p>
                        <p><strong>Copy Rate:</strong> {trader.copy_mode === 'percentage' ? `${trader.copy_percentage}%` : `$${trader.fixed_amount_usd}`}</p>
                        <p><strong>Max Position:</strong> ${trader.max_position_usd}</p>
                        <p><strong>Min Trade Value:</strong> ${trader.min_trade_value_usd || 0}</p>
                    </Col>
                    <Col md={6}>
                        <h6>Risk Controls</h6>
                        <p><strong>Max Slippage:</strong> {(trader.max_slippage_bps / 100).toFixed(1)}%</p>
                        <p><strong>Allowed Chains:</strong> {(trader.allowed_chains || [trader.chain]).join(', ')}</p>
                        <p><strong>Buy Only:</strong> {trader.copy_buy_only ? '✅' : '❌'}</p>
                        <p><strong>Sell Only:</strong> {trader.copy_sell_only ? '✅' : '❌'}</p>
                    </Col>
                </Row>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={onHide}>
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
}