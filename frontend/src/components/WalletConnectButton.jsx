import { useState } from 'react';
import { Button, Badge, Dropdown, Modal } from 'react-bootstrap';
import { useAccount, useDisconnect } from 'wagmi';
import { useWallet } from '@solana/wallet-adapter-react';
import { WalletConnect } from './WalletConnect';

export function WalletConnectButton() {
    const [showWalletModal, setShowWalletModal] = useState(false);

    // EVM wallet state
    const { address: evmAddress, isConnected: evmConnected, chain } = useAccount();
    const { disconnect } = useDisconnect();

    // Solana wallet state
    const { publicKey: solPubKey, connected: solConnected, disconnect: solDisconnect } = useWallet();

    const getConnectionStatus = () => {
        const connections = [];

        if (evmConnected && evmAddress) {
            connections.push({
                type: 'EVM',
                chain: chain?.name || 'Unknown',
                address: evmAddress,
                color: 'primary'
            });
        }

        if (solConnected && solPubKey) {
            connections.push({
                type: 'Solana',
                chain: 'Solana',
                address: solPubKey.toString(),
                color: 'warning'
            });
        }

        return connections;
    };

    const connections = getConnectionStatus();
    const isConnected = connections.length > 0;

    const handleDisconnectAll = async () => {
        try {
            if (evmConnected) await disconnect();
            if (solConnected) await solDisconnect();
        } catch (error) {
            console.error('Error disconnecting wallets:', error);
        }
    };

    const formatAddress = (address) => {
        if (!address) return '';
        return `${address.slice(0, 6)}...${address.slice(-4)}`;
    };

    if (isConnected) {
        return (
            <>
                <Dropdown>
                    <Dropdown.Toggle
                        variant="success"
                        size="sm"
                        className="d-flex align-items-center gap-2"
                    >
                        <span>🔗</span>
                        <span className="d-none d-md-inline">
                            {connections.length} Wallet{connections.length > 1 ? 's' : ''} Connected
                        </span>
                        <span className="d-md-none">Connected</span>
                    </Dropdown.Toggle>

                    <Dropdown.Menu>
                        <Dropdown.Header>Connected Wallets</Dropdown.Header>

                        {connections.map((conn, idx) => (
                            <Dropdown.Item key={idx} className="d-flex justify-content-between align-items-center">
                                <div>
                                    <Badge bg={conn.color} className="me-2">{conn.type}</Badge>
                                    <small>{conn.chain}</small>
                                    <div className="small text-muted font-monospace">
                                        {formatAddress(conn.address)}
                                    </div>
                                </div>
                            </Dropdown.Item>
                        ))}

                        <Dropdown.Divider />
                        <Dropdown.Item onClick={() => setShowWalletModal(true)}>
                            ⚙️ Manage Wallets
                        </Dropdown.Item>
                        <Dropdown.Item onClick={handleDisconnectAll} className="text-danger">
                            🔌 Disconnect All
                        </Dropdown.Item>
                    </Dropdown.Menu>
                </Dropdown>

                {/* Wallet Management Modal */}
                <Modal show={showWalletModal} onHide={() => setShowWalletModal(false)} size="lg">
                    <Modal.Header closeButton>
                        <Modal.Title>Wallet Management</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <WalletConnect />
                    </Modal.Body>
                </Modal>
            </>
        );
    }

    // Not connected state
    return (
        <>
            <Button
                variant="outline-primary"
                size="sm"
                onClick={() => setShowWalletModal(true)}
                className="d-flex align-items-center gap-2"
            >
                <span>🔗</span>
                <span className="d-none d-sm-inline">Connect Wallet</span>
                <span className="d-sm-none">Connect</span>
            </Button>

            {/* Wallet Connection Modal */}
            <Modal show={showWalletModal} onHide={() => setShowWalletModal(false)} size="lg">
                <Modal.Header closeButton>
                    <Modal.Title>Connect Your Wallet</Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    <WalletConnect />
                </Modal.Body>
            </Modal>
        </>
    );
}