import { useEffect, useState } from "react";
import { Card, Table, Spinner, Alert, Button, Form, InputGroup } from "react-bootstrap";
import api from "../lib/api";

export default function ProvidersPanel() {
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState(null);

    const [form, setForm] = useState({
        name: "",
        kind: "rpc",
        url: "",
        mode: "free",
        enabled: true,
    });
    const [submitting, setSubmitting] = useState(false);

    const load = () => {
        setLoading(true);
        setErr(null);
        api.get("/api/v1/providers/")
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
            await api.post("/api/v1/providers/", form);
            setForm({ name: "", kind: "rpc", url: "", mode: "free", enabled: true });
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
                <span>Providers</span>
                <Button size="sm" variant="outline-secondary" onClick={load} disabled={loading}>
                    Refresh
                </Button>
            </Card.Header>
            <Card.Body>
                {err && <Alert variant="danger" className="mb-3">{fmtError(err)}</Alert>}

                <Form onSubmit={onSubmit} className="mb-3">
                    <div className="d-flex gap-2 flex-wrap">
                        <Form.Control
                            size="sm"
                            placeholder="Name (e.g., Ankr ETH)"
                            value={form.name}
                            onChange={(e) => setForm({ ...form, name: e.target.value })}
                            required
                            style={{ minWidth: 180 }}
                        />
                        <Form.Select
                            size="sm"
                            value={form.kind}
                            onChange={(e) => setForm({ ...form, kind: e.target.value })}
                            style={{ width: 120 }}
                        >
                            <option value="rpc">rpc</option>
                            <option value="ws">ws</option>
                            <option value="mempool">mempool</option>
                            <option value="sim">sim</option>
                        </Form.Select>
                        <InputGroup style={{ minWidth: 320 }}>
                            <Form.Control
                                size="sm"
                                placeholder="URL (https://rpc.ankr.com/eth)"
                                value={form.url}
                                onChange={(e) => setForm({ ...form, url: e.target.value })}
                                required
                            />
                        </InputGroup>
                        <Form.Select
                            size="sm"
                            value={form.mode}
                            onChange={(e) => setForm({ ...form, mode: e.target.value })}
                            style={{ width: 120 }}
                        >
                            <option value="free">free</option>
                            <option value="pro">pro</option>
                        </Form.Select>
                        <Form.Check
                            type="switch"
                            id="provider-enabled"
                            label="Enabled"
                            checked={form.enabled}
                            onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
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
                                <th>Name</th>
                                <th>Kind</th>
                                <th>Mode</th>
                                <th>Enabled</th>
                                <th>URL</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows?.map(p => (
                                <tr key={p.id}>
                                    <td>{p.id}</td>
                                    <td>{p.name}</td>
                                    <td>{p.kind}</td>
                                    <td>{p.mode}</td>
                                    <td>{String(p.enabled)}</td>
                                    <td className="text-truncate" style={{ maxWidth: 360 }}>{p.url}</td>
                                </tr>
                            ))}
                            {!rows?.length && (
                                <tr><td colSpan={6} className="text-muted">No providers yet.</td></tr>
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