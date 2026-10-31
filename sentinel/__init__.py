"""SENTINEL — personal Schwab trading engine (Phase 1 vertical slice)."""

__version__ = "0.2.0"

# Hard invariant: trading stays off unless the owner flips config + passkey.
# Agents and automation MUST NEVER set this to True.
DEFAULT_TRADING_ENABLED = False
