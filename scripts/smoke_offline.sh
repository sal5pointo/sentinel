#!/usr/bin/env bash
set -euo pipefail
export TRADING_ENABLED=false
cd "$(dirname "$0")/.."
uv sync --all-extras
uv run pytest -q
uv run sentinel status
uv run sentinel goal-math --equity 100000
