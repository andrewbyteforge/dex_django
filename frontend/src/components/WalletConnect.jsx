import { useState, useEffect } from 'react';
import { Card, Button, Badge, Alert, Form, Spinner, Table } from 'react-bootstrap';
import { useConnect, useAccount, useDisconnect, useBalance, useChainId, useSwitchChain } from 'wagmi';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import axios from 'axios';

const SUPPORTED_CHAINS = {
    ethereum: { id: 1, name: 'Ethereum', symbol: 'ETH', color: 'primary' },
    base: { id: 8453, name: 'Base', symbol: 'ETH', color: 'info' },
    polygon: { id: 137, name: 'Polygon', symbol: 'MATIC', color: 'success' },
    bsc: { id: 56, name: 'BSC', symbol: 'BNB', color: 'warning' }
};

const TRADING_MODES = {
    paper: { label: '📝 Paper Trading', variant: 'info', description: 'Safe testing with virtual funds' },
    manual: { label: '🔗 Manual Trading', variant: 'primary', description: 'Connect external wallet for real trades' },
    autotrade: { label: '⚡ Autotrade', variant: 'success', description: 'Fully automated trading (Coming Soon)', disabled: true }
};

export function WalletConnect() {
    // State management
    const [selectedMode, setSelectedMode] = useState('paper');
    const [activeChain, setActiveChain] = useState('ethereum');
    const [balances, setBalances] = useState({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [walletStatus, setWalletStatus] = useState({});

    // Wagmi hooks for EVM chains
    const { connectors, connect, isPending: isConnecting, error: connectError } = useConnect();
    const { address: evmAddress, isConnected: evmConnected, chain: currentChain } = useAccount();
    const { disconnect } = useDisconnect();
    const chainId = useChainId();
    const { switchChain } = useSwitchChain();

    // Solana wallet hooks
    const { wallet: solWallet, publicKey: solPubKey, connected: solConnected, select: selectSolWallet } = useWallet();
    const { connection } = useConnection();

    // API client
    const api = axios.create({
        baseURL: 'http://127.0.0.1:8000',
        timeout: 10000
    });

    // Get balance for current chain
    const { data: nativeBalance, refetch: refetchBalance } = useBalance({
        address: evmAddress,
        enabled: evmConnected && selectedMode === 'manual'
    });

    // Update wallet status when connections change
    useEffect(() => {
        updateWalletStatus();
    }, [evmConnected, evmAddress, solConnected, solPubKey, selectedMode, chainId]);

    // Fetch balances when wallet connects
    useEffect(() => {
        if (selectedMode === 'manual' && (evmConnected || solConnected)) {
            fetchBalances();
        }
    }, [evmConnected, solConnected, selectedMode, chainId]);

    const updateWalletStatus = () => {
        const status = {};

        // EVM chains status
        Object.keys(SUPPORTED_CHAINS).forEach(chainName => {
            const chainConfig = SUPPORTED_CHAINS[chainName];
            status[chainName] = {
                connected: evmConnected && chainId === chainConfig.id,
                address: evmConnected && chainId === chainConfig.id ? evmAddress : null,
                chain: chainConfig
            };
        });

        // Solana status
        status.solana = {
            connected: solConnected,
            address: solPubKey?.toString() || null,
            chain: { name: 'Solana', symbol: 'SOL', color: 'warning' }
        };

        setWalletStatus(status);
    };

    const fetchBalances = async () => {
        if (selectedMode !== 'manual') return;

        setLoading(true);
        try {
            const balanceData = {};

            // Fetch EVM balances
            if (evmConnected && evmAddress) {
                const chainName = Object.keys(SUPPORTED_CHAINS).find(
                    name => SUPPORTED_CHAINS[name].id === chainId
                );

                if (chainName && nativeBalance) {
                    balanceData[chainName] = {
                        native: parseFloat(nativeBalance.formatted),
                        symbol: nativeBalance.symbol,
                        tokens: {}
                    };

                    // Fetch token balances via API
                    try {
                        const response = await api.post('/api/v1/wallet/balances', {
                            chain: chainName,
                            address: evmAddress
                        });

                        if (response.data?.status === 'ok') {
                            balanceData[chainName].tokens = response.data.balance?.token_balances || {};
                        }
                    } catch (err) {
                        console.warn(`Failed to fetch ${chainName} token balances:`, err);
                    }
                }
            }

            // Fetch Solana balance
            if (solConnected && solPubKey) {
                try {
                    const balance = await connection.getBalance(solPubKey);
                    balanceData.solana = {
                        native: balance / 1e9, // Convert lamports to SOL
                        symbol: 'SOL',
                        tokens: {}
                    };

                    // Fetch SPL token balances
                    const response = await api.post('/api/v1/wallet/balances', {
                        chain: 'solana',
                        address: solPubKey.toString()
                    });

                    if (response.data?.status === 'ok') {
                        balanceData.solana.tokens = response.data.balance?.token_balances || {};
                    }
                } catch (err) {
                    console.warn('Failed to fetch Solana balances:', err);
                }
            }

            setBalances(balanceData);
        } catch (err) {
            setError(`Failed to fetch balances: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleConnectEVM = async () => {
        if (evmConnected) return;

        try {
            setError(null);
            // Try MetaMask first, fall back to injected
            const metamaskConnector = connectors.find(c => c.name === 'MetaMask');
            const connector = metamaskConnector || connectors[0];

            if (!connector) {
                throw new Error('No wallet connector available');
            }

            await connect({ connector });
        } catch (err) {
            setError(`Failed to connect EVM wallet: ${err.message}`);
        }
    };

    const handleSwitchChain = async (chainName) => {
        const chainConfig = SUPPORTED_CHAINS[chainName];
        if (!chainConfig || !evmConnected) return;

        try {
            setError(null);
            await switchChain({ chainId: chainConfig.id });
            setActiveChain(chainName);
        } catch (err) {
            setError(`Failed to switch to ${chainConfig.name}: ${err.message}`);
        }
    };

    const handleDisconnect = async () => {
        try {
            if (evmConnected) await disconnect();
            setBalances({});
            setError(null);
        } catch (err) {
            setError(`Failed to disconnect: ${err.message}`);
        }
    };

    const handleModeChange = (mode) => {
        setSelectedMode(mode);
        setError(null);

        if (mode === 'paper') {
            setBalances({});
        }
    };

    const getTotalConnected = () => {
        return Object.values(walletStatus).filter(status => status.connected).length;
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>Wallet Connection</strong>
                    <Badge bg={getTotalConnected() > 0 ? "success" : "secondary"}>
                        {getTotalConnected()} Connected
                    </Badge>
                </div>
                {selectedMode === 'manual' && getTotalConnected() > 0 && (
                    <Button variant="outline-danger" size="sm" onClick={handleDisconnect}>
                        Disconnect All
                    </Button>
                )}
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" dismissible onClose={() => setError(null)}>
                        <strong>Error:</strong> {error}
                    </Alert>
                )}

                {/* Trading Mode Selection */}
                <div className="mb-4">
                    <Form.Label><strong>Trading Mode</strong></Form.Label>
                    <div className="d-flex gap-2 flex-wrap">
                        {Object.entries(TRADING_MODES).map(([mode, config]) => (
                            <div key={mode} className="flex-fill">
                                <Form.Check
                                    type="radio"
                                    id={`mode-${mode}`}
                                    name="tradingMode"
                                    checked={selectedMode === mode}
                                    onChange={() => handleModeChange(mode)}
                                    disabled={config.disabled}
                                    label={
                                        <div>
                                            <Badge bg={config.variant} className="me-2">
                                                {config.label}
                                            </Badge>
                                            <div className="small text-muted">
                                                {config.description}
                                            </div>
                                        </div>
                                    }
                                />
                            </div>
                        ))}
                    </div>
                </div>

                {/* Manual Trading Mode */}
                {selectedMode === 'manual' && (
                    <div>
                        <div className="row mb-4">
                            {/* EVM Chains */}
                            <div className="col-lg-8">
                                <h6 className="mb-3">EVM Chains</h6>
                                <div className="row g-2">
                                    {Object.entries(SUPPORTED_CHAINS).map(([chainName, chainConfig]) => {
                                        const status = walletStatus[chainName];
                                        const balance = balances[chainName];

                                        return (
                                            <div key={chainName} className="col-md-6">
                                                <Card className="h-100" style={{ borderColor: status?.connected ? '#28a745' : '#dee2e6' }}>
                                                    <Card.Body className="p-3">
                                                        <div className="d-flex justify-content-between align-items-center mb-2">
                                                            <Badge bg={chainConfig.color}>{chainConfig.name}</Badge>
                                                            <Badge bg={status?.connected ? "success" : "secondary"}>
                                                                {status?.connected ? "Connected" : "Disconnected"}
                                                            </Badge>
                                                        </div>

                                                        {status?.connected && status.address && (
                                                            <div className="mb-2">
                                                                <small className="text-muted">Address:</small>
                                                                <div className="small font-monospace">
                                                                    {status.address.slice(0, 8)}...{status.address.slice(-6)}
                                                                </div>
                                                            </div>
                                                        )}

                                                        {balance && (
                                                            <div className="mb-2">
                                                                <small className="text-muted">Balance:</small>
                                                                <div className="fw-bold">
                                                                    {balance.native.toFixed(4)} {balance.symbol}
                                                                </div>
                                                                {Object.keys(balance.tokens).length > 0 && (
                                                                    <div className="small text-muted">
                                                                        +{Object.keys(balance.tokens).length} tokens
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}

                                                        <div className="d-flex gap-2">
                                                            {!evmConnected ? (
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline-primary"
                                                                    onClick={handleConnectEVM}
                                                                    disabled={isConnecting}
                                                                    className="flex-fill"
                                                                >
                                                                    {isConnecting ? <Spinner size="sm" /> : 'Connect'}
                                                                </Button>
                                                            ) : status?.connected ? (
                                                                <Button size="sm" variant="success" disabled className="flex-fill">
                                                                    Active
                                                                </Button>
                                                            ) : (
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline-secondary"
                                                                    onClick={() => handleSwitchChain(chainName)}
                                                                    className="flex-fill"
                                                                >
                                                                    Switch
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </Card.Body>
                                                </Card>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Solana */}
                            <div className="col-lg-4">
                                <h6 className="mb-3">Solana</h6>
                                <Card className="h-100" style={{ borderColor: solConnected ? '#28a745' : '#dee2e6' }}>
                                    <Card.Body className="p-3">
                                        <div className="d-flex justify-content-between align-items-center mb-2">
                                            <Badge bg="warning">Solana</Badge>
                                            <Badge bg={solConnected ? "success" : "secondary"}>
                                                {solConnected ? "Connected" : "Disconnected"}
                                            </Badge>
                                        </div>

                                        {solConnected && solPubKey && (
                                            <div className="mb-2">
                                                <small className="text-muted">Address:</small>
                                                <div className="small font-monospace">
                                                    {solPubKey.toString().slice(0, 8)}...{solPubKey.toString().slice(-6)}
                                                </div>
                                            </div>
                                        )}

                                        {balances.solana && (
                                            <div className="mb-2">
                                                <small className="text-muted">Balance:</small>
                                                <div className="fw-bold">
                                                    {balances.solana.native.toFixed(4)} SOL
                                                </div>
                                                {Object.keys(balances.solana.tokens).length > 0 && (
                                                    <div className="small text-muted">
                                                        +{Object.keys(balances.solana.tokens).length} tokens
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <div className="d-flex justify-content-center">
                                            <WalletMultiButton className="btn btn-outline-primary btn-sm" />
                                        </div>
                                    </Card.Body>
                                </Card>
                            </div>
                        </div>

                        {/* Balance Loading Indicator */}
                        {loading && (
                            <div className="text-center py-3">
                                <Spinner className="me-2" />
                                Loading balances...
                            </div>
                        )}

                        {/* Connected Wallets Summary */}
                        {getTotalConnected() > 0 && (
                            <Alert variant="success">
                                <div className="d-flex align-items-center gap-2">
                                    <span>✅</span>
                                    <div>
                                        <strong>Ready for Manual Trading</strong>
                                        <div>
                                            {getTotalConnected()} wallet{getTotalConnected() > 1 ? 's' : ''} connected.
                                            You can now execute trades with manual approval.
                                        </div>
                                    </div>
                                </div>
                            </Alert>
                        )}
                    </div>
                )}

                {/* Paper Trading Mode */}
                {selectedMode === 'paper' && (
                    <Alert variant="info">
                        <div className="d-flex align-items-center gap-2">
                            <span>📝</span>
                            <div>
                                <strong>Paper Trading Mode Active</strong>
                                <div>No real funds needed. Test your strategies with virtual balances!</div>
                            </div>
                        </div>
                    </Alert>
                )}
            </Card.Body>
        </Card>
    );
}