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


def build_bracket_order(
    *,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
    limit_price: float | None = None,
    plan_id: str | None = None,
) -> OrderRequest:
    """Entry + protective stop child (GTC at broker in live; paper simulates)."""
    entry_type = "LIMIT" if limit_price is not None else "MARKET"
    return OrderRequest(
        symbol=symbol.upper(),
        side=side.upper(),
        quantity=quantity,
        order_type="BRACKET",
        limit_price=limit_price,
        stop_price=stop_price,
        plan_id=plan_id,
        extra={
            "entry_type": entry_type,
            "stop_type": "STOP",
            "stop_duration": "GTC",
            "children": [
                {
                    "role": "stop",
                    "side": "SELL" if side.upper() == "BUY" else "BUY",
                    "order_type": "STOP",
                    "stop_price": stop_price,
                    "quantity": quantity,
                }
            ],
        },
    )


# Back-compat alias used by Phase 0 tests / docs
def build_bracket_stub(
    *,
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
    plan_id: str | None = None,
) -> OrderRequest:
    return build_bracket_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        stop_price=stop_price,
        plan_id=plan_id,
    )
