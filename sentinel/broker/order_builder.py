"""Deterministic order construction. LLM must never call this with broker access."""

from __future__ import annotations

from typing import Any

from sentinel.broker.base import OrderRequest


def build_market_order(
    *,
    symbol: str,
    side: str,
    quantity: float,
    plan_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> OrderRequest:
    return OrderRequest(
        symbol=symbol.upper(),
        side=side.upper(),
        quantity=quantity,
        order_type="MARKET",
        plan_id=plan_id,
        extra=extra or {},
    )


def build_bracket_stub(
    *,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
    plan_id: str | None = None,
) -> OrderRequest:
    """Phase 0 stub — full bracket mapping to Schwab payload is Phase 2."""
    return OrderRequest(
        symbol=symbol.upper(),
        side=side.upper(),
        quantity=quantity,
        order_type="BRACKET_STUB",
        stop_price=stop_price,
        plan_id=plan_id,
        extra={"todo": "Map to Schwab OCO/bracket in Phase 2"},
    )
