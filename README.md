# SENTINEL

Personal Schwab trading engine: **signal → plan → one-click approval → execution**.

**Phase 1 — universe U0, EDGAR parsers, MVP scanners, freshness, dashboard shell.**  
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
uv run sentinel universe rebuild --month 2025-10 --json
uv run sentinel scan                # MVP scanners on fixtures; persist alerts
uv run sentinel freshness
uv run sentinel dashboard           # http://127.0.0.1:8787  (read-only)
```

### U0 universe rebuild

```bash
# Offline / CI (default): Nasdaq Trader–shaped fixtures + metrics under data/fixtures/universe
uv run sentinel universe rebuild --month YYYY-MM --source fixture

# After network vendors are allowed on the Windows host, point symbol files at
# downloaded nasdaqlisted.txt / otherlisted.txt and refresh metrics from quotes/ADV.
# Live ADV still needs Schwab Market Data OAuth on the always-on PC.
```

Point-in-time membership is stored in SQLite (`universe_snapshots` + `universe_members`). Rebuilds for the same `stage` + `as_of_month` replace membership in place.

## What is live vs needs Schwab OAuth (Windows)

| Capability | Status |
|---|---|
| Config / CI / SQLite WAL / audit log | **Live offline** |
| Universe U0 builder + monthly PIT snapshots | **Live offline** (fixtures); live Nasdaq Trader download optional |
| EDGAR Form 4 / 8-K / companyfacts parsers | **Live offline** on ≥5 vendored fixtures each |
| Scanners: 52w hi/lo, Form 4 cluster, catalysts, regime | **Live offline** — deterministic on fixtures |
| Quant forensics red-flag gate (slim) | **Live offline** on companyfacts fixtures |
| Composite confluence scoring stubs | **Live** (alerts do not require ≥2 families; plans will) |
| Freshness monitor (Schwab + EDGAR) | **Live** — EDGAR marks ok after fixture ingest; Schwab stays `unknown` until OAuth |
| Dashboard v1 (Paper chip, positions/alerts/freshness, HALT stub) | **Live** read-only shell |
| Paper broker fills on seeded quotes | **Live** (in-memory; Phase 0) |
| Goal-math report | **Live** |
| Schwab accounts / positions / balances / quotes / history | **Needs owner OAuth on Windows always-on PC** |
| Live ADV / history for full U0 (~500) from Schwab | **Needs Market Data on Windows** |
| Live EDGAR HTTP pull (vs fixtures) | Optional later; fixtures satisfy Phase 1 accept |
| Approval / passkey / paper execute path | **Phase 2** |
| `trading_enabled` / live orders | **Blocked** — remains false |

## Config

YAML under `config/`:

- `settings.yaml` — `trading_enabled: false`, timezones, LLM queue path, OAuth refs
- `risk.yaml` — buckets, breakers, pilot caps
- `signals.yaml` — MVP families + deferred kill switches
- `universe.yaml` — U0 filters (price, ADV, listing age, excludes)

## Architecture (trimmed)

- **`sentinel-core`** — tokens, data ingest, signals, risk, planner, executor, approval
- **`sentinel-llm`** — Claude key only; local queue + JSON schemas; no broker access

Broker wrappers: `BrokerClient` + `schwab-py==1.5.1` stub + `paper_broker`.

## Windows always-on PC

1. Money path host runs `sentinel-core` + `sentinel-llm` (localhost queue).
2. Owner runs `uv run sentinel auth login` and completes Schwab consent in a browser there.
3. Dashboard binds to `127.0.0.1:8787`; expose via Tailscale Funnel later — never WAN ports.
4. Keep `TRADING_ENABLED=false` until Phase 4 + passkey.

## Tests

Offline tests **must pass without Schwab credentials**:

```bash
uv run pytest -q
```

Fixtures: `tests/fixtures/universe`, `tests/fixtures/edgar`, `tests/fixtures/prices` (mirrored under `data/fixtures` for CLI defaults).

## License

Proprietary — personal use.
