"""Paper broker — simulate fills off provided quotes (no Schwab sandbox)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sentinel.broker.base import (
    Account,
    Balance,
    BrokerClient,
    BrokerError,
    OrderRequest,
    OrderResult,
    Position,
    PriceBar,
    Quote,
)
from sentinel.logging_setup import get_logger

log = get_logger("broker.paper")


class PaperBroker(BrokerClient):
    """In-memory paper account. Uses live quotes from an optional quote source."""

    def __init__(
        self,
        *,
        starting_cash: float = 100_000.0,
        slippage_bps: float = 5.0,
        quote_source: BrokerClient | None = None,
        account_hash: str = "paper-001",
    ) -> None:
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.slippage_bps = slippage_bps
        self.quote_source = quote_source
        self.account_hash = account_hash
        self._positions: dict[str, Position] = {}
        self._quotes: dict[str, Quote] = {}
        self._history: dict[str, list[PriceBar]] = {}
        self._orders: list[OrderResult] = []

    def seed_quote(self, quote: Quote) -> None:
        self._quotes[quote.symbol] = quote

    def seed_history(self, symbol: str, bars: list[PriceBar]) -> None:
        self._history[symbol] = list(bars)

    def get_accounts(self) -> list[Account]:
        return [Account(account_hash=self.account_hash, account_type="PAPER")]

    def get_balances(self, account_hash: str) -> Balance:
        mv = sum(p.market_value or 0.0 for p in self._positions.values())
        equity = self.cash + mv
        return Balance(
            equity=equity,
            cash=self.cash,
            buying_power=self.cash,
            settled_cash=self.cash,
            as_of=datetime.now(tz=UTC),
        )

    def get_positions(self, account_hash: str) -> list[Position]:
        return list(self._positions.values())

    def get_quotes(self, symbols: list[str]) -> list[Quote]:
        if self.quote_source is not None:
            return self.quote_source.get_quotes(symbols)
        out: list[Quote] = []
        for s in symbols:
            if s not in self._quotes:
                raise BrokerError(f"No paper quote seeded for {s}")
            out.append(self._quotes[s])
        return out

    def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PriceBar]:
        if self.quote_source is not None:
            try:
                return self.quote_source.get_price_history(symbol, start=start, end=end)
            except BrokerError:
                pass
        bars = list(self._history.get(symbol, []))
        if start:
            bars = [b for b in bars if b.ts.date() >= start]
        if end:
            bars = [b for b in bars if b.ts.date() <= end]
        return bars

    def _fill_price(self, order: OrderRequest, quote: Quote) -> float:
        slip = self.slippage_bps / 10_000.0
        if order.side.upper() == "BUY":
            base = quote.ask if quote.ask is not None else quote.last
            if base is None:
                raise BrokerError(f"No ask/last for {order.symbol}")
            return float(base) * (1.0 + slip)
        base = quote.bid if quote.bid is not None else quote.last
        if base is None:
            raise BrokerError(f"No bid/last for {order.symbol}")
        return float(base) * (1.0 - slip)

    def preview_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        quotes = self.get_quotes([order.symbol])
        px = self._fill_price(order, quotes[0])
        return OrderResult(
            order_id=f"preview-{uuid4().hex[:8]}",
            status="PREVIEW_OK",
            raw={"estimated_price": px, "order": order.__dict__},
        )

    def place_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        """Paper place — allowed even when TRADING_ENABLED is false (simulation)."""
        quotes = self.get_quotes([order.symbol])
        px = self._fill_price(order, quotes[0])
        notional = px * order.quantity
        side = order.side.upper()
        if side == "BUY":
            if notional > self.cash:
                raise BrokerError("Insufficient paper cash")
            self.cash -= notional
            prev = self._positions.get(order.symbol)
            qty = (prev.quantity if prev else 0.0) + order.quantity
            self._positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=qty,
                average_price=px,
                market_value=qty * px,
            )
        elif side == "SELL":
            prev = self._positions.get(order.symbol)
            if prev is None or prev.quantity < order.quantity:
                raise BrokerError("Insufficient paper position")
            self.cash += notional
            qty = prev.quantity - order.quantity
            if qty <= 0:
                self._positions.pop(order.symbol, None)
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=qty,
                    average_price=prev.average_price,
                    market_value=qty * px,
                )
        else:
            raise BrokerError(f"Unknown side: {order.side}")

        result = OrderResult(
            order_id=f"paper-{uuid4().hex[:12]}",
            status="FILLED",
            raw={"fill_price": px, "plan_id": order.plan_id},
        )
        self._orders.append(result)
        log.info("paper fill %s %s x%s @ %.4f", side, order.symbol, order.quantity, px)
        return result

    def snapshot(self) -> dict[str, Any]:
        bal = self.get_balances(self.account_hash)
        return {
            "account_hash": self.account_hash,
            "cash": bal.cash,
            "equity": bal.equity,
            "positions": [p.__dict__ for p in self.get_positions(self.account_hash)],
            "orders": [o.__dict__ for o in self._orders],
        }
