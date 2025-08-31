import { useEffect, useState } from "react";
import { Card, Table, Spinner, Alert, Button, Form, InputGroup } from "react-bootstrap";
import api from "../lib/api";

export default function TokensPanel() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState(null);

    const [form, setForm] = useState({
        chain: "ethereum",
        address: "",
        symbol: "",
        name: "",
        decimals: 18,
        fee_on_transfer: false,
    });
    const [submitting, setSubmitting] = useState(false);

    const load = () => {
        setLoading(true);
        setErr(null);
        api.get("/api/v1/tokens/")
            .then(res => {
                const d = res.data;
                const items = Array.isArray(d) ? d : (d?.results ?? []);
                setRows(items);
            })
            .catch(e => setErr(e))
            .finally(() => setLoading(false));
    };

    useEffect(() => { load(); }, []);

    const onSubmit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        setErr(null);
        try {
            await api.post("/api/v1/tokens/", {
                ...form,
                decimals: Number(form.decimals),
            });
            setForm({
                chain: "ethereum",
                address: "",
                symbol: "",
                name: "",
                decimals: 18,
                fee_on_transfer: false,
            });
            load();
        } catch (e) {
            setErr(e);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Card className="shadow-sm">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <span>Tokens</span>
                <Button size="sm" variant="outline-secondary" onClick={load} disabled={loading}>
                    Refresh
                </Button>
            </Card.Header>
            <Card.Body>
                {err && <Alert variant="danger" className="mb-3">{fmtError(err)}</Alert>}

                <Form onSubmit={onSubmit} className="mb-3">
                    <div className="d-flex gap-2 flex-wrap">
                        <Form.Select
                            size="sm"
                            value={form.chain}
                            onChange={(e) => setForm({ ...form, chain: e.target.value })}
                            style={{ width: 150 }}
                        >
                            <option value="ethereum">ethereum</option>
                            <option value="bsc">bsc</option>
                            <option value="polygon">polygon</option>
                            <option value="solana">solana</option>
                        </Form.Select>

                        <InputGroup style={{ minWidth: 320 }}>
                            <Form.Control
                                size="sm"
                                placeholder="Token address (EVM) or mint (Solana)"
                                value={form.address}
                                onChange={(e) => setForm({ ...form, address: e.target.value })}
                                required
                            />
                        </InputGroup>

                        <Form.Control
                            size="sm"
                            placeholder="Symbol (e.g., USDC)"
                            value={form.symbol}
                            onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                            required
                            style={{ width: 140 }}
                        />

                        <Form.Control
                            size="sm"
                            placeholder="Name (e.g., USD Coin)"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            required
                            style={{ minWidth: 220 }}
                        />

                        <Form.Control
                            size="sm"
                            type="number"
                            placeholder="Decimals"
                            value={form.decimals}
                            onChange={(e) => setForm({ ...form, decimals: e.target.value })}
                            style={{ width: 110 }}
                        />

                        <Form.Check
                            type="switch"
                            id="token-fee-transfer"
                            label="Fee-on-transfer"
                            checked={form.fee_on_transfer}
                            onChange={(e) => setForm({ ...form, fee_on_transfer: e.target.checked })}
                        />

                        <Button size="sm" type="submit" disabled={submitting}>
                            {submitting ? "Adding..." : "Add"}
                        </Button>
                    </div>
                </Form>

                {loading ? (
                    <Spinner />
                ) : (
                    <Table striped hover size="sm" className="align-middle">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Chain</th>
                                <th>Symbol</th>
                                <th>Name</th>
                                <th>Decimals</th>
                                <th>Address</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows?.map(t => (
                                <tr key={t.id}>
                                    <td>{t.id}</td>
                                    <td>{t.chain}</td>
                                    <td>{t.symbol}</td>
                                    <td>{t.name}</td>
                                    <td>{t.decimals}</td>
                                    <td className="text-truncate" style={{ maxWidth: 360 }}>{t.address}</td>
                                </tr>
                            ))}
                            {!rows?.length && (
                                <tr><td colSpan={6} className="text-muted">No tokens yet.</td></tr>
                            )}
                        </tbody>
                    </Table>
                )}
            </Card.Body>
        </Card>
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