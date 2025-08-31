import { useState } from 'react';
import { Modal, Button, Form, Alert, Spinner } from 'react-bootstrap';

export function TokenModal({ show, onHide, onSave, loading, error }) {
    const [formData, setFormData] = useState({
        symbol: '',
        name: '',
        chain: 'ethereum',
        address: '',
        decimals: 18,
        fee_on_transfer: false
    });

    const [validated, setValidated] = useState(false);

    const handleSubmit = (event) => {
        event.preventDefault();
        const form = event.currentTarget;

        console.log('Form submitted with data:', formData);

        if (form.checkValidity()) {
            console.log('Form is valid, calling onSave...');
            onSave(formData);
        } else {
            console.log('Form validation failed');
            setValidated(true);
        }
    };

    const handleInputChange = (field, value) => {
        setFormData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleClose = () => {
        setFormData({
            symbol: '',
            name: '',
            chain: 'ethereum',
            address: '',
            decimals: 18,
            fee_on_transfer: false
        });
        setValidated(false);
        onHide();
    };

    return (
        <Modal show={show} onHide={handleClose} size="lg">
            <Modal.Header closeButton>
                <Modal.Title>Add New Token</Modal.Title>
            </Modal.Header>

            <Form noValidate validated={validated} onSubmit={handleSubmit}>
                <Modal.Body>
                    {error && (
                        <Alert variant="danger">
                            <strong>Error:</strong> {error.error || error.message || JSON.stringify(error)}
                            {error.details && (
                                <div className="mt-2">
                                    <strong>Details:</strong>
                                    <pre className="mt-1">{JSON.stringify(error.details, null, 2)}</pre>
                                </div>
                            )}
                        </Alert>
                    )}

                    <div className="row">
                        <div className="col-md-6">
                            <Form.Group className="mb-3">
                                <Form.Label>Symbol *</Form.Label>
                                <Form.Control
                                    type="text"
                                    placeholder="e.g. USDC"
                                    value={formData.symbol}
                                    onChange={(e) => handleInputChange('symbol', e.target.value.toUpperCase())}
                                    required
                                    maxLength="24"
                                />
                                <Form.Control.Feedback type="invalid">
                                    Please provide a valid token symbol.
                                </Form.Control.Feedback>
                            </Form.Group>
                        </div>

                        <div className="col-md-6">
                            <Form.Group className="mb-3">
                                <Form.Label>Chain *</Form.Label>
                                <Form.Select
                                    value={formData.chain}
                                    onChange={(e) => handleInputChange('chain', e.target.value)}
                                    required
                                >
                                    <option value="ethereum">Ethereum</option>
                                    <option value="bsc">BSC</option>
                                    <option value="polygon">Polygon</option>
                                    <option value="base">Base</option>
                                    <option value="solana">Solana</option>
                                </Form.Select>
                            </Form.Group>
                        </div>
                    </div>

                    <Form.Group className="mb-3">
                        <Form.Label>Name</Form.Label>
                        <Form.Control
                            type="text"
                            placeholder="e.g. USD Coin"
                            value={formData.name}
                            onChange={(e) => handleInputChange('name', e.target.value)}
                            maxLength="120"
                        />
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>Contract Address *</Form.Label>
                        <Form.Control
                            type="text"
                            placeholder="0x..."
                            value={formData.address}
                            onChange={(e) => handleInputChange('address', e.target.value)}
                            required
                            maxLength="100"
                        />
                        <Form.Control.Feedback type="invalid">
                            Please provide a valid contract address.
                        </Form.Control.Feedback>
                    </Form.Group>

                    <div className="row">
                        <div className="col-md-6">
                            <Form.Group className="mb-3">
                                <Form.Label>Decimals</Form.Label>
                                <Form.Control
                                    type="number"
                                    min="0"
                                    max="255"
                                    value={formData.decimals}
                                    onChange={(e) => handleInputChange('decimals', parseInt(e.target.value) || 18)}
                                />
                            </Form.Group>
                        </div>

                        <div className="col-md-6">
                            <Form.Group className="mb-3">
                                <Form.Check
                                    type="checkbox"
                                    label="Fee on Transfer Token"
                                    checked={formData.fee_on_transfer}
                                    onChange={(e) => handleInputChange('fee_on_transfer', e.target.checked)}
                                    className="mt-4"
                                />
                            </Form.Group>
                        </div>
                    </div>
                </Modal.Body>

                <Modal.Footer>
                    <Button variant="secondary" onClick={handleClose} disabled={loading}>
                        Cancel
                    </Button>
                    <Button variant="primary" type="submit" disabled={loading}>
                        {loading && <Spinner size="sm" className="me-2" />}
                        Add Token
                    </Button>
                </Modal.Footer>
            </Form>
        </Modal>
    );
}