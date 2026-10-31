# SENTINEL

Personal Schwab trading engine: **signal → plan → one-click approval → execution**.

**Phase 0 — foundations only.** Live trading is **disabled**. `trading_enabled: false` stays false unless the **owner** flips config **and** confirms with a passkey (Phase 4). **Agents never flip it.**

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

```powershell
# Windows (PowerShell) — from repo root
winget install astral-sh.uv   # or: pip install uv
uv sync --all-extras
uv run sentinel status
uv run pytest
```

```bash
# Linux / macOS
uv sync --all-extras
uv run sentinel status
uv run pytest
```

Secrets go in the **OS keychain** (Windows Credential Manager / macOS Keychain / Secret Service) or env vars for CI. See `.env.example`. Never commit tokens or App Secret.

Keychain names (default service `sentinel`):

| Name | Purpose |
|------|---------|
| `schwab_api_key` | Developer Portal App Key |
| `schwab_app_secret` | Developer Portal App Secret |
| `schwab_token_blob` | Encrypted OAuth token (after login) |
| `schwab_account_hash` | Account hash (not account number) |
| `owner_email` | Alert destination |

## CLI

```bash
uv run sentinel status
uv run sentinel init-db
uv run sentinel auth login          # opens consent URL pattern; owner completes browser login
uv run sentinel auth status
uv run sentinel goal-math --equity 100000
uv run sentinel dashboard           # http://127.0.0.1:8787  (read-only)
```

`sentinel auth login` **never** asks for or stores a Schwab password. It only prepares the OAuth consent URL / callback pattern.

## Config

YAML under `config/`:

- `settings.yaml` — `trading_enabled: false`, timezones, LLM queue path, OAuth refs
- `risk.yaml` — buckets, breakers, pilot caps
- `signals.yaml` — MVP families + deferred kill switches
- `universe.yaml` — U0 stage

## Architecture (trimmed)

- **`sentinel-core`** — tokens, risk, planner, executor, approval (this package’s main process)
- **`sentinel-llm`** — Claude key only; local queue + JSON schemas (`sentinel/llm/`); no broker access

Broker wrappers: `BrokerClient` + `schwab-py==1.5.1` stub + `paper_broker` (no Schwab sandbox).

## Windows always-on PC (run notes)

Aligned with project ops topology (`ops-architecture.md` in the agent store):

1. **Money path host:** dedicated always-on Windows PC runs `sentinel-core` + `sentinel-llm` (localhost queue only). MacBook = clone/dev; iPhone = approve/monitor via tunnel.
2. Install Python 3.12 + `uv`; clone to a stable path (e.g. `C:\sentinel`).
3. `uv sync --all-extras`; store App Key/Secret in **Windows Credential Manager** via `keyring` (service `sentinel`). Never put Schwab passwords in env files.
4. Owner runs `uv run sentinel auth login` on the Windows box; complete Schwab consent in a browser there. Tokens stay on that machine.
5. Dashboard/approval bind to `127.0.0.1` (default `:8787`). Expose later via **Tailscale Funnel** (recommended) or Cloudflare Tunnel — never open WAN router ports.
6. Keep `TRADING_ENABLED=false` / `trading_enabled: false` until Phase 4 + passkey on the Windows-hosted approval server. **Agents never flip it.**
7. Later: Task Scheduler / NSSM for core services; healthchecks.io heartbeat; GTC stops remain at Schwab if the PC dies.

## Tests

Offline tests **must pass without Schwab credentials**:

```bash
uv run pytest
```

Mark/skip live tests with `@pytest.mark.live` (none required for Phase 0 CI).

## Attaching / pushing to GitHub

If this clone already has `origin` → `https://github.com/sal5pointo/sentinel.git`, just push. Otherwise:

```bash
cd /path/to/sentinel
git remote add origin https://github.com/sal5pointo/sentinel.git
git push -u origin main
```

## License

Proprietary — personal use.
