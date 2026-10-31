"""LLM worker — triage/memo only. No broker imports / order tools.

Schema-validated JSON. Numeric plan fields are locked to core-provided values;
hostile untrusted text must not change them (prompt-injection guard).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentinel.llm.queue import LLMQueue
from sentinel.logging_setup import get_logger

log = get_logger("llm.worker")

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

# HARD RULE: this module must never import BrokerClient, OrderRequest, or schwab.

_CRITICAL_NUMBER_KEYS = ("quantity", "entry_ref_price", "stop_price", "risk_usd", "risk_pct")


def _load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def numbers_unchanged(locked: dict[str, Any], proposed: dict[str, Any]) -> bool:
    """Return True iff proposed numbers do not mutate locked core numbers."""
    for key in proposed:
        if key not in locked or proposed[key] != locked[key]:
            return False
    for critical in _CRITICAL_NUMBER_KEYS:
        if critical in locked and critical in proposed and proposed[critical] != locked[critical]:
            return False
    if set(proposed.keys()) == set(locked.keys()):
        return proposed == locked
    return True


def apply_memo_response(
    *,
    locked_numbers: dict[str, Any],
    response: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    """Validate memo JSON; reject if numbers diverge from locked plan fields."""
    required = {"plan_id", "thesis", "numbers"}
    if not required.issubset(response.keys()):
        return False, "schema_missing_fields", None
    if not isinstance(response["thesis"], str):
        return False, "thesis_not_string", None
    nums = response.get("numbers") or {}
    if not isinstance(nums, dict):
        return False, "numbers_not_object", None
    if not numbers_unchanged(locked_numbers, nums):
        return False, "numeric_mutation_rejected", None
    safe = {
        "plan_id": response["plan_id"],
        "thesis": response["thesis"],
        "numbers": dict(locked_numbers),  # always re-bind to core
        "risks": list(response.get("risks") or []),
        "sources_cited": list(response.get("sources_cited") or []),
    }
    return True, "ok", safe


def stub_memo_from_request(request: dict[str, Any]) -> dict[str, Any]:
    """Offline stub — echoes locked numbers; ignores untrusted_text for numerics."""
    numbers = dict(request.get("numbers") or {})
    _ = request.get("untrusted_text") or []
    return {
        "plan_id": request.get("plan_id", ""),
        "thesis": "Stub memo — numbers from sentinel-core only.",
        "numbers": numbers,
        "risks": ["LLM has no broker access"],
        "sources_cited": list(request.get("evidence") or [])[:5],
    }


def process_one(queue: LLMQueue) -> bool:
    """Pop one pending message; validate schema boundary (stub: no Claude)."""
    pending = queue.pending()
    if not pending:
        return False
    msg = pending[0]
    log.info("LLM stub would process schema=%s id=%s", msg.schema_name, msg.id)
    # HARD RULE: never construct OrderRequest or touch BrokerClient here.
    return True


def main() -> None:
    log.info("sentinel-llm worker stub — schema-only; no Claude; no broker")
    _ = _load_schema("memo_request.schema.json")
    _ = _load_schema("memo_response.schema.json")
    process_one(LLMQueue())


if __name__ == "__main__":
    main()
