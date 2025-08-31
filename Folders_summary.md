**One actionable step:** here’s a clear, app-by-app guide for what each package is for and the kinds of code/classes it should contain. Drop this into your docs so we all file things consistently.

---

# App Responsibilities & What They Should House

## `backend/app/api/` — HTTP API layer

Purpose: Public FastAPI routers and request/response models. No business logic; just validation, auth, orchestration, and mapping to services.

What to put here:

* `APIRouter` modules per domain: `wallet.py`, `quotes.py`, `trades.py`, `pairs.py`, `autotrade.py`, `paper.py`, `health.py`.
* Pydantic request/response models (thin, no DB logic).
* Dependency functions (auth, pagination, idempotency, trace\_id injection).
* Error mappers converting domain exceptions → HTTP errors.

Avoid:

* Direct RPC/DEX calls, SQL, or complex calculations.

---

## `backend/app/core/` — process bootstrapping & cross-cutting concerns

Purpose: App wiring and infrastructure that everything else depends on.

What to put here:

* `settings.py` (Pydantic Settings), `bootstrap.py` (create app, wire routers), `logging_config.py` (JSONL handlers), `middleware_setup.py` (CORS, request IDs).
* `scheduler.py` (APScheduler factory), `retry.py` (tenacity policies), `runtime_state.py` (in-memory flags, WS client registries), `wallet_registry.py` (registered wallets/keystores).
* Exception types shared across layers.

Avoid:

* Feature logic (DEX specifics, strategy decisions).

---

## `backend/app/chains/` — chain clients & RPC pools

Purpose: Low-level blockchain I/O with strict separation per family.

What to put here:

* `evm_client.py`: async client (httpx/websocket) for EVM (nonce, gas, sendRawTx, call, logs).
* `solana_client.py`: async wrappers for RPC/Jito/Jupiter pricing where relevant.
* `rpc_pool.py`: rotating endpoints, health checks, median gas, backoff.

Classes:

* `EvmClient`, `SolanaClient`, `RpcPool`, `GasSnapshot`.

Avoid:

* Trading logic or strategy decisions.

---

## `backend/app/dex/` — DEX adapters (router-first)

Purpose: Uniform interface to different DEXs; quote/build/simulate routes.

What to put here:

* `uniswap_v2.py`, `uniswap_v3.py`, `pancake.py`, `quickswap.py`, `jupiter.py`.
* Interfaces: `DexAdapter` (abstract), `RouteQuote`, `RouteLeg`.

Functions/classes:

* `get_quote(...)`, `build_swap_tx(...)`, `parse_fill(...)`.
* Fee/tick math helpers, pool selectors, slippage calculators.

Avoid:

* Risk scoring, balance reads (delegate to services).

---

## `backend/app/discovery/` — find opportunities

Purpose: Feed the strategy with candidate pairs/trends.

What to put here:

* `dexscreener.py` (poll + normalize), `chain_watchers.py` (new LP events), `mempool_listeners.py` (optional), `trend_aggregator.py`.
* Normalized models: `PairSnapshot`, `TrendSignal`.
* Dedup + freshness logic, rate limits, circuit breakers.

Avoid:

* Executing trades or scoring beyond basic hygiene.

---

## `backend/app/strategy/` — risk, scoring, and order intent

Purpose: Decide *if* and *how* to trade (including Paper mode parity).

What to put here:

* `risk_manager.py` (liquidity thresholds, blacklist/owner flags, tax checks).
* `risk_scoring.py` (composite score), `safety_controls.py` (circuit breakers).
* `autotrade_strategy.py` (profile logic: conservative/standard/aggressive).
* `orders.py` (intent objects: canary/full entry/exit; not signed yet).

Classes:

* `RiskGateResult`, `RiskScore`, `TradeIntent`, `AutotradeProfile`.

Avoid:

* Building/sending raw transactions (that’s `trading/`).

---

## `backend/app/trading/` — execution engine

Purpose: Turn a `TradeIntent` into a simulated or real transaction.

What to put here:

* `executor.py` (decide paper vs live; coordinate with dex adapter).
* `nonce_manager.py`, `approvals.py` (minimal approvals + revoker), `gas_strategy.py` (EIP-1559 targets).
* `settlement.py` (parse receipts, compute realized slippage/fees).

Classes:

* `TradeExecutor`, `ApprovalManager`, `GasStrategy`.

Avoid:

* Discovery or high-level risk logic.

---

## `backend/app/ledger/` — recording & export

Purpose: Persist fills, balances, metrics; export CSV/JSON.

What to put here:

* `ledger_writer.py` (append-only writes; flag `is_paper`), `journals.py` (per-chain journals), `exporters.py`.
* Models: `FillRecord`, `BalanceSnapshot`, `MetricSnapshot`.

Avoid:

* Business decisions; this is audit & analytics storage.

---

## `backend/app/sim/` — simulator & backtester

Purpose: Deterministic testing of strategies and “paper” behavior.

What to put here:

* `simulator.py` (slippage curves, revert probability), `backtester.py` (replay past signals), `metrics.py` (PnL, drawdown, Sharpe-lite).
* Configurable seeds for repeatability.

Avoid:

* Live RPC usage.

---

## `backend/app/ws/` — WebSocket hubs

Purpose: Real-time streaming to the UI.

What to put here:

* `hub.py` (optional central registry), `autotrade_handler.py`, `intelligence_handler.py`, `paper.py`, `metrics.py`.
* Message contracts: `status`, `thought_log`, `paper_order`, `paper_fill`, `session_metrics`, `heartbeat`.

Avoid:

* Doing work; hubs should only broadcast frames produced elsewhere.

---

## `backend/app/services/` — reusable “domain services”

Purpose: Cross-feature utilities used by multiple layers.

What to put here:

* `pricing.py` (FX/GBP conversion, oracle snapshots), `token_metadata.py`, `security_providers.py` (rug lists, owner checks), `alerts.py`, `anomaly_detector.py`.
* Cache layers, simple in-memory LRU or SQLite-backed caches.

Avoid:

* HTTP routing or raw SQL inline in services.

---

## `backend/app/storage/` — persistence layer

Purpose: SQLite models, migrations, and repos.

What to put here:

* `models.py` (SQLAlchemy), `repos/` (query classes), `migrations/` (DDL).
* Repositories that return domain models (`FillRecord`, `PairSnapshot`) rather than raw rows.

Avoid:

* Business logic; keep it CRUD + mapping.

---

## `frontend/src/` — UI (React + Vite + Bootstrap 5)

Purpose: Operator dashboard for visibility and control.

What to put here:

* `components/` (cards, modals, tables):

  * **AutotradeCard** (mode select, **Paper Trade** toggle).
  * **ThoughtLogPanel** (subscribes to `/ws/paper`).
  * **PaperMetricsCards** (subscribes to `/ws/metrics`).
  * **OpportunitiesTable**, **ApprovalsPane**, **IncidentTimeline**.
* `services/` (API client, WS client with reconnect/heartbeat).
* `hooks/` (`useApi`, `useWebSocket`, `useMetricsStream`).
* `pages/` (Dashboard, Settings).
* `styles/` (Bootstrap overrides).

Conventions:

* No heavy logic in components; push compute into hooks/services.
* All writes idempotent; show risk badges and typed confirmations for high slippage.

---

## Cross-cutting conventions

* **flake8-clean** Python with full type hints and PEP-257 docstrings.
* **Decimal** for token math; never float.
* Structured JSONL logs with `trace_id`.
* REST under `/api/v1/*`, WS under `/ws/*`.
* Consistent error schema and pagination.
* Paper mode parity with live mode (same gates, different settlement).

---

