Here’s the **updated project overview** with the **API & WebSocket contract coverage note** folded in.

---

# DEX Sniper Pro (dex\_django) — Project Overview

## Vision

DEX Sniper Pro is a **single-user professional-grade decentralized trading bot** designed for speed, safety, and transparency. It combines **new-pair sniping** with **opportunistic re-entries**, guided by **risk controls and an AI advisory layer**. The app is positioned to be **faster than typical bots**, **safer than copy-trading tools**, and **more explainable than black-box AI dashboards**.

---

## Core Goals

1. **New-Pair Sniping** — detect and trade new liquidity pairs within seconds across Base, BSC, Solana, Polygon, and ETH L1 (for larger trades).
2. **Opportunistic Re-Entries** — re-enter trending tokens when liquidity, momentum, and risk checks align.
3. **Risk Gates** — liquidity thresholds, owner/LP checks, blacklist detection, circuit breakers, slippage caps, and approval hygiene.
4. **Transparency** — audit-ready ledgers (730-day retention), JSONL logs, real-time dashboards, and explainable AI reasoning.
5. **Modes** — Manual (non-custodial), Autotrade (encrypted hot wallet), and **Paper Trading**.

---

## Competitive Advantages

* **Router-first execution** (Uniswap v2/v3, Pancake, QuickSwap, Jupiter) with 0x/1inch fallback for fragmented liquidity.
* **Built-in risk scoring** with liquidity, tax, blacklist, and anomaly checks before committing funds.
* **AI Thought Log** panel that explains why trades were taken or skipped.
* **Low overhead** — single-user app with SQLite (WAL mode) for durability, migration path to Postgres.
* **Approval hygiene** — minimal approvals and auto-revoker built in.

---

## Role of AI

AI is not a black box — it acts as a **transparent advisor**:

* **Discovery intelligence** (ranking opportunities via liquidity/volume/momentum + optional mempool/social feeds).
* **Risk classification** (flag suspicious wallet behaviors, owner activity, LP unlocks, and contract anomalies).
* **Adaptive strategy** (learn from past trades to tune slippage curves, canary sizing, entry/exit thresholds).
* **Explainability** (real-time Thought Log showing signals, risk checks, rationale, and post-trade evaluations).

---

## Paper Trading Mode

Paper Trading allows running the **full discovery → risk → routing pipeline** without risking real funds.

* **Parity with live execution** — identical risk gates and routing logic.
* **Simulated fills** — ledger writes with `is_paper=true`.
* **Virtual balances** — per-chain balances tracked in GBP and native assets.
* **AI Thought Log** — step-by-step reasoning for every decision.
* **Metrics** — rolling/session PnL, win rate, slippage, gas-to-PnL ratio, max drawdown.
* **Frontend UX** — a **Paper Trade button** beside the **Auto Trade button**, with a **Paper badge**, a **Thought Log panel**, and **Paper Metrics cards**.

---

## API Surface (REST)

* **System:** `/api/v1/health`, `/api/v1/system/initialize`, `/api/v1/system/shutdown`.
* **Autotrade:** `/api/v1/autotrade/status`, `/autotrade/mode`, `/autotrade/toggle`.
* **Paper Trading:** `/api/v1/paper/ping`, `/paper/toggle`, `/metrics/paper`, `/trades/paper`.
* **Discovery:** `/pairs/new`, `/pairs/{address}`.
* **Quotes & Trades:** `/quotes/route`, `/trades/simulate`.
* **Wallet & Approvals:** `/wallet/balances`, `/wallet/approvals`, `/wallet/approvals/revoke`.

---

## WebSocket Hubs

* **Discovery:** `/ws/discovery` — new pairs, trending signals, risk updates.
* **Autotrade:** `/ws/autotrade` — live trades, fills, circuit breakers.
* **Paper Trading:** `/ws/paper` — paper trade events + AI Thought Log frames.
* **Metrics:** `/ws/metrics` — session/rolling KPIs for dashboard cards.
* **Monitoring:** `/ws/monitoring` — RPC pool health, gas medians, anomalies.

---

## API & WebSocket Coverage Notes

The API/WS surface has been scoped, but **not all endpoints are implemented yet**. Current state:

* ✅ `/health`, `/api/v1/paper/ping`, `/ws/paper` (hello/echo) working.
* 🟡 `/paper/toggle`, `/metrics/paper`, `/trades/paper` partially planned.
* 🟡 Discovery, Quotes, Autotrade, Wallet endpoints in design phase.
* **WS channels** (autotrade, discovery, metrics, monitoring) planned but not wired.

**Gaps to close before “thoroughly covered”:**

* Formal **error schema** and consistent 4xx/5xx codes.
* **Pagination & filtering** contracts for list endpoints.
* **Idempotency keys** for writes (toggles, trades).
* **Auth** (simple token/Bearer) even for single-user deployment.
* **WS contracts**: message types (`thought_log`, `paper_order`, `paper_fill`, `metrics`, `status`), ping/heartbeat cadence, and optional replay/subscription params.
* **Operational endpoints**: split `/health/live` vs `/health/ready`, include RPC/DB checks.

Next deliverable will be an **API & WS Contract v0.1 doc**:

* Endpoint matrix with method/path/params/req/resp/errors.
* WS message schemas with examples.
* Error taxonomy + auth/versioning conventions.

---

## Architecture

* **Backend:** FastAPI (async), httpx/websockets, APScheduler, SQLite (WAL). Organized into `api/`, `core/`, `dex/`, `discovery/`, `strategy/`, `trading/`, `ledger/`, `ws/`, `services/`, and `storage/`.
* **Frontend:** React + Vite + Bootstrap 5, WalletConnect (EVM) and Phantom/Solflare (Solana).
* **Logging:** daily JSONL logs with 90-day retention.
* **Security:** encrypted hot wallet keystore, runtime passphrase, approval hygiene, kill switch.

---

## Development Progress

* ✅ Project scope, risk gates, AI role defined.
* ✅ Backend package skeleton created (`backend/app/api/`, `backend/app/ws/`).
* ✅ Minimal `/paper/ping` API and `/ws/paper` WS live for testing.
* ✅ Fixed import issues with sys.path shim in `dex_django/main.py`.
* 🔄 Next: `/paper/toggle` + broadcast → `/ws/paper`, then frontend Paper Trade button + AI Thought Log panel.

---

## Roadmap

1. **Core v1:** multi-chain discovery, router-first quotes, Manual trading, structured logging.
2. **v1.1:** Paper Trading toggle, metrics, and Thought Log streaming (in progress).
3. **v1.2:** Autotrade live mode with circuit breakers + approval hygiene.
4. **v1.3:** AI enhancements (adaptive thresholds, anomaly detection, clustering).
5. **v1.4:** Simulation/backtesting suite with deterministic runs and strategy testing.

---

Would you like me to now **draft that API & WebSocket Contract v0.1 matrix** (methods, schemas, examples) so you’ve got a reference spec to build against?
