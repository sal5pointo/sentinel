"""Price / quote helpers.

TODO (Schwab credentials required):
- Batch quote pulls via BrokerClient.get_quotes
- Daily history for active universe via get_price_history
- Streamer for watchlist (Phase 1+)
"""

from __future__ import annotations

from sentinel.broker.base import BrokerClient, Quote


def fetch_quotes(client: BrokerClient, symbols: list[str]) -> list[Quote]:
    return client.get_quotes(symbols)
