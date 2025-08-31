import React from 'react';
import { Card } from 'react-bootstrap';

export const DiscoveryCard = () => {
    return (
        <Card className="mb-3">
            <Card.Header>
                <h5 className="mb-0">Token Discovery</h5>
            </Card.Header>
            <Card.Body>
                <div className="text-muted">
                    <p className="mb-2">Scanning for new token launches...</p>
                    <small>Discovery engine will appear here for first-liquidity sniping opportunities.</small>
                </div>
            </Card.Body>
        </Card>
    );
};