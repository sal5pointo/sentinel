"""SENTINEL — personal Schwab trading engine (Phase 2 paper money path)."""

__version__ = "0.3.0"

# Hard invariant: trading stays off unless the owner flips config + passkey.
# Agents and automation MUST NEVER set this to True.
DEFAULT_TRADING_ENABLED = False
