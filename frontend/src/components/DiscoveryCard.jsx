import { useState, useEffect } from 'react';
import { Card, Button, Alert, Badge, Form } from 'react-bootstrap';
import { useDjangoData, djangoApi } from '../hooks/useDjangoApi'; // Fix this import

export function DiscoveryCard() {
    const [discoveryRunning, setDiscoveryRunning] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Use useDjangoData for status
    const {
        data: discoveryStatus,
        refresh: refreshStatus
    } = useDjangoData('/api/v1/discovery/status', {
        running: false,
        last_scan: null,
        total_discovered: 0
    });

    const {
        data: recentDiscoveries,
        refresh: refreshDiscoveries
    } = useDjangoData('/api/v1/discovery/recent', []);

    useEffect(() => {
        setDiscoveryRunning(discoveryStatus.running || false);
    }, [discoveryStatus]);

    const toggleDiscovery = async () => {
        setLoading(true);
        setError(null);

        try {
            const endpoint = discoveryRunning ?
                '/api/v1/discovery/stop' :
                '/api/v1/discovery/start';

            const response = await djangoApi.post(endpoint);
            setDiscoveryRunning(response.data.running);
            refreshStatus();
        } catch (err) {
            setError(err.response?.data?.error || 'Discovery toggle failed');
        } finally {
            setLoading(false);
        }
    };

    const forceScan = async () => {
        setLoading(true);
        setError(null);

        try {
            await djangoApi.post('/api/v1/discovery/scan');
            refreshStatus();
            refreshDiscoveries();
        } catch (err) {
            setError(err.response?.data?.error || 'Force scan failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card className="mb-4">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <div className="d-flex align-items-center gap-2">
                    <strong>🔍 Discovery Engine</strong>
                    <Badge bg={discoveryRunning ? 'success' : 'secondary'}>
                        {discoveryRunning ? 'RUNNING' : 'STOPPED'}
                    </Badge>
                </div>
                <div className="d-flex gap-2 align-items-center">
                    <Button
                        size="sm"
                        variant="outline-primary"
                        onClick={forceScan}
                        disabled={loading}
                    >
                        Force Scan
                    </Button>
                    <Form.Check
                        type="switch"
                        id="discovery-switch"
                        checked={discoveryRunning}
                        onChange={toggleDiscovery}
                        disabled={loading}
                    />
                </div>
            </Card.Header>

            <Card.Body>
                {error && (
                    <Alert variant="danger" className="mb-3">
                        {error}
                    </Alert>
                )}

                <div className="row text-center mb-3">
                    <div className="col-md-4">
                        <div className="fw-bold">Total Discovered</div>
                        <div className="fs-5">{discoveryStatus.total_discovered || 0}</div>
                    </div>
                    <div className="col-md-4">
                        <div className="fw-bold">Last Scan</div>
                        <div className="fs-6">
                            {discoveryStatus.last_scan ?
                                new Date(discoveryStatus.last_scan).toLocaleTimeString() :
                                'Never'
                            }
                        </div>
                    </div>
                    <div className="col-md-4">
                        <div className="fw-bold">Recent Found</div>
                        <div className="fs-5">{recentDiscoveries.length || 0}</div>
                    </div>
                </div>

                {recentDiscoveries.length > 0 && (
                    <div>
                        <h6>Recent Discoveries:</h6>
                        <div className="d-flex flex-wrap gap-1">
                            {recentDiscoveries.slice(0, 5).map((discovery, index) => (
                                <Badge key={index} bg="info" className="font-monospace">
                                    {discovery.symbol || 'TOKEN'}
                                </Badge>
                            ))}
                        </div>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
}