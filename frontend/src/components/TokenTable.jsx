import { useState, useEffect } from 'react';
import { Card, Table, Spinner, Alert, Button, Pagination, Form, InputGroup, Badge } from 'react-bootstrap';
import api from '../lib/api';

export default function TokenTable() {
    const [tokens, setTokens] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const [pageSize, setPageSize] = useState(20);

    // Filter state
    const [filters, setFilters] = useState({
        scoreMin: 0,
        scoreMax: 30,
        liquidityMin: 0,
        liquidityMax: 1000000,
        chains: ['ETHEREUM', 'BSC', 'BASE', 'POLYGON', 'SOLANA'],
        sources: ['DEX', 'CG', 'JUP']
    });

    const loadTokens = async (page = 1) => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: pageSize.toString(),
                // Add filter params as needed
                ...filters
            });

            const response = await api.get(`/api/v1/tokens/?${params}`);
            const data = response.data;

            setTokens(data.data || []);
            setTotalPages(data.pagination?.pages || 1);
            setTotalCount(data.pagination?.total || 0);
            setCurrentPage(page);
        } catch (err) {
            setError(err?.response?.data?.message || 'Failed to load tokens');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadTokens(1);
    }, [pageSize, filters]);

    const handlePageChange = (page) => {
        if (page >= 1 && page <= totalPages && page !== currentPage) {
            loadTokens(page);
        }
    };

    const PaginationComponent = () => {
        const pages = [];
        const maxVisiblePages = 5;

        // Calculate start and end pages
        let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

        // Adjust if we're near the end
        if (endPage - startPage < maxVisiblePages - 1) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }

        // First page
        if (startPage > 1) {
            pages.push(
                <Pagination.Item key={1} onClick={() => handlePageChange(1)}>
                    1
                </Pagination.Item>
            );
            if (startPage > 2) {
                pages.push(<Pagination.Ellipsis key="start-ellipsis" />);
            }
        }

        // Visible pages
        for (let i = startPage; i <= endPage; i++) {
            pages.push(
                <Pagination.Item
                    key={i}
                    active={i === currentPage}
                    onClick={() => handlePageChange(i)}
                >
                    {i}
                </Pagination.Item>
            );
        }

        // Last page
        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                pages.push(<Pagination.Ellipsis key="end-ellipsis" />);
            }
            pages.push(
                <Pagination.Item key={totalPages} onClick={() => handlePageChange(totalPages)}>
                    {totalPages}
                </Pagination.Item>
            );
        }

        return (
            <div className="d-flex justify-content-between align-items-center mt-3">
                <div className="d-flex align-items-center gap-2">
                    <small className="text-muted">
                        Showing {((currentPage - 1) * pageSize) + 1} - {Math.min(currentPage * pageSize, totalCount)} of {totalCount}
                    </small>
                    <Form.Select
                        size="sm"
                        value={pageSize}
                        onChange={(e) => setPageSize(parseInt(e.target.value))}
                        style={{ width: 'auto' }}
                    >
                        <option value={10}>10 per page</option>
                        <option value={20}>20 per page</option>
                        <option value={50}>50 per page</option>
                        <option value={100}>100 per page</option>
                    </Form.Select>
                </div>

                <Pagination className="mb-0">
                    <Pagination.Prev
                        disabled={currentPage === 1}
                        onClick={() => handlePageChange(currentPage - 1)}
                    />
                    {pages}
                    <Pagination.Next
                        disabled={currentPage === totalPages}
                        onClick={() => handlePageChange(currentPage + 1)}
                    />
                </Pagination>
            </div>
        );
    };

    return (
        <Card className="shadow-sm">
            <Card.Header>
                <div className="d-flex justify-content-between align-items-center">
                    <span>Token Opportunities</span>
                    <Button
                        size="sm"
                        variant="outline-secondary"
                        onClick={() => loadTokens(currentPage)}
                        disabled={loading}
                    >
                        {loading ? <Spinner size="sm" /> : 'Refresh'}
                    </Button>
                </div>
            </Card.Header>

            <Card.Body className="p-0">
                {error && (
                    <Alert variant="danger" className="mx-3 mt-3">
                        {error}
                    </Alert>
                )}

                <div className="table-responsive">
                    <Table className="table-sm table-striped table-hover mb-0">
                        <thead>
                            <tr>
                                <th>Token Pair</th>
                                <th>Chain</th>
                                <th>DEX</th>
                                <th>Liquidity</th>
                                <th>Source</th>
                                <th>Score</th>
                                <th>Time</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && tokens.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="text-center py-4">
                                        <Spinner />
                                    </td>
                                </tr>
                            ) : tokens.length === 0 ? (
                                <tr>
                                    <td colSpan={8} className="text-center py-4 text-muted">
                                        No tokens found
                                    </td>
                                </tr>
                            ) : (
                                tokens.map((token, index) => (
                                    <tr key={token.id || index}>
                                        <td>
                                            <strong>{token.base_symbol}</strong>
                                            <span className="text-muted">/</span>
                                            <span>{token.quote_symbol}</span>
                                            <div className="small text-muted font-monospace">
                                                {token.address?.substring(0, 8)}...
                                            </div>
                                        </td>
                                        <td>
                                            <Badge bg="secondary">{token.chain}</Badge>
                                        </td>
                                        <td>
                                            <Badge bg="info">{token.dex}</Badge>
                                        </td>
                                        <td>
                                            <span className={`fw-bold ${token.liquidity_usd > 100000 ? 'text-success' :
                                                    token.liquidity_usd > 50000 ? 'text-warning' : 'text-danger'
                                                }`}>
                                                ${token.liquidity_usd?.toLocaleString()}
                                            </span>
                                        </td>
                                        <td>
                                            <Badge bg="primary">{token.source}</Badge>
                                        </td>
                                        <td>
                                            <Badge bg="secondary">{token.score}</Badge>
                                        </td>
                                        <td>
                                            <small className="text-muted">{token.time_ago}</small>
                                        </td>
                                        <td>
                                            <Button size="sm" variant="outline-primary">
                                                Analyze
                                            </Button>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </Table>
                </div>

                {totalCount > 0 && <div className="px-3 pb-3"><PaginationComponent /></div>}
            </Card.Body>
        </Card>
    );
}