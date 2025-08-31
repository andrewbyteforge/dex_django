import { Badge, Card, Button, ButtonGroup } from 'react-bootstrap';
import { WalletConnectButton } from './WalletConnectButton';

export function DashboardHeader({ botStatus, onEmergencyStop, onExportLogs }) {
    const getBotStatusColor = (status) => {
        switch (status?.toLowerCase()) {
            case 'running': return 'success';
            case 'stopped': return 'danger';
            case 'paused': return 'warning';
            default: return 'secondary';
        }
    };

    const getBotStatusIcon = (status) => {
        switch (status?.toLowerCase()) {
            case 'running': return '🟢';
            case 'stopped': return '🔴';
            case 'paused': return '🟡';
            default: return '⚪';
        }
    };

    return (
        <Card className="mb-4">
            <Card.Header className="bg-dark text-white">
                <div className="d-flex justify-content-between align-items-center">
                    {/* Left side - Bot Status */}
                    <div className="d-flex align-items-center gap-3">
                        <div>
                            <strong>DEX Sniper Pro</strong>
                            <div className="small text-muted">Professional Trading Bot</div>
                        </div>
                        <div className="d-flex align-items-center gap-2">
                            <span>{getBotStatusIcon(botStatus?.status)}</span>
                            <Badge bg={getBotStatusColor(botStatus?.status)}>
                                {botStatus?.status?.toUpperCase() || 'UNKNOWN'}
                            </Badge>
                        </div>
                    </div>

                    {/* Right side - Controls */}
                    <div className="d-flex align-items-center gap-2">
                        {/* Wallet Connection */}
                        <WalletConnectButton />

                        {/* Quick Actions */}
                        <ButtonGroup size="sm">
                            <Button
                                variant="outline-warning"
                                onClick={onEmergencyStop}
                                title="Emergency Stop"
                            >
                                🛑
                            </Button>
                            <Button
                                variant="outline-info"
                                onClick={onExportLogs}
                                title="Export Logs"
                            >
                                📊
                            </Button>
                        </ButtonGroup>
                    </div>
                </div>
            </Card.Header>
        </Card>
    );
}