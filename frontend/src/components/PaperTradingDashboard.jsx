import { Container, Row, Col } from 'react-bootstrap';
import { PaperTradeCard } from './PaperTradeCard';
import { AIThoughtLogPanel } from './AIThoughtLogPanel';

export function PaperTradingDashboard() {
    return (
        <Container fluid className="py-4">
            <Row>
                {/* Left Column - Paper Trading Controls */}
                <Col lg={4} className="mb-4">
                    <PaperTradeCard />

                    {/* Additional controls or info could go here */}
                    <div className="text-muted small text-center">
                        <p className="mb-1">
                            <strong>Paper Trading Mode:</strong> Practice trading with virtual funds
                        </p>
                        <p className="mb-0">
                            All trades are simulated • No real money at risk • Same logic as live trading
                        </p>
                    </div>
                </Col>

                {/* Right Column - AI Thought Log */}
                <Col lg={8}>
                    <AIThoughtLogPanel />
                </Col>
            </Row>
        </Container>
    );
}