// APP: frontend
// FILE: frontend/src/components/CopyTradingTab.jsx
import { useState, useEffect } from 'react';
import {
    Row, Col, Card, Table, Button, Modal, Form, Badge, Alert,
    Spinner, ProgressBar, Tabs, Tab, InputGroup, Dropdown,
    OverlayTrigger, Tooltip, ButtonGroup
} from 'react-bootstrap';

// API Configuration
const API_BASE = 'http://127.0.0.1:8000';

// API utility functions
const apiCall = async (endpoint, options = {}) => {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error(`API Error ${endpoint}:`, error);
        throw error;
    }
};

// API service functions
const copyTradingApi = {
    async getStatus() {
        return await apiCall('/api/v1/copy/status');
    },

    async getTraders() {
        return await apiCall('/api/v1/copy/traders');
    },

    async addTrader(traderData) {
        return await apiCall('/api/v1/copy/traders', {
            method: 'POST',
            body: JSON.stringify(traderData)
        });
    },

    async removeTrader(traderId) {
        return await apiCall(`/api/v1/copy/traders/${traderId}`, {
            method: 'DELETE'
        });
    },

    async getTrades(filters = {}) {
        const params = new URLSearchParams(filters);
        return await apiCall(`/api/v1/copy/trades?${params}`);
    }
};

const discoveryApi = {
    async getStatus() {
        return await apiCall('/api/v1/copy/discovery/status');
    },

    async discoverTraders(config) {
        return await apiCall('/api/v1/copy/discovery/discover-traders', {
            method: 'POST',
            body: JSON.stringify(config)
        });
    },

    async analyzeWallet(walletData) {
        return await apiCall('/api/v1/copy/discovery/analyze-wallet', {
            method: 'POST',
            body: JSON.stringify(walletData)
        });
    }
};

