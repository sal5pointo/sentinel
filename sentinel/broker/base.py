"""BrokerClient interface — swap schwab-py / schwabdev / paper behind this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


class BrokerError(Exception):
    """Base broker failure."""


class AuthRequiredError(BrokerError):
    """Refresh token missing/expired — go read-nothing / trade-nothing."""


class TradingDisabledError(BrokerError):
    """Raised when any order path is invoked while TRADING_ENABLED is false."""


@dataclass(frozen=True)
class Account:
    account_hash: str
    account_type: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Balance:
    equity: float
    cash: float
    buying_power: float | None = None
    settled_cash: float | None = None
    currency: str = "USD"
    as_of: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    average_price: float | None = None
    market_value: float | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float | None = None
    bid: float | None = None
    ask: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    as_of: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass
class OrderRequest:
    symbol: str
    side: str  # BUY | SELL
    quantity: float
    order_type: str = "MARKET"
    limit_price: float | None = None
    stop_price: float | None = None
    plan_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


class BrokerClient(ABC):
    """Read + gated write surface used by sentinel-core only."""

    @abstractmethod
    def get_accounts(self) -> list[Account]:
        raise NotImplementedError

    @abstractmethod
    def get_balances(self, account_hash: str) -> Balance:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self, account_hash: str) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def get_quotes(self, symbols: list[str]) -> list[Quote]:
        raise NotImplementedError

    @abstractmethod
    def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PriceBar]:
        raise NotImplementedError

    @abstractmethod
    def preview_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        """Must refuse when TRADING_ENABLED is false."""
        raise NotImplementedError
