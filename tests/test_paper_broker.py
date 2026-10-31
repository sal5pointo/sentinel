"""Paper broker offline tests — no Schwab credentials."""

from __future__ import annotations

import pytest
from sentinel.broker.base import AuthRequiredError, OrderRequest, Quote, TradingDisabledError
from sentinel.broker.order_builder import build_market_order
from sentinel.broker.paper_broker import PaperBroker
from sentinel.broker.schwab_client import SchwabClient


def test_paper_buy_and_balances() -> None:
    pb = PaperBroker(starting_cash=100_000.0, slippage_bps=0.0)
    pb.seed_quote(Quote(symbol="AAPL", last=200.0, bid=199.5, ask=200.5))
    order = build_market_order(symbol="AAPL", side="BUY", quantity=10, plan_id="p1")
    result = pb.place_order(pb.account_hash, order)
    assert result.status == "FILLED"
    bal = pb.get_balances(pb.account_hash)
    assert bal.cash == pytest.approx(100_000.0 - 10 * 200.5)
    pos = pb.get_positions(pb.account_hash)
    assert len(pos) == 1
    assert pos[0].symbol == "AAPL"


def test_schwab_place_order_refuses_when_disabled(config_dir: object) -> None:
    client = SchwabClient(client=object())  # pretend authenticated
    with pytest.raises(TradingDisabledError):
        client.place_order(
            "hash",
            OrderRequest(symbol="AAPL", side="BUY", quantity=1),
        )


def test_schwab_unauthenticated_reads_raise() -> None:
    client = SchwabClient()
    with pytest.raises(AuthRequiredError):
        client.get_accounts()
