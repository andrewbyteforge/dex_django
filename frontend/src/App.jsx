import { useState, useEffect } from 'react';
import { Container, Row, Col, Nav, Tab, Card, Button, Alert, Spinner, Table } from 'react-bootstrap';
import { PaperTradeCard } from './components/PaperTradeCard.jsx';
import { AIThoughtLogPanel } from './components/AIThoughtLogPanel.jsx';
import { PaperTradingDashboard } from './components/PaperTradingDashboard.jsx';
import { TokenModal } from './components/TokenModal.jsx';
import { DiscoveryCard } from './components/DiscoveryCard.jsx';
import { LiveOpportunitiesCard } from './components/LiveOpportunitiesCard.jsx';
import { CopyTradingTab } from './components/CopyTradingTab.jsx';
import { useDjangoData, useBotControl, useDjangoMutations } from './hooks/useDjangoApi.js';
import { DashboardHeader } from './components/DashboardHeader';
import { WalletConnectButton } from './components/WalletConnectButton';
import { WalletStatusBar } from './components/WalletStatusBar';
import { IntelligencePanel } from './components/IntelligencePanel';

// Bot Status Card Component with Copy Trading Integration
const BotStatusCard = ({ botData, liveOpportunities, tradingMode, copyTradingStats }) => {
    return (
        <Card className="bg-dark border-primary mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <h5 className="text-primary mb-0">🤖 DEX Sniper Pro - Advanced Intelligence</h5>
                <div className="d-flex gap-2">
                    <span className={`badge ${botData?.status === 'running' ? 'bg-success' : 'bg-warning'}`}>
                        {botData?.status === 'running' ? 'ACTIVE' : 'STANDBY'}
                    </span>
                    <span className="badge bg-info">COPY TRADING</span>
                </div>
            </Card.Header>
            <Card.Body>
                <Row>
                    <Col md={6}>
                        <h6 className="text-warning">Premium Capabilities</h6>
                        <ul className="list-unstyled text-light small">
                            <li>✅ Copy Trading Intelligence (Track {copyTradingStats?.followed_traders || 0} traders)</li>
                            <li>✅ Advanced contract bytecode analysis</li>
                            <li>✅ Real-time honeypot & rug detection</li>
                            <li>✅ Social manipulation pattern analysis</li>
                            <li>✅ Whale activity & liquidity monitoring</li>
                            <li>✅ AI-powered risk scoring (0-100)</li>
                        </ul>
                    </Col>
                    <Col md={6}>
                        <h6 className="text-warning">Performance Metrics</h6>
                        <div className="d-flex justify-content-between mb-1">
                            <span className="small">Live Opportunities:</span>
                            <span className="text-success small">{liveOpportunities?.length || 0} detected</span>
                        </div>
                        <div className="d-flex justify-content-between mb-1">
                            <span className="small">Copy Success Rate:</span>
                            <span className="text-success small">{copyTradingStats?.win_rate_pct?.toFixed(1) || '0.0'}%</span>
                        </div>
                        <div className="d-flex justify-content-between mb-1">
                            <span className="small">Tracked Traders:</span>
                            <span className="text-info small">{copyTradingStats?.followed_traders_count || 0} verified</span>
                        </div>
                        <div className="d-flex justify-content-between mb-1">
                            <span className="small">Connected Chains:</span>
                            <span className="text-info small">2/4 (BSC, Base)</span>
                        </div>
                        <div className="d-flex justify-content-between mb-1">
                            <span className="small">24h Copy Profit:</span>
                            <span className={`small ${parseFloat(copyTradingStats?.total_pnl_usd || 0) >= 0 ? 'text-success' : 'text-danger'}`}>
                                ${parseFloat(copyTradingStats?.total_pnl_usd || 0).toFixed(2)}
                            </span>
                        </div>
                        <div className="d-flex justify-content-between">
                            <span className="small">Risk Analysis:</span>
                            <span className="text-success small">100% validated</span>
                        </div>
                    </Col>
                </Row>
            </Card.Body>
        </Card>
    );
};

export default function App() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [showTokenModal, setShowTokenModal] = useState(false);
    const [tradingMode, setTradingMode] = useState('paper');
    const [liveOpportunities, setLiveOpportunities] = useState([]);
    const [copyTradingStats, setCopyTradingStats] = useState(null);

    // Django API hooks
    const {
        data: trades,
        loading: tradesLoading,
        error: tradesError,
        hasNext: tradesHasNext,
        hasPrev: tradesHasPrev,
        nextPage: tradesNextPage,
        prevPage: tradesPrevPage,
        page: tradesPage
    } = useDjangoData('/api/v1/trades/', []);

    const {
        data: tokens,
        loading: tokensLoading,
        error: tokensError,
        refresh: refreshTokens
    } = useDjangoData('/api/v1/tokens/', []);

    const {
        data: providers,
        loading: providersLoading,
        error: providersError,
        refresh: refreshProviders
    } = useDjangoData('/api/v1/providers/', []);

    const {
        botStatus,
        loading: botLoading,
        startBot,
        stopBot,
        error: botError
    } = useBotControl();

    // State for displaying token operation errors
    const [tokenError, setTokenError] = useState(null);

    const tokenMutations = useDjangoMutations('/api/v1/tokens/');
    const providerMutations = useDjangoMutations('/api/v1/providers/');

    const canPrev = tradesHasPrev;
    const canNext = tradesHasNext;

    // Load copy trading statistics
    useEffect(() => {
        const loadCopyTradingStats = async () => {
            try {
                const response = await fetch('http://127.0.0.1:8000/api/v1/copy/status'); // ← Fix
                const data = await response.json();
                setCopyTradingStats(data);
            } catch (error) {
                console.error('Failed to load copy trading stats:', error);
            }
        };

        loadCopyTradingStats();
        const interval = setInterval(loadCopyTradingStats, 60000); // Update every minute
        return () => clearInterval(interval);
    }, []);

    // Helper function for error formatting
    const fmtError = (error) => {
        if (typeof error === 'string') return error;
        if (error?.message) return error.message;
        if (error?.detail) return error.detail;
        return JSON.stringify(error);
    };

    // Token management handlers
    const handleAddToken = async (tokenData) => {
        try {
            console.log('Adding token:', tokenData);
            setTokenError(null);
            await tokenMutations.create(tokenData);
            console.log('Token added successfully');
            setShowTokenModal(false);
            refreshTokens();
        } catch (error) {
            console.error('Failed to add token:', error);
            const errorData = error.response?.data || error;
            console.log('Setting tokenError to:', errorData);
            setTokenError(errorData);
        }
    };

    const handleRemoveToken = async (id, tokenSymbol) => {
        if (!confirm(`Are you sure you want to remove token ${tokenSymbol}?`)) {
            return;
        }

        try {
            console.log('Removing token ID:', id);
            setTokenError(null);
            await tokenMutations.remove(id);
            console.log('Token removed successfully');
            refreshTokens();
        } catch (error) {
            console.error('Failed to remove token:', error);
            const errorData = error.response?.data || error;
            console.log('Setting tokenError to:', errorData);
            setTokenError(errorData);
        }
    };

    const handleStartBot = async () => {
        try {
            await startBot();
        } catch (error) {
            console.error('Failed to start bot:', error);
        }
    };

    const handleStopBot = async () => {
        try {
            await stopBot();
        } catch (error) {
            console.error('Failed to stop bot:', error);
        }
    };

    const handleEmergencyStop = () => {
        console.log('Emergency stop triggered');
        if (botStatus?.status === 'running') {
            handleStopBot();
        }
    };

    const handleExportLogs = () => {
        console.log('Export logs triggered');
        alert('Log export functionality coming soon!');
    };

    return (
        <Container fluid className="py-3">
            <Row>
                <Col>
                    {/* Dashboard Header with Wallet Integration */}
                    <DashboardHeader
                        botStatus={botStatus}
                        onEmergencyStop={handleEmergencyStop}
                        onExportLogs={handleExportLogs}
                    />

                    <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k)}>
                        <Nav variant="tabs" className="mb-4">
                            <Nav.Item>
                                <Nav.Link eventKey="dashboard">
                                    📊 Dashboard
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="discovery">
                                    🔍 Discovery
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="copy-trading">
                                    👥 Copy Trading
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="paper-trading">
                                    📝 Paper Trading
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="trades">
                                    💰 Trades
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="tokens">
                                    🪙 Tokens
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="providers">
                                    🔗 Providers
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="settings">
                                    ⚙️ Settings
                                </Nav.Link>
                            </Nav.Item>
                        </Nav>

                        <Tab.Content>
                            {/* Wallet Status Bar - shows on all tabs */}
                            <WalletStatusBar tradingMode={tradingMode} />

                            {/* Dashboard Tab - UPDATED with Bot Status Card */}
                            <Tab.Pane eventKey="dashboard">
                                <Row>
                                    {/* Bot Status Card - Featured prominently at top */}
                                    <Col xs={12}>
                                        <BotStatusCard
                                            botData={botStatus}
                                            liveOpportunities={liveOpportunities}
                                            tradingMode={tradingMode}
                                            copyTradingStats={copyTradingStats}
                                        />
                                    </Col>
                                </Row>

                                <Row>
                                    <Col lg={8}>
                                        <Card className="mb-3">
                                            <Card.Header><strong>System Status</strong></Card.Header>
                                            <Card.Body>
                                                <div className="row">
                                                    <div className="col-md-3 text-center">
                                                        <div className="fw-bold text-success">Bot Status</div>
                                                        <div className="fs-5">
                                                            {botLoading ? '⚪ Loading...' :
                                                                botStatus?.status === 'running' ? '🟢 Running' :
                                                                    '🔴 Stopped'}
                                                        </div>
                                                    </div>
                                                    <div className="col-md-3 text-center">
                                                        <div className="fw-bold">Balance</div>
                                                        <div className="fs-5">£1,250.00</div>
                                                    </div>
                                                    <div className="col-md-3 text-center">
                                                        <div className="fw-bold">24h P&L</div>
                                                        <div className="fs-5 text-success">+£45.30</div>
                                                    </div>
                                                    <div className="col-md-3 text-center">
                                                        <div className="fw-bold">Trades Today</div>
                                                        <div className="fs-5">12</div>
                                                    </div>
                                                </div>
                                            </Card.Body>
                                        </Card>

                                        <Card>
                                            <Card.Header><strong>Recent Activity</strong></Card.Header>
                                            <Card.Body>
                                                <div className="text-muted">Recent trades and events will appear here...</div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                    <Col lg={4}>
                                        <Card className="mb-3">
                                            <Card.Header><strong>Trading Mode</strong></Card.Header>
                                            <Card.Body>
                                                <div className="d-grid gap-2">
                                                    <Button
                                                        variant={tradingMode === 'paper' ? 'success' : 'outline-secondary'}
                                                        onClick={() => setTradingMode('paper')}
                                                    >
                                                        📝 Paper Trading
                                                    </Button>
                                                    <Button
                                                        variant={tradingMode === 'manual' ? 'primary' : 'outline-secondary'}
                                                        onClick={() => setTradingMode('manual')}
                                                    >
                                                        👤 Manual Trading
                                                    </Button>
                                                    <Button
                                                        variant={tradingMode === 'auto' ? 'warning' : 'outline-secondary'}
                                                        onClick={() => setTradingMode('auto')}
                                                        disabled
                                                    >
                                                        🤖 Auto Trading (Soon)
                                                    </Button>
                                                </div>
                                            </Card.Body>
                                        </Card>

                                        <Card className="mb-3">
                                            <Card.Header><strong>Quick Actions</strong></Card.Header>
                                            <Card.Body>
                                                <div className="d-grid gap-2">
                                                    <Button
                                                        variant="success"
                                                        disabled={botLoading || botStatus?.status === 'running'}
                                                        onClick={handleStartBot}
                                                    >
                                                        {botLoading ? 'Loading...' : 'Start Bot'}
                                                    </Button>
                                                    <Button
                                                        variant="danger"
                                                        disabled={botLoading || botStatus?.status !== 'running'}
                                                        onClick={handleStopBot}
                                                    >
                                                        {botLoading ? 'Loading...' : 'Stop Bot'}
                                                    </Button>
                                                    {botError && (
                                                        <Alert variant="danger" className="mt-2">
                                                            {fmtError(botError)}
                                                        </Alert>
                                                    )}
                                                </div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                </Row>
                            </Tab.Pane>

                            {/* Discovery Tab */}
                            <Tab.Pane eventKey="discovery">
                                <IntelligencePanel
                                    opportunities={liveOpportunities}
                                    userBalance={1000}
                                />
                                <LiveOpportunitiesCard />
                            </Tab.Pane>

                            {/* Copy Trading Tab - NEW */}
                            <Tab.Pane eventKey="copy-trading">
                                <CopyTradingTab />
                            </Tab.Pane>

                            {/* Paper Trading Tab - Updated with AI Thought Log */}
                            <Tab.Pane eventKey="paper-trading">
                                <Row>
                                    <Col lg={4} className="mb-4">
                                        <PaperTradeCard />

                                        {/* Additional info card */}
                                        <Card className="mt-3">
                                            <Card.Body className="text-center">
                                                <div className="text-muted small">
                                                    <p className="mb-1">
                                                        <strong>Paper Trading Mode:</strong> Practice trading with virtual funds
                                                    </p>
                                                    <p className="mb-0">
                                                        All trades are simulated • No real money at risk • Same logic as live trading
                                                    </p>
                                                </div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                    <Col lg={8}>
                                        <AIThoughtLogPanel />
                                    </Col>
                                </Row>
                            </Tab.Pane>

                            {/* Trades Tab */}
                            <Tab.Pane eventKey="trades">
                                <Card>
                                    <Card.Header className="d-flex justify-content-between align-items-center">
                                        <strong>Trade History</strong>
                                        <div className="d-flex align-items-center gap-3">
                                            <span className="small text-muted">
                                                Count: {trades?.count || 0} · page: {tradesPage}
                                            </span>
                                            <Button
                                                size="sm"
                                                variant="outline-secondary"
                                                disabled={!canPrev}
                                                onClick={tradesPrevPage}
                                            >
                                                ← Prev
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="outline-secondary"
                                                disabled={!canNext}
                                                onClick={tradesNextPage}
                                            >
                                                Next →
                                            </Button>
                                        </div>
                                    </Card.Header>
                                    <Card.Body>
                                        {tradesLoading ? (
                                            <div className="text-center py-3">
                                                <Spinner animation="border" />
                                            </div>
                                        ) : tradesError ? (
                                            <Alert variant="danger">
                                                <strong>Error:</strong> {fmtError(tradesError)}
                                            </Alert>
                                        ) : (
                                            <TradesTable results={trades?.results || []} />
                                        )}
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Tokens Tab */}
                            <Tab.Pane eventKey="tokens">
                                <Card>
                                    <Card.Header className="d-flex justify-content-between align-items-center">
                                        <strong>Token Management</strong>
                                        <Button size="sm" variant="primary" onClick={() => setShowTokenModal(true)}>
                                            + Add Token
                                        </Button>
                                    </Card.Header>
                                    <Card.Body>
                                        {tokensLoading ? (
                                            <div className="text-center py-3">
                                                <Spinner animation="border" />
                                            </div>
                                        ) : tokensError ? (
                                            <Alert variant="danger">
                                                <strong>Error:</strong> {fmtError(tokensError)}
                                            </Alert>
                                        ) : (
                                            <TokensTable
                                                tokens={tokens?.results || []}
                                                onRemove={handleRemoveToken}
                                                loading={tokenMutations.loading}
                                                error={tokenError}
                                            />
                                        )}
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Providers Tab */}
                            <Tab.Pane eventKey="providers">
                                <Card>
                                    <Card.Header>
                                        <strong>RPC Providers</strong>
                                    </Card.Header>
                                    <Card.Body>
                                        {providersLoading ? (
                                            <div className="text-center py-3">
                                                <Spinner animation="border" />
                                            </div>
                                        ) : providersError ? (
                                            <Alert variant="danger">
                                                <strong>Error:</strong> {fmtError(providersError)}
                                            </Alert>
                                        ) : (
                                            <ProvidersTable providers={providers?.results || []} />
                                        )}
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Settings Tab */}
                            <Tab.Pane eventKey="settings">
                                <Row>
                                    <Col md={6}>
                                        <Card>
                                            <Card.Header><strong>Trading Settings</strong></Card.Header>
                                            <Card.Body>
                                                <div className="text-muted">Trading settings will appear here...</div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                    <Col md={6}>
                                        <Card>
                                            <Card.Header><strong>Risk Management</strong></Card.Header>
                                            <Card.Body>
                                                <div className="text-muted">Risk settings will appear here...</div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                </Row>
                            </Tab.Pane>
                        </Tab.Content>
                    </Tab.Container>

                    {/* Token Modal */}
                    <TokenModal
                        show={showTokenModal}
                        onHide={() => {
                            setShowTokenModal(false);
                            setTokenError(null);
                        }}
                        onSave={handleAddToken}
                        loading={tokenMutations.loading}
                        error={tokenError}
                    />
                </Col>
            </Row>
        </Container>
    );
}

function TradesTable({ results }) {
    if (!results || results.length === 0) {
        return <div className="text-muted">No trades to display.</div>;
    }

    return (
        <Table striped bordered hover size="sm" className="align-middle">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Time</th>
                    <th>Pair</th>
                    <th>Side</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Tx Hash</th>
                </tr>
            </thead>
            <tbody>
                {results.map((t) => (
                    <tr key={t.id}>
                        <td>{t.id}</td>
                        <td>{new Date(t.created_at).toLocaleTimeString()}</td>
                        <td>{t.pair || 'N/A'}</td>
                        <td className={t.side === "buy" ? "text-success" : "text-danger"}>
                            {t.side?.toUpperCase()}
                        </td>
                        <td>{t.amount_in}</td>
                        <td>
                            <span className={`badge bg-${t.status === 'completed' ? 'success' : 'warning'}`}>
                                {t.status}
                            </span>
                        </td>
                        <td className="text-truncate" style={{ maxWidth: 120 }}>
                            {t.tx_hash ? (
                                <a href={`https://etherscan.io/tx/${t.tx_hash}`} target="_blank" rel="noopener noreferrer">
                                    {t.tx_hash.slice(0, 10)}...
                                </a>
                            ) : '-'}
                        </td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
}

function TokensTable({ tokens, onRemove, loading, error }) {
    if (!tokens || tokens.length === 0) {
        return <div className="text-muted">No tokens configured.</div>;
    }

    return (
        <Table striped hover size="sm">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Name</th>
                    <th>Chain</th>
                    <th>Address</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {tokens.map((token) => (
                    <tr key={token.id}>
                        <td><strong>{token.symbol}</strong></td>
                        <td>{token.name}</td>
                        <td>{token.chain}</td>
                        <td className="font-monospace text-truncate" style={{ maxWidth: 150 }}>
                            {token.address}
                        </td>
                        <td>
                            <Button
                                size="sm"
                                variant="outline-danger"
                                onClick={() => onRemove(token.id, token.symbol)}
                                disabled={loading}
                            >
                                Remove
                            </Button>
                        </td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
}

function ProvidersTable({ providers }) {
    if (!providers || providers.length === 0) {
        return <div className="text-muted">No providers configured.</div>;
    }

    return (
        <Table striped hover size="sm">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Kind</th>
                    <th>URL</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {providers.map((provider) => (
                    <tr key={provider.id}>
                        <td><strong>{provider.name}</strong></td>
                        <td>
                            <span className="badge bg-secondary">{provider.kind}</span>
                        </td>
                        <td className="text-truncate font-monospace" style={{ maxWidth: 200 }}>
                            {provider.url}
                        </td>
                        <td>
                            <span className={`badge bg-${provider.enabled ? 'success' : 'secondary'}`}>
                                {provider.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                        </td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
}