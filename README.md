# SENTINEL

Personal Schwab trading engine: **signal → plan → one-click approval → execution**.

**Phase 2 — paper plan → approve → paper execute.**  
Live trading is **disabled**. `trading_enabled: false` stays false unless the **owner** flips config **and** confirms with a passkey (Phase 4). **Agents never flip it.**

## Hard rules

- No live orders during development.
- Never automate Schwab browser login or handle the account password. OAuth consent is owner-only.
- The LLM process (`sentinel-llm`) never gets Schwab credentials or order tools.
- Ask before paid data subscriptions.

## Requirements

- Python **3.12+**
- [`uv`](https://github.com/astral-sh/uv) (recommended)
- Windows always-on PC preferred for `sentinel-core` (see preferences); Mac is fine for development.

## Setup

```bash
uv sync --all-extras
export TRADING_ENABLED=false
uv run sentinel status
uv run pytest -q
```

Secrets go in the **OS keychain** (Windows Credential Manager / macOS Keychain / Secret Service) or env vars for CI. See `.env.example`. Never commit tokens or App Secret.

## CLI

```bash
uv run sentinel status
uv run sentinel init-db
uv run sentinel auth login          # owner completes browser consent on Windows
uv run sentinel auth status
uv run sentinel goal-math --equity 100000
uv run sentinel universe rebuild    # U0 PIT snapshot (fixture mode offline)
uv run sentinel scan                # MVP scanners on fixtures; persist alerts
uv run sentinel plan-demo           # build + persist synthetic TradePlan + token link
uv run sentinel freshness
uv run sentinel dashboard           # http://127.0.0.1:8787  (paper approval + API)
```

## What works offline vs needs Windows OAuth

| Capability | Status |
|---|---|
| Config / CI / SQLite WAL / audit log | **Live offline** |
| Universe U0 + EDGAR parsers + MVP scanners | **Live offline** (fixtures) |
| Planner + sizing + funding + `TradePlan` persistence | **Live offline** |
| Risk rules / stops / breakers / price-drift / settled-cash | **Live offline** |
| Approval FastAPI (token links; GET never executes) | **Live offline** |
| WebAuthn/passkey scaffolding | **Scaffold** — tests use `SENTINEL_INSECURE_WEBAUTHN_BYPASS=1` only |
| Email / push | **Fixture stubs** (Gmail/ntfy interfaces; no network in CI) |
| Paper executor preview→bracket→reconcile | **Live offline** (PaperBroker only) |
| Kill switch HALT API + dashboard | **Live** |
| Prompt-injection guard (hostile press release) | **Tested** — numeric plan fields locked |
| REST: `/api/positions` `/api/plans` `/api/signals` `/api/mode` `/api/halt` | **Live** |
| LLM memo worker | **Schema-only stub** — no broker access |
| Schwab accounts / quotes / live orders | **Needs owner OAuth on Windows** |
| `trading_enabled` / live Schwab orders | **Blocked** — remains false |

## Run API locally

```bash
export TRADING_ENABLED=false
uv run sentinel init-db
uv run sentinel plan-demo
uv run sentinel dashboard --host 127.0.0.1 --port 8787
# Open confirm link printed by plan-demo (GET is safe).
# Confirm POST requires passkey (or insecure bypass in tests only).
```

## Config

YAML under `config/`:

- `settings.yaml` — `trading_enabled: false`, approval drift %, execution mode `paper`
- `risk.yaml` — buckets, breakers, pilot caps, cash floor
- `signals.yaml` / `universe.yaml` — Phase 1 scanners + U0

## Architecture

- **`sentinel-core`** — tokens, data, signals, risk, planner, executor, approval, dashboard
- **`sentinel-llm`** — Claude key only; local queue + JSON schemas; no broker access

## Windows always-on PC (owner tonight)

1. Register Schwab Trader API app; store App Key/Secret in Credential Manager.
2. Run `uv run sentinel auth login` and complete browser consent **yourself**.
3. Bind dashboard to `127.0.0.1:8787`; expose via Tailscale Funnel or Cloudflare Tunnel — never WAN ports.
4. Set `SENTINEL_APPROVAL_HMAC_SECRET`; leave `SENTINEL_INSECURE_WEBAUTHN_BYPASS` unset.
5. Keep `TRADING_ENABLED=false` until Phase 4 + passkey.

## Tests

```bash
uv run pytest -q
# Expect 58 passed (Phase 2)
```

## License

Proprietary — personal use.
