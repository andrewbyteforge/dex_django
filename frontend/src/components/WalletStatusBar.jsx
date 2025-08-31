import { Alert, Badge, Button } from 'react-bootstrap';
import { useAccount } from 'wagmi';
import { useWallet } from '@solana/wallet-adapter-react';

export function WalletStatusBar({ tradingMode = 'paper' }) {
    const { address: evmAddress, isConnected: evmConnected, chain } = useAccount();
    const { publicKey: solPubKey, connected: solConnected } = useWallet();

    const getConnectionCount = () => {
        let count = 0;
        if (evmConnected) count++;
        if (solConnected) count++;
        return count;
    };

    const connectionCount = getConnectionCount();

    if (tradingMode === 'paper') {
        return (
            <Alert variant="info" className="mb-3 d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <span>📝</span>
                    <div>
                        <strong>Paper Trading Mode</strong>
                        <div className="small">Testing with virtual funds - no wallet required</div>
                    </div>
                </div>
                <Badge bg="info">SAFE MODE</Badge>
            </Alert>
        );
    }

    if (connectionCount === 0) {
        return (
            <Alert variant="warning" className="mb-3 d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <span>⚠️</span>
                    <div>
                        <strong>No Wallet Connected</strong>
                        <div className="small">Connect your wallet to start manual trading</div>
                    </div>
                </div>
                <Badge bg="warning">DISCONNECTED</Badge>
            </Alert>
        );
    }

    return (
        <Alert variant="success" className="mb-3 d-flex justify-content-between align-items-center">
            <div className="d-flex align-items-center gap-2">
                <span>✅</span>
                <div>
                    <strong>Wallet Connected</strong>
                    <div className="small">
                        {connectionCount} wallet{connectionCount > 1 ? 's' : ''} ready for trading
                        {chain && <span className="ms-1">• Active: {chain.name}</span>}
                    </div>
                </div>
            </div>
            <Badge bg="success">READY</Badge>
        </Alert>
    );
}