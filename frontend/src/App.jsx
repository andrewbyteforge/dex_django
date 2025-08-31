import { useEffect, useState } from "react";
import { Container, Row, Col, Card, Spinner, Table, Alert, Button } from "react-bootstrap";
import api from "./lib/api";
import ProvidersPanel from "./components/Providers.jsx";
import TokensPanel from "./components/Tokens.jsx";
import BotControl from "./components/BotControl.jsx";

function useFetch(url) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        let cancel = false;
        setLoading(true);
        setError(null);

        api
            .get(url)
            .then((res) => !cancel && setData(res.data))
            .catch((err) => !cancel && setError(err))
            .finally(() => !cancel && setLoading(false));

        return () => {
            cancel = true;
        };
    }, [url]);

    return { data, loading, error };
}


export default function App() {
    const { data: health, loading: healthLoading, error: healthError } = useFetch("/api/v1/health");

    const [page, setPage] = useState(1);
    const { data: trades, loading: tradesLoading, error: tradesError } = useFetch(`/api/v1/trades/?page=${page}`);

    const canPrev = Boolean(trades?.previous);
    const canNext = Boolean(trades?.next);

    return (
        <Container className="py-4">
            <Row>
                <Col md={12} className="mb-3">
                    <BotControl />
                </Col>

                <Col md={4}>
                    <Card className="mb-3 shadow-sm">
                        <Card.Header>Health</Card.Header>
                        <Card.Body>
                            {healthLoading && <Spinner />}
                            {healthError && <Alert variant="danger">{fmtError(healthError)}</Alert>}
                            {health && <pre className="mb-0 small">{JSON.stringify(health, null, 2)}</pre>}
                        </Card.Body>
                    </Card>
                </Col>

                <Col md={8}>
                    <Card className="shadow-sm">
                        <Card.Header className="d-flex justify-content-between align-items-center">
                            <span>Trades</span>
                            <div className="d-flex align-items-center gap-2">
                                <span className="small text-muted">
                                    count: {trades?.count ?? 0} · page: {page}
                                </span>
                                <Button
                                    size="sm"
                                    variant="outline-secondary"
                                    disabled={!canPrev}
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                >
                                    Prev
                                </Button>
                                <Button
                                    size="sm"
                                    variant="outline-secondary"
                                    disabled={!canNext}
                                    onClick={() => setPage((p) => p + 1)}
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

                    <div className="mt-3">
                        <ProvidersPanel />
                    </div>
                    <div className="mt-3">
                        <TokensPanel />
                    </div>                 
                </Col>
            </Row>
        </Container>
    );
}

function TradesTable({ results }) {
    return (
        <Table striped bordered hover size="sm" className="align-middle">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Side</th>
                    <th>Amount In</th>
                    <th>Status</th>
                    <th>Tx Hash</th>
                </tr>
            </thead>
            <tbody>
                {results.map((t) => (
                    <tr key={t.id}>
                        <td>{t.id}</td>
                        <td className={t.side === "buy" ? "text-success" : "text-danger"}>{t.side}</td>
                        <td>{t.amount_in}</td>
                        <td>{t.status}</td>
                        <td className="text-truncate" style={{ maxWidth: 180 }}>{t.tx_hash || "-"}</td>
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
