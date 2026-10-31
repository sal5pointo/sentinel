"""Schwab broker adapter (schwab-py).

Phase 0: scaffolding + offline-safe behavior.
Live calls require owner OAuth tokens — never automate Schwab password login.

TODO (owner credentials required):
- Wire schwab.auth.client_from_token_file / easy_client after `sentinel auth login`
- Map account hashes, positions, balances, quotes, price history
- Rate-limit (≈120 req/min) and 429 backoff
"""

from __future__ import annotations

from datetime import UTC, date
from typing import Any

from sentinel.broker.base import (
    Account,
    AuthRequiredError,
    Balance,
    BrokerClient,
    BrokerError,
    OrderRequest,
    OrderResult,
    Position,
    PriceBar,
    Quote,
    TradingDisabledError,
)
from sentinel.config import resolve_trading_enabled
from sentinel.logging_setup import get_logger

log = get_logger("broker.schwab")

# Pinned in pyproject.toml: schwab-py==1.5.1
SCHWAB_PY_PIN = "1.5.1"


class SchwabClient(BrokerClient):
    """Thin wrapper around schwab-py. Instantiable without credentials for tests."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        app_secret: str | None = None,
        token_path: str | None = None,
        callback_url: str = "https://127.0.0.1:8182",
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.app_secret = app_secret
        self.token_path = token_path
        self.callback_url = callback_url
        self._client = client  # injected schwab-py client or None

    @property
    def is_authenticated(self) -> bool:
        return self._client is not None

    def _require_client(self) -> Any:
        if self._client is None:
            raise AuthRequiredError(
                "Schwab client not authenticated. Owner must run "
                "`sentinel auth login` (browser consent only; no password in CLI)."
            )
        return self._client

    # --- Read paths ---------------------------------------------------------

    def get_accounts(self) -> list[Account]:
        # TODO: client.get_account_numbers() once authenticated
        client = self._require_client()
        try:
            resp = client.get_account_numbers()
            data = resp.json() if hasattr(resp, "json") else resp
        except Exception as exc:  # noqa: BLE001 — surface as BrokerError
            raise BrokerError(f"get_accounts failed: {exc}") from exc
        accounts: list[Account] = []
        if isinstance(data, list):
            for item in data:
                accounts.append(
                    Account(
                        account_hash=str(item.get("hashValue") or item.get("accountNumber")),
                        account_type=item.get("accountType"),
                        raw=dict(item),
                    )
                )
        return accounts

    def get_balances(self, account_hash: str) -> Balance:
        # TODO: client.get_account(account_hash, fields=...) map equity/cash
        client = self._require_client()
        try:
            resp = client.get_account(account_hash)
            data = resp.json() if hasattr(resp, "json") else resp
        except Exception as exc:  # noqa: BLE001
            raise BrokerError(f"get_balances failed: {exc}") from exc
        sec = (data or {}).get("securitiesAccount") or data or {}
        balances = sec.get("currentBalances") or sec.get("initialBalances") or {}
        equity = float(balances.get("liquidationValue") or balances.get("equity") or 0)
        cash = float(balances.get("cashBalance") or balances.get("availableFunds") or 0)
        return Balance(
            equity=equity,
            cash=cash,
            buying_power=balances.get("buyingPower"),
            settled_cash=balances.get("cashAvailableForTrading"),
            raw=dict(data) if isinstance(data, dict) else {},
        )

    def get_positions(self, account_hash: str) -> list[Position]:
        # TODO: include positions field on get_account
        client = self._require_client()
        try:
            resp = client.get_account(account_hash)
            data = resp.json() if hasattr(resp, "json") else resp
        except Exception as exc:  # noqa: BLE001
            raise BrokerError(f"get_positions failed: {exc}") from exc
        sec = (data or {}).get("securitiesAccount") or {}
        positions: list[Position] = []
        for p in sec.get("positions") or []:
            instr = p.get("instrument") or {}
            positions.append(
                Position(
                    symbol=str(instr.get("symbol") or ""),
                    quantity=float(p.get("longQuantity") or 0) - float(p.get("shortQuantity") or 0),
                    average_price=p.get("averagePrice"),
                    market_value=p.get("marketValue"),
                    raw=dict(p),
                )
            )
        return positions

    def get_quotes(self, symbols: list[str]) -> list[Quote]:
        # TODO: batch quotes (start ~200 symbols/request); map 52w hi/lo
        client = self._require_client()
        try:
            resp = client.get_quotes(symbols)
            data = resp.json() if hasattr(resp, "json") else resp
        except Exception as exc:  # noqa: BLE001
            raise BrokerError(f"get_quotes failed: {exc}") from exc
        out: list[Quote] = []
        payload = data if isinstance(data, dict) else {}
        for sym in symbols:
            q = payload.get(sym) or {}
            quote = q.get("quote") or q
            out.append(
                Quote(
                    symbol=sym,
                    last=quote.get("lastPrice"),
                    bid=quote.get("bidPrice"),
                    ask=quote.get("askPrice"),
                    high_52w=quote.get("52WkHigh") or quote.get("highPrice52"),
                    low_52w=quote.get("52WkLow") or quote.get("lowPrice52"),
                    raw=dict(q) if isinstance(q, dict) else {},
                )
            )
        return out

    def get_price_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[PriceBar]:
        # TODO: map schwab price_history candles
        client = self._require_client()
        try:
            # Signature depends on schwab-py helpers; keep call optional for stub.
            if hasattr(client, "get_price_history_every_day"):
                resp = client.get_price_history_every_day(symbol)
            else:
                resp = client.get_price_history(symbol)
            data = resp.json() if hasattr(resp, "json") else resp
        except Exception as exc:  # noqa: BLE001
            raise BrokerError(f"get_price_history failed: {exc}") from exc
        candles = (data or {}).get("candles") or []
        bars: list[PriceBar] = []
        from datetime import datetime

        for c in candles:
            ts_ms = c.get("datetime") or c.get("datetimeISO")
            if isinstance(ts_ms, (int, float)):
                ts = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
            else:
                ts = datetime.now(tz=UTC)
            bars.append(
                PriceBar(
                    symbol=symbol,
                    ts=ts,
                    open=float(c.get("open", 0)),
                    high=float(c.get("high", 0)),
                    low=float(c.get("low", 0)),
                    close=float(c.get("close", 0)),
                    volume=c.get("volume"),
                )
            )
        # Optional date filter (stub-friendly)
        if start:
            bars = [b for b in bars if b.ts.date() >= start]
        if end:
            bars = [b for b in bars if b.ts.date() <= end]
        return bars

    def preview_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        self._require_client()
        if not resolve_trading_enabled():
            # Preview itself is allowed for paper planning later; Phase 0 still
            # refuses to call live preview without explicit future wiring.
            raise TradingDisabledError(
                "Live order preview blocked: trading_enabled is false "
                "(owner-only flip with passkey; agents never enable)."
            )
        raise BrokerError("Live preview_order not wired in Phase 0")

    def place_order(self, account_hash: str, order: OrderRequest) -> OrderResult:
        if not resolve_trading_enabled():
            raise TradingDisabledError(
                "place_order refused: TRADING_ENABLED is false. "
                "Agents must never flip this flag."
            )
        self._require_client()
        raise BrokerError("Live place_order not wired in Phase 0")