export function CopyTradingTab() {
    // State management
    const [followedTraders, setFollowedTraders] = useState([]);
    const [recentTrades, setRecentTrades] = useState([]);
    const [systemStatus, setSystemStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Discovery states
    const [discoveryStatus, setDiscoveryStatus] = useState(null);
    const [discoveredWallets, setDiscoveredWallets] = useState([]);
    const [discoveryLoading, setDiscoveryLoading] = useState(false);
    const [discoveryError, setDiscoveryError] = useState(null);

    // Discovery configuration
    const [discoveryConfig, setDiscoveryConfig] = useState({
        chains: ['ethereum', 'bsc'],
        limit: 20,
        min_volume_usd: 50000,
        days_back: 30,
        auto_add_threshold: 80.0
    });

    // Manual wallet analysis
    const [manualAnalysis, setManualAnalysis] = useState({
        address: '',
        chain: 'ethereum',
        days_back: 30
    });

    // Modal states
    const [showAddModal, setShowAddModal] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showDetailsModal, setShowDetailsModal] = useState(false);
    const [showAnalysisModal, setShowAnalysisModal] = useState(false);
    const [selectedTrader, setSelectedTrader] = useState(null);
    const [analysisResult, setAnalysisResult] = useState(null);

    // Tab state
    const [activeTabKey, setActiveTabKey] = useState('traders');
    const [discoveryActiveTab, setDiscoveryActiveTab] = useState('discover');

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
        loadAllData();
    }, []);

    // API Functions - Now using real API calls
    const loadAllData = async () => {
        try {
            setLoading(true);
            await Promise.all([
                loadFollowedTraders(),
                loadRecentTrades(),
                loadSystemStatus(),
                loadDiscoveryStatus()
            ]);
        } catch (err) {
            console.error('Failed to load data:', err);
        } finally {
            setLoading(false);
        }
    };

    const loadFollowedTraders = async () => {
        try {
            const response = await copyTradingApi.getTraders();
            if (response.status === 'ok' && response.data) {
                const formattedTraders = response.data.map(trader => ({
                    id: trader.id,
                    wallet_address: trader.wallet_address,
                    trader_name: trader.trader_name,
                    description: trader.description,
                    chain: trader.chain,
                    copy_percentage: parseFloat(trader.copy_percentage || 0),
                    max_position_usd: parseFloat(trader.max_position_usd || 0),
                    status: trader.status,
                    quality_score: parseInt(trader.quality_score || 0),
                    total_pnl: parseFloat(trader.total_pnl_usd || 0),
                    win_rate: parseFloat(trader.win_rate_pct || 0),
                    total_trades: parseInt(trader.total_trades || 0),
                    avg_trade_size: parseFloat(trader.avg_trade_size_usd || 0),
                    last_activity_at: trader.last_activity_at,
                    created_at: trader.created_at
                }));
                setFollowedTraders(formattedTraders);
            }
        } catch (err) {
            setError('Failed to load followed traders');
            console.error('Load traders error:', err);
        }
    };

    const loadRecentTrades = async () => {
        try {
            const response = await copyTradingApi.getTrades({ limit: 50 });
            if (response.status === 'ok' && response.data) {
                const formattedTrades = response.data.map(trade => ({
                    id: trade.id,
                    trader_address: trade.trader_address,
                    trader_name: trade.trader_name,
                    token_symbol: trade.token_symbol,
                    action: trade.action,
                    amount_usd: parseFloat(trade.amount_usd || 0),
                    status: trade.status,
                    pnl_usd: parseFloat(trade.pnl_usd || 0),
                    timestamp: trade.timestamp,
                    chain: trade.chain,
                    tx_hash: trade.tx_hash
                }));
                setRecentTrades(formattedTrades);
            }
        } catch (err) {
            console.error('Load trades error:', err);
        }
    };

    const loadSystemStatus = async () => {
        try {
            const response = await copyTradingApi.getStatus();
            if (response.status === 'ok') {
                setSystemStatus({
                    active_traders: response.active_traders || 0,
                    total_pnl_usd: parseFloat(response.total_pnl_usd || 0),
                    trades_today: response.trades_today || 0,
                    success_rate: parseFloat(response.success_rate || 0)
                });
            }
        } catch (err) {
            console.error('Load system status error:', err);
        }
    };

    const loadDiscoveryStatus = async () => {
        try {
            const response = await discoveryApi.getStatus();
            if (response.status === 'ok') {
                setDiscoveryStatus({
                    discovery_running: response.discovery_running || false,
                    total_discovered: response.total_discovered || 0,
                    high_confidence_candidates: response.high_confidence_candidates || 0,
                    discovered_by_chain: response.discovered_by_chain || {}
                });
            }
        } catch (err) {
            console.error('Load discovery status error:', err);
        }
    };

    // Discovery Functions - Now using real API calls
    const handleStartAutoDiscovery = async () => {
        try {
            setDiscoveryLoading(true);
            setDiscoveryError(null);

            console.log('📡 Starting auto discovery with config:', discoveryConfig);

            const response = await discoveryApi.discoverTraders(discoveryConfig);

            console.log('📊 Discovery API response:', response);

            if (response.status === 'ok') {
                // Handle multiple possible response structures
                let wallets = response.discovered_wallets || response.candidates || response.data || [];

                if (Array.isArray(wallets) && wallets.length > 0) {
                    const formattedWallets = wallets.map(wallet => ({
                        id: wallet.id || wallet.address,
                        address: wallet.address,
                        chain: wallet.chain,
                        quality_score: parseInt(wallet.quality_score || wallet.confidence_score || 0),
                        total_volume_usd: parseFloat(wallet.total_volume_usd || 0),
                        win_rate: parseFloat(wallet.win_rate || 0),
                        trades_count: parseInt(wallet.trades_count || wallet.total_trades || 0),
                        avg_trade_size: parseFloat(wallet.avg_trade_size || wallet.avg_trade_size_usd || 0),
                        last_active: wallet.last_active || wallet.last_trade,
                        recommended_copy_percentage: parseFloat(wallet.recommended_copy_percentage || 0),
                        risk_level: wallet.risk_level || 'Medium',
                        confidence: wallet.confidence || 'Medium'
                    }));

                    console.log(`✅ Formatted ${formattedWallets.length} discovered wallets:`, formattedWallets);
                    setDiscoveredWallets(formattedWallets);
                } else {
                    console.warn('⚠️ No wallets found in discovery response');
                    setDiscoveredWallets([]);
                    setDiscoveryError('No profitable traders found with current criteria');
                }
            } else {
                throw new Error(response.error || 'Discovery failed');
            }
        } catch (err) {
            setDiscoveryError(err.message || 'Failed to start auto discovery');
            console.error('❌ Auto discovery error:', err);
        } finally {
            setDiscoveryLoading(false);
        }
    };

    const handleManualAnalysis = async () => {
        if (!manualAnalysis.address) return;

        // Validate wallet address format
        if (!/^0x[a-fA-F0-9]{40}$/.test(manualAnalysis.address)) {
            setDiscoveryError('Invalid wallet address format');
            return;
        }

        try {
            setDiscoveryLoading(true);
            setDiscoveryError(null);

            const response = await discoveryApi.analyzeWallet(manualAnalysis);

            if (response.status === 'ok' && response.analysis) {
                setAnalysisResult(response.analysis);
                setShowAnalysisModal(true);
            } else {
                throw new Error(response.error || 'Analysis failed');
            }
        } catch (err) {
            setDiscoveryError(err.message || 'Failed to analyze wallet');
            console.error('Manual analysis error:', err);
        } finally {
            setDiscoveryLoading(false);
        }
    };

    const handleAddDiscoveredTrader = (discoveredWallet) => {
        // Pre-fill form with discovered trader data
        setFormData({
            wallet_address: discoveredWallet.address,
            trader_name: `Trader_${discoveredWallet.address.slice(-4)}`,
            description: `Auto-discovered trader (Score: ${discoveredWallet.quality_score})`,
            chain: discoveredWallet.chain,
            copy_mode: 'percentage',
            copy_percentage: discoveredWallet.recommended_copy_percentage || 3.0,
            fixed_amount_usd: 100,
            max_position_usd: 1000,
            min_trade_value_usd: 50,
            max_slippage_bps: 300,
            allowed_chains: [discoveredWallet.chain],
            copy_buy_only: false,
            copy_sell_only: false
        });
        setShowAddModal(true);
    };

    // Handler Functions - Now using real API calls
    const handleAutoDiscoveryClick = () => {
        setActiveTabKey('discovery');
        setDiscoveryActiveTab('discover');
    };

    const handleAddTrader = async () => {
        try {
            // Validate required fields
            if (!formData.wallet_address || !formData.trader_name) {
                setError('Wallet address and trader name are required');
                return;
            }

            // Validate wallet address format
            if (!/^0x[a-fA-F0-9]{40}$/.test(formData.wallet_address)) {
                setError('Invalid wallet address format');
                return;
            }

            const response = await copyTradingApi.addTrader(formData);

            if (response.status === 'ok') {
                await loadFollowedTraders(); // Reload traders list
                setShowAddModal(false);
                resetForm();
                setError(null); // Clear any previous errors
            } else {
                throw new Error(response.error || 'Failed to add trader');
            }
        } catch (err) {
            setError(err.message || 'Failed to add trader');
            console.error('Add trader error:', err);
        }
    };

    const handleDeleteTrader = async (trader) => {
        if (!window.confirm(`Remove ${trader.trader_name} from followed traders?`)) return;

        try {
            const response = await copyTradingApi.removeTrader(trader.id);

            if (response.status === 'ok') {
                await loadFollowedTraders(); // Reload traders list
            } else {
                throw new Error(response.error || 'Failed to remove trader');
            }
        } catch (err) {
            setError(err.message || 'Failed to delete trader');
            console.error('Delete trader error:', err);
        }
    };

    const handleToggleTraderStatus = async (trader, newStatus) => {
        try {
            // For now, just update locally - you can implement the API call later
            setFollowedTraders(prev =>
                prev.map(t => t.id === trader.id ? { ...t, status: newStatus } : t)
            );
        } catch (err) {
            setError('Failed to update trader status');
            console.error('Toggle status error:', err);
        }
    };

    const openEditModal = (trader) => {
        setSelectedTrader(trader);
        setFormData({
            wallet_address: trader.wallet_address,
            trader_name: trader.trader_name,
            description: trader.description,
            chain: trader.chain,
            copy_mode: trader.copy_mode || 'percentage',
            copy_percentage: trader.copy_percentage,
            fixed_amount_usd: trader.fixed_amount_usd || 100,
            max_position_usd: trader.max_position_usd,
            min_trade_value_usd: trader.min_trade_value_usd || 50,
            max_slippage_bps: trader.max_slippage_bps || 300,
            allowed_chains: trader.allowed_chains || [trader.chain],
            copy_buy_only: trader.copy_buy_only || false,
            copy_sell_only: trader.copy_sell_only || false
        });
        setShowEditModal(true);
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
        setSelectedTrader(null);
    };

    if (loading) {
        return (
            <div className="text-center py-4">
                <Spinner animation="border" variant="primary" />
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
                        <Card className="bg-dark border-primary">
                            <Card.Header>
                                <h6 className="text-primary mb-0">📊 Copy Trading Status</h6>
                            </Card.Header>
                            <Card.Body>
                                <Row>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-primary">{systemStatus.active_traders}</div>
                                            <div className="text-muted small">Active Traders</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-info">{systemStatus.trades_today}</div>
                                            <div className="text-muted small">Trades Today</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className="h4 text-warning">{systemStatus.success_rate}%</div>
                                            <div className="text-muted small">Success Rate</div>
                                        </div>
                                    </Col>
                                    <Col md={3}>
                                        <div className="text-center">
                                            <div className={`h4 ${systemStatus.total_pnl_usd >= 0 ? 'text-success' : 'text-danger'}`}>
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
                                <Button variant="primary" onClick={handleAutoDiscoveryClick}>
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
                                            const qualityColor = trader.quality_score >= 80 ? 'success' :
                                                trader.quality_score >= 60 ? 'warning' : 'danger';
                                            return (
                                                <tr key={trader.id}>
                                                    <td>
                                                        <div>
                                                            <strong>{trader.trader_name}</strong>
                                                            <div className="small text-muted">
                                                                {trader.wallet_address}
                                                            </div>
                                                            <Badge bg="secondary" className="mt-1">
                                                                {trader.chain}
                                                            </Badge>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <Badge bg={qualityColor}>
                                                            {trader.quality_score}/100
                                                        </Badge>
                                                    </td>
                                                    <td>
                                                        <div className="small">
                                                            <div className={`fw-bold ${trader.total_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                                                                ${trader.total_pnl.toFixed(2)}
                                                            </div>
                                                            <div className="text-muted">
                                                                {trader.win_rate}% win rate
                                                            </div>
                                                            <div className="text-muted">
                                                                {trader.total_trades} trades
                                                            </div>
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <div className="small">
                                                            <div>{trader.copy_percentage}% allocation</div>
                                                            <div className="text-muted">
                                                                Max: ${trader.max_position_usd}
                                                            </div>
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
                                                                : 'Never'
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

                {/* Wallet Discovery Tab */}
                <Tab eventKey="discovery" title="🔍 Auto Discovery">
                    <div>
                        {/* Discovery Status */}
                        {discoveryStatus && (
                            <Row className="mb-3">
                                <Col>
                                    <Card className="bg-dark border-info">
                                        <Card.Header>
                                            <div className="d-flex justify-content-between align-items-center">
                                                <span>🎯 Discovery Status</span>
                                                <Badge bg={discoveryStatus.discovery_running ? 'success' : 'secondary'}>
                                                    {discoveryStatus.discovery_running ? 'Active' : 'Inactive'}
                                                </Badge>
                                            </div>
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

                        {/* Discovery Interface */}
                        <Card>
                            <Card.Header>
                                <ButtonGroup className="w-100">
                                    <Button
                                        variant={discoveryActiveTab === 'discover' ? 'primary' : 'outline-primary'}
                                        onClick={() => setDiscoveryActiveTab('discover')}
                                    >
                                        🎯 Auto Discovery
                                    </Button>
                                    <Button
                                        variant={discoveryActiveTab === 'analyze' ? 'primary' : 'outline-primary'}
                                        onClick={() => setDiscoveryActiveTab('analyze')}
                                    >
                                        🔬 Manual Analysis
                                    </Button>
                                </ButtonGroup>
                            </Card.Header>

                            <Card.Body>
                                {discoveryError && (
                                    <Alert variant="danger" dismissible onClose={() => setDiscoveryError(null)}>
                                        {discoveryError}
                                    </Alert>
                                )}

                                {/* Auto Discovery Tab */}
                                {discoveryActiveTab === 'discover' && (
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
                                                <Form.Group className="mb-3">
                                                    <Form.Label>Minimum Volume (USD)</Form.Label>
                                                    <Form.Control
                                                        type="number"
                                                        min="1000"
                                                        step="1000"
                                                        value={discoveryConfig.min_volume_usd}
                                                        onChange={(e) => setDiscoveryConfig(prev => ({
                                                            ...prev,
                                                            min_volume_usd: parseInt(e.target.value)
                                                        }))}
                                                    />
                                                </Form.Group>
                                                <Form.Group className="mb-3">
                                                    <Form.Label>Days to Analyze</Form.Label>
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

                                        <div className="text-center mb-4">
                                            <Button
                                                variant="primary"
                                                size="lg"
                                                onClick={handleStartAutoDiscovery}
                                                disabled={discoveryLoading || discoveryConfig.chains.length === 0}
                                            >
                                                {discoveryLoading ? (
                                                    <>
                                                        <Spinner animation="border" size="sm" className="me-2" />
                                                        Discovering Traders...
                                                    </>
                                                ) : (
                                                    '🚀 Start Auto Discovery'
                                                )}
                                            </Button>
                                        </div>

                                        {/* Discovered Traders Results Table */}
                                        {discoveredWallets.length > 0 && (
                                            <div>
                                                <h6 className="mb-3">🎯 Discovered Trader Candidates ({discoveredWallets.length})</h6>
                                                <Table responsive hover>
                                                    <thead>
                                                        <tr>
                                                            <th>Address</th>
                                                            <th>Chain</th>
                                                            <th>Quality Score</th>
                                                            <th>Performance</th>
                                                            <th>Risk Level</th>
                                                            <th>Recommended</th>
                                                            <th>Actions</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {discoveredWallets.map((wallet) => {
                                                            const scoreColor = wallet.quality_score >= 85 ? 'success' :
                                                                wallet.quality_score >= 70 ? 'warning' : 'danger';
                                                            const riskColor = wallet.risk_level === 'Low' ? 'success' :
                                                                wallet.risk_level === 'Medium' ? 'warning' : 'danger';
                                                            return (
                                                                <tr key={wallet.id}>
                                                                    <td>
                                                                        <div className="small font-monospace">
                                                                            {wallet.address}
                                                                        </div>
                                                                        <div className="small text-muted">
                                                                            Last active: {wallet.last_active}
                                                                        </div>
                                                                    </td>
                                                                    <td>
                                                                        <Badge bg="secondary">{wallet.chain}</Badge>
                                                                    </td>
                                                                    <td>
                                                                        <Badge bg={scoreColor}>
                                                                            {wallet.quality_score}/100
                                                                        </Badge>
                                                                        <div className="small text-muted mt-1">
                                                                            {wallet.confidence} confidence
                                                                        </div>
                                                                    </td>
                                                                    <td>
                                                                        <div className="small">
                                                                            <div><strong>${(wallet.total_volume_usd / 1000).toFixed(0)}k</strong> volume</div>
                                                                            <div className="text-success">{wallet.win_rate}% win rate</div>
                                                                            <div className="text-muted">{wallet.trades_count} trades</div>
                                                                        </div>
                                                                    </td>
                                                                    <td>
                                                                        <Badge bg={riskColor}>
                                                                            {wallet.risk_level}
                                                                        </Badge>
                                                                    </td>
                                                                    <td>
                                                                        <div className="small">
                                                                            <div><strong>{wallet.recommended_copy_percentage}%</strong> allocation</div>
                                                                            <div className="text-muted">Avg: ${wallet.avg_trade_size}</div>
                                                                        </div>
                                                                    </td>
                                                                    <td>
                                                                        <div className="d-flex gap-1">
                                                                            <Button
                                                                                variant="success"
                                                                                size="sm"
                                                                                onClick={() => handleAddDiscoveredTrader(wallet)}
                                                                            >
                                                                                ➕ Add
                                                                            </Button>
                                                                            <Button
                                                                                variant="outline-info"
                                                                                size="sm"
                                                                                onClick={() => {
                                                                                    setAnalysisResult({
                                                                                        candidate: wallet,
                                                                                        analysis: {
                                                                                            strengths: ['High win rate', 'Consistent volume', 'Low risk'],
                                                                                            weaknesses: ['Limited time data', 'Single chain focus'],
                                                                                            recommendation: 'Good candidate for medium allocation'
                                                                                        }
                                                                                    });
                                                                                    setShowAnalysisModal(true);
                                                                                }}
                                                                            >
                                                                                📊
                                                                            </Button>
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            );
                                                        })}
                                                    </tbody>
                                                </Table>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Manual Analysis Tab */}
                                {discoveryActiveTab === 'analyze' && (
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
                                                        isInvalid={manualAnalysis.address && !/^0x[a-fA-F0-9]{40}$/.test(manualAnalysis.address)}
                                                    />
                                                    <Form.Control.Feedback type="invalid">
                                                        Please enter a valid Ethereum address (0x followed by 40 hex characters)
                                                    </Form.Control.Feedback>
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
                                            disabled={discoveryLoading || !manualAnalysis.address || !/^0x[a-fA-F0-9]{40}$/.test(manualAnalysis.address)}
                                        >
                                            {discoveryLoading ? (
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
                            </Card.Body>
                        </Card>
                    </div>
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
                                    <div className="h4">📋</div>
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
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {recentTrades.map((trade, index) => (
                                            <tr key={trade.id || index}>
                                                <td>{new Date(trade.timestamp).toLocaleString()}</td>
                                                <td>{trade.trader_name}</td>
                                                <td>{trade.token_symbol}</td>
                                                <td>
                                                    <Badge bg={trade.action === 'BUY' ? 'success' : 'danger'}>
                                                        {trade.action}
                                                    </Badge>
                                                </td>
                                                <td>${trade.amount_usd}</td>
                                                <td>
                                                    <Badge bg={
                                                        trade.status === 'executed' ? 'success' :
                                                            trade.status === 'pending' ? 'warning' : 'danger'
                                                    }>
                                                        {trade.status}
                                                    </Badge>
                                                </td>
                                                <td className={trade.pnl_usd >= 0 ? 'text-success' : 'text-danger'}>
                                                    ${trade.pnl_usd.toFixed(2)}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </Table>
                            )}
                        </Card.Body>
                    </Card>
                </Tab>
            </Tabs>

            {/* Add Trader Modal */}
            <Modal show={showAddModal} onHide={() => setShowAddModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>➕ Add Trader to Copy</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <Form>
                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Wallet Address</Form.Label>
                                    <Form.Control
                                        type="text"
                                        placeholder="0x..."
                                        value={formData.wallet_address}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            wallet_address: e.target.value
                                        }))}
                                        isInvalid={formData.wallet_address && !/^0x[a-fA-F0-9]{40}$/.test(formData.wallet_address)}
                                    />
                                    <Form.Control.Feedback type="invalid">
                                        Please enter a valid Ethereum address
                                    </Form.Control.Feedback>
                                </Form.Group>
                            </Col>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Trader Name</Form.Label>
                                    <Form.Control
                                        type="text"
                                        placeholder="Friendly name for this trader"
                                        value={formData.trader_name}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            trader_name: e.target.value
                                        }))}
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
                                onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    description: e.target.value
                                }))}
                            />
                        </Form.Group>

                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Primary Chain</Form.Label>
                                    <Form.Select
                                        value={formData.chain}
                                        onChange={(e) => setFormData(prev => ({
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
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Copy Mode</Form.Label>
                                    <Form.Select
                                        value={formData.copy_mode}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            copy_mode: e.target.value
                                        }))}
                                    >
                                        <option value="percentage">Percentage of Portfolio</option>
                                        <option value="fixed">Fixed Amount</option>
                                    </Form.Select>
                                </Form.Group>
                            </Col>
                        </Row>

                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>
                                        {formData.copy_mode === 'percentage' ? 'Copy Percentage (%)' : 'Fixed Amount (USD)'}
                                    </Form.Label>
                                    <Form.Control
                                        type="number"
                                        step={formData.copy_mode === 'percentage' ? '0.1' : '10'}
                                        min={formData.copy_mode === 'percentage' ? '0.1' : '10'}
                                        value={formData.copy_mode === 'percentage' ? formData.copy_percentage : formData.fixed_amount_usd}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            [formData.copy_mode === 'percentage' ? 'copy_percentage' : 'fixed_amount_usd']: parseFloat(e.target.value)
                                        }))}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Max Position (USD)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        step="50"
                                        min="50"
                                        value={formData.max_position_usd}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            max_position_usd: parseInt(e.target.value)
                                        }))}
                                    />
                                </Form.Group>
                            </Col>
                        </Row>

                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Min Trade Value (USD)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        step="10"
                                        min="10"
                                        value={formData.min_trade_value_usd}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            min_trade_value_usd: parseInt(e.target.value)
                                        }))}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Max Slippage (basis points)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        step="10"
                                        min="50"
                                        max="1000"
                                        value={formData.max_slippage_bps}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            max_slippage_bps: parseInt(e.target.value)
                                        }))}
                                    />
                                    <div className="small text-muted">
                                        {(formData.max_slippage_bps / 100).toFixed(1)}% slippage
                                    </div>
                                </Form.Group>
                            </Col>
                        </Row>

                        <div className="mb-3">
                            <Form.Check
                                type="checkbox"
                                label="Copy buy orders only"
                                checked={formData.copy_buy_only}
                                onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    copy_buy_only: e.target.checked,
                                    copy_sell_only: e.target.checked ? false : prev.copy_sell_only
                                }))}
                            />
                            <Form.Check
                                type="checkbox"
                                label="Copy sell orders only"
                                checked={formData.copy_sell_only}
                                onChange={(e) => setFormData(prev => ({
                                    ...prev,
                                    copy_sell_only: e.target.checked,
                                    copy_buy_only: e.target.checked ? false : prev.copy_buy_only
                                }))}
                            />
                        </div>
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowAddModal(false)}>
                        Cancel
                    </Button>
                    <Button
                        variant="primary"
                        onClick={handleAddTrader}
                        disabled={!formData.wallet_address || !formData.trader_name || !/^0x[a-fA-F0-9]{40}$/.test(formData.wallet_address)}
                    >
                        Add Trader
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Edit Trader Modal */}
            <Modal show={showEditModal} onHide={() => setShowEditModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>✏️ Edit Trader Settings</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {/* Same form as Add Modal but for editing */}
                    <Form>
                        <Row>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Copy Percentage (%)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        step="0.1"
                                        min="0.1"
                                        value={formData.copy_percentage}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            copy_percentage: parseFloat(e.target.value)
                                        }))}
                                    />
                                </Form.Group>
                            </Col>
                            <Col md={6}>
                                <Form.Group className="mb-3">
                                    <Form.Label>Max Position (USD)</Form.Label>
                                    <Form.Control
                                        type="number"
                                        step="50"
                                        min="50"
                                        value={formData.max_position_usd}
                                        onChange={(e) => setFormData(prev => ({
                                            ...prev,
                                            max_position_usd: parseInt(e.target.value)
                                        }))}
                                    />
                                </Form.Group>
                            </Col>
                        </Row>
                        {/* Add other edit fields as needed */}
                    </Form>
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowEditModal(false)}>
                        Cancel
                    </Button>
                    <Button
                        variant="primary"
                        onClick={() => {
                            // Update trader logic here
                            setShowEditModal(false);
                        }}
                    >
                        Save Changes
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Trader Details Modal */}
            <Modal show={showDetailsModal} onHide={() => setShowDetailsModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>👁️ Trader Details</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {selectedTrader && (
                        <div>
                            <Row>
                                <Col md={6}>
                                    <h6>Basic Info</h6>
                                    <p><strong>Name:</strong> {selectedTrader.trader_name}</p>
                                    <p><strong>Address:</strong> {selectedTrader.wallet_address}</p>
                                    <p><strong>Chain:</strong> {selectedTrader.chain}</p>
                                    <p><strong>Status:</strong> <Badge bg="success">{selectedTrader.status}</Badge></p>
                                </Col>
                                <Col md={6}>
                                    <h6>Performance</h6>
                                    <p><strong>Quality Score:</strong> {selectedTrader.quality_score}/100</p>
                                    <p><strong>Total P&L:</strong> <span className={selectedTrader.total_pnl >= 0 ? 'text-success' : 'text-danger'}>${selectedTrader.total_pnl.toFixed(2)}</span></p>
                                    <p><strong>Win Rate:</strong> {selectedTrader.win_rate}%</p>
                                    <p><strong>Total Trades:</strong> {selectedTrader.total_trades}</p>
                                </Col>
                            </Row>
                        </div>
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowDetailsModal(false)}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>

            {/* Analysis Result Modal */}
            <Modal show={showAnalysisModal} onHide={() => setShowAnalysisModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>🔬 Wallet Analysis Results</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {analysisResult && (
                        <div>
                            <Row className="mb-3">
                                <Col md={6}>
                                    <h6>Candidate Overview</h6>
                                    <p><strong>Address:</strong> <code>{analysisResult.candidate.address}</code></p>
                                    <p><strong>Chain:</strong> {analysisResult.candidate.chain}</p>
                                    <p><strong>Quality Score:</strong> <Badge bg="success">{analysisResult.candidate.quality_score}/100</Badge></p>
                                    <p><strong>Total Volume:</strong> ${(analysisResult.candidate.total_volume_usd / 1000).toFixed(0)}k</p>
                                </Col>
                                <Col md={6}>
                                    <h6>Performance Metrics</h6>
                                    <p><strong>Win Rate:</strong> {analysisResult.candidate.win_rate}%</p>
                                    <p><strong>Total Trades:</strong> {analysisResult.candidate.trades_count}</p>
                                    <p><strong>Avg Trade Size:</strong> ${analysisResult.candidate.avg_trade_size}</p>
                                    <p><strong>Risk Level:</strong> <Badge bg="warning">{analysisResult.candidate.risk_level}</Badge></p>
                                </Col>
                            </Row>

                            <Row>
                                <Col md={6}>
                                    <h6>Strengths</h6>
                                    <ul>
                                        {analysisResult.analysis.strengths.map((strength, idx) => (
                                            <li key={idx} className="text-success">✅ {strength}</li>
                                        ))}
                                    </ul>
                                </Col>
                                <Col md={6}>
                                    <h6>Weaknesses</h6>
                                    <ul>
                                        {analysisResult.analysis.weaknesses.map((weakness, idx) => (
                                            <li key={idx} className="text-warning">⚠️ {weakness}</li>
                                        ))}
                                    </ul>
                                </Col>
                            </Row>

                            <Alert variant="info">
                                <strong>Recommendation:</strong> {analysisResult.analysis.recommendation}
                            </Alert>

                            <div className="text-center">
                                <p><strong>Recommended Copy Allocation:</strong> <Badge bg="primary">{analysisResult.candidate.recommended_copy_percentage}%</Badge></p>
                                <Button
                                    variant="success"
                                    onClick={() => {
                                        handleAddDiscoveredTrader(analysisResult.candidate);
                                        setShowAnalysisModal(false);
                                    }}
                                >
                                    Add to Copy Trading
                                </Button>
                            </div>
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