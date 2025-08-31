import { useEffect, useState } from "react";
import { Card, Button, Badge, Spinner, Row, Col, Form, Alert } from "react-bootstrap";
import api from "../lib/api";

export default function BotControl() {
    const [status, setStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [err, setErr] = useState(null);

    const [form, setForm] = useState(null);
    const [saving, setSaving] = useState(false);

    const load = async () => {
        try {
            setLoading(true);
            setErr(null);
            const [st, bs] = await Promise.all([
                api.get("/api/v1/bot/status"),
                api.get("/api/v1/bot/settings"),
            ]);
            setStatus(st.data.status);
            setForm(bs.data);
        } catch (e) {
            setErr(e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { load(); }, []);

    const onStart = async () => {
        await api.post("/api/v1/bot/start");
        load();
    };
    const onStop = async () => {
        await api.post("/api/v1/bot/stop");
        load();
    };

    const onSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload = {
                autotrade_enabled: form.autotrade_enabled,
                mainnet_enabled: form.mainnet_enabled,
                base_currency: form.base_currency,
                per_trade_cap_base: Number(form.per_trade_cap_base),
                daily_cap_base: Number(form.daily_cap_base),
                hot_wallet_hard_cap_base: Number(form.hot_wallet_hard_cap_base),
                slippage_bps_new_pair: Number(form.slippage_bps_new_pair),
                slippage_bps_normal: Number(form.slippage_bps_normal),
                tp_percent: Number(form.tp_percent),
                sl_percent: Number(form.sl_percent),
                trailing_percent: Number(form.trailing_percent),
            };
            await api.put("/api/v1/bot/settings", payload);
            load();
        } catch (e) {
            setErr(e);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Card className="shadow-sm">
            <Card.Header className="d-flex justify-content-between align-items-center">
                <span>Bot Control</span>
                <div>
                    {status?.running ? (
                        <Badge bg="success">Running</Badge>
                    ) : (
                        <Badge bg="secondary">Stopped</Badge>
                    )}
                </div>
            </Card.Header>
            <Card.Body>
                {loading && <Spinner />}
                {err && <Alert variant="danger">{fmtError(err)}</Alert>}

                {!loading && (
                    <>
                        <div className="mb-3 d-flex gap-2">
                            <Button size="sm" variant="primary" onClick={onStart} disabled={status?.running}>
                                Start
                            </Button>
                            <Button size="sm" variant="outline-danger" onClick={onStop} disabled={!status?.running}>
                                Stop
                            </Button>
                            <div className="small text-muted ms-2">
                                loops: {status?.loop_count ?? 0} · last beat: {status?.last_beat ?? "-"}
                            </div>
                        </div>

                        {form && (
                            <Form onSubmit={onSave}>
                                <Row className="g-2">
                                    <Col xs={6} md={3}>
                                        <Form.Check
                                            type="switch"
                                            label="Mainnet enabled"
                                            checked={form.mainnet_enabled}
                                            onChange={(e) => setForm({ ...form, mainnet_enabled: e.target.checked })}
                                        />
                                    </Col>
                                    <Col xs={6} md={3}>
                                        <Form.Check
                                            type="switch"
                                            label="Autotrade enabled"
                                            checked={form.autotrade_enabled}
                                            onChange={(e) => setForm({ ...form, autotrade_enabled: e.target.checked })}
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            value={form.base_currency}
                                            onChange={(e) => setForm({ ...form, base_currency: e.target.value })}
                                            placeholder="Base (GBP)"
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.per_trade_cap_base}
                                            onChange={(e) => setForm({ ...form, per_trade_cap_base: e.target.value })}
                                            placeholder="Per trade cap"
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.daily_cap_base}
                                            onChange={(e) => setForm({ ...form, daily_cap_base: e.target.value })}
                                            placeholder="Daily cap"
                                        />
                                    </Col>
                                    <Col xs={6} md={3}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.hot_wallet_hard_cap_base}
                                            onChange={(e) => setForm({ ...form, hot_wallet_hard_cap_base: e.target.value })}
                                            placeholder="Hot wallet cap"
                                        />
                                    </Col>
                                    <Col xs={6} md={3}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.slippage_bps_new_pair}
                                            onChange={(e) => setForm({ ...form, slippage_bps_new_pair: e.target.value })}
                                            placeholder="New pair slippage bps"
                                        />
                                    </Col>
                                    <Col xs={6} md={3}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.slippage_bps_normal}
                                            onChange={(e) => setForm({ ...form, slippage_bps_normal: e.target.value })}
                                            placeholder="Normal slippage bps"
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.tp_percent}
                                            onChange={(e) => setForm({ ...form, tp_percent: e.target.value })}
                                            placeholder="TP %"
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.sl_percent}
                                            onChange={(e) => setForm({ ...form, sl_percent: e.target.value })}
                                            placeholder="SL %"
                                        />
                                    </Col>
                                    <Col xs={6} md={2}>
                                        <Form.Control
                                            size="sm"
                                            type="number"
                                            value={form.trailing_percent}
                                            onChange={(e) => setForm({ ...form, trailing_percent: e.target.value })}
                                            placeholder="Trail %"
                                        />
                                    </Col>
                                </Row>
                                <div className="mt-3">
                                    <Button size="sm" type="submit" disabled={saving}>
                                        {saving ? "Saving..." : "Save Settings"}
                                    </Button>
                                </div>
                            </Form>
                        )}
                    </>
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
