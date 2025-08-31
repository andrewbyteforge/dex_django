import { useState, useEffect } from 'react';
import { Container, Row, Col, Nav, Tab, Card, Button, Alert, Spinner, Table } from 'react-bootstrap';
import { PaperTradeCard } from './components/PaperTradeCard.jsx';
import { TokenModal } from './components/TokenModal.jsx';
import { useDjangoData, useBotControl, useDjangoMutations } from './hooks/useDjangoApi.js';

export default function App() {
    const [activeTab, setActiveTab] = useState('dashboard');
    const [showTokenModal, setShowTokenModal] = useState(false);

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

    // Token management handlers
    const handleAddToken = async (tokenData) => {
        try {
            console.log('Adding token:', tokenData);
            setTokenError(null); // Clear previous errors
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
            setTokenError(null); // Clear previous errors
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

    return (
        <Container fluid className="py-3">
            <Row>
                <Col>
                    <h1 className="mb-4">DEX Sniper Pro — Dashboard</h1>

                    <Tab.Container activeKey={activeTab} onSelect={(k) => setActiveTab(k)}>
                        <Nav variant="tabs" className="mb-4">
                            <Nav.Item>
                                <Nav.Link eventKey="dashboard">
                                    📊 Dashboard
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
                            {/* Dashboard Tab */}
                            <Tab.Pane eventKey="dashboard">
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
                                        <Card>
                                            <Card.Header><strong>Quick Actions</strong></Card.Header>
                                            <Card.Body className="d-grid gap-2">
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
                                                <Button variant="outline-primary">Emergency Stop</Button>
                                                <Button variant="outline-secondary">Export Logs</Button>
                                                {botError && (
                                                    <Alert variant="danger" className="mt-2">
                                                        {fmtError(botError)}
                                                    </Alert>
                                                )}
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                </Row>
                            </Tab.Pane>

                            {/* Paper Trading Tab */}
                            <Tab.Pane eventKey="paper-trading">
                                <PaperTradeCard />
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
                                                Prev
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="outline-secondary"
                                                disabled={!canNext}
                                                onClick={tradesNextPage}
                                            >
                                                Next
                                            </Button>
                                        </div>
                                    </Card.Header>
                                    <Card.Body>
                                        {tradesLoading && <Spinner />}
                                        {tradesError && <Alert variant="danger">{fmtError(tradesError)}</Alert>}
                                        {trades && trades.results && <TradesTable results={trades.results} />}
                                        {!tradesLoading && trades?.results?.length === 0 && (
                                            <div className="text-muted">No trades yet.</div>
                                        )}
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Tokens Tab */}
                            <Tab.Pane eventKey="tokens">
                                <Card>
                                    <Card.Header className="d-flex justify-content-between align-items-center">
                                        <strong>Token Management</strong>
                                        <Button variant="primary" size="sm">Add Token</Button>
                                    </Card.Header>
                                    <Card.Body>
                                        {tokensLoading && <Spinner />}
                                        {tokensError && <Alert variant="danger">{fmtError(tokensError)}</Alert>}
                                        <TokensTable
                                            tokens={tokens?.results || []}
                                            onRemove={async (id) => {
                                                try {
                                                    await tokenMutations.remove(id);
                                                    refreshTokens();
                                                } catch (error) {
                                                    console.error('Failed to remove token:', error);
                                                }
                                            }}
                                        />
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Providers Tab */}
                            <Tab.Pane eventKey="providers">
                                <Card>
                                    <Card.Header className="d-flex justify-content-between align-items-center">
                                        <strong>RPC Providers</strong>
                                        <Button variant="primary" size="sm">Add Provider</Button>
                                    </Card.Header>
                                    <Card.Body>
                                        {providersLoading && <Spinner />}
                                        {providersError && <Alert variant="danger">{fmtError(providersError)}</Alert>}
                                        <ProvidersTable providers={providers?.results || []} />
                                    </Card.Body>
                                </Card>
                            </Tab.Pane>

                            {/* Settings Tab */}
                            <Tab.Pane eventKey="settings">
                                <Row>
                                    <Col md={6}>
                                        <Card className="mb-3">
                                            <Card.Header><strong>Trading Settings</strong></Card.Header>
                                            <Card.Body>
                                                <div className="mb-3">
                                                    <label className="form-label">Max Slippage (%)</label>
                                                    <input type="number" className="form-control" defaultValue="3" />
                                                </div>
                                                <div className="mb-3">
                                                    <label className="form-label">Max Trade Size (ETH)</label>
                                                    <input type="number" className="form-control" defaultValue="1.0" />
                                                </div>
                                                <div className="mb-3">
                                                    <label className="form-label">Gas Price Multiplier</label>
                                                    <input type="number" className="form-control" defaultValue="1.2" step="0.1" />
                                                </div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                    <Col md={6}>
                                        <Card>
                                            <Card.Header><strong>Risk Management</strong></Card.Header>
                                            <Card.Body>
                                                <div className="mb-3">
                                                    <label className="form-label">Min Liquidity (USD)</label>
                                                    <input type="number" className="form-control" defaultValue="10000" />
                                                </div>
                                                <div className="mb-3">
                                                    <label className="form-label">Max Daily Trades</label>
                                                    <input type="number" className="form-control" defaultValue="50" />
                                                </div>
                                                <div className="form-check">
                                                    <input className="form-check-input" type="checkbox" id="autoStop" />
                                                    <label className="form-check-label" htmlFor="autoStop">
                                                        Auto-stop on high loss
                                                    </label>
                                                </div>
                                            </Card.Body>
                                        </Card>
                                    </Col>
                                </Row>
                            </Tab.Pane>
                        </Tab.Content>
                    </Tab.Container>
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
        return <div className="text-muted">No tokens configured. Add tokens to start tracking.</div>;
    }

    return (
        <Table striped bordered hover size="sm">
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
                        <td>{token.name || '-'}</td>
                        <td><span className="badge bg-secondary">{token.chain}</span></td>
                        <td className="text-truncate" style={{ maxWidth: 150 }}>
                            <small>{token.address.slice(0, 10)}...{token.address.slice(-6)}</small>
                        </td>
                        <td>
                            <Button
                                size="sm"
                                variant="outline-danger"
                                onClick={() => onRemove && onRemove(token.id, token.symbol)}
                                disabled={loading}
                            >
                                {loading ? <Spinner size="sm" /> : 'Remove'}
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
        return <div className="text-muted">No providers configured. Add RPC providers for blockchain connectivity.</div>;
    }

    return (
        <Table striped bordered hover size="sm">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>URL</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {providers.map((provider) => (
                    <tr key={provider.id}>
                        <td><strong>{provider.name}</strong></td>
                        <td><span className="badge bg-info">{provider.kind}</span></td>
                        <td className="text-truncate" style={{ maxWidth: 200 }}>
                            {provider.url}
                        </td>
                        <td>
                            <span className={`badge bg-${provider.enabled ? 'success' : 'secondary'}`}>
                                {provider.enabled ? 'Active' : 'Disabled'}
                            </span>
                        </td>
                        <td>
                            <Button size="sm" variant="outline-secondary">Edit</Button>
                        </td>
                    </tr>
                ))}
            </tbody>
        </Table>
    );
}

function fmtError(e) {
    try {
        const data = e?.response?.data || {};
        const trace = e?.response?.headers?.["x-trace-id"];
        return `${JSON.stringify(data)}${trace ? ` (trace ${trace})` : ""}`;
    } catch {
        return String(e);
    }
}