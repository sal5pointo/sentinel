"""LLM worker stub — triage/memo only. No broker imports with credentials.

Run as a separate process in later phases:
  python -m sentinel.llm.worker
"""

from __future__ import annotations

from sentinel.llm.queue import LLMQueue
from sentinel.logging_setup import get_logger

log = get_logger("llm.worker")


def process_one(queue: LLMQueue) -> bool:
    """Pop one pending message and reject if schema invalid (stub: log only)."""
    pending = queue.pending()
    if not pending:
        return False
    msg = pending[0]
    log.info("LLM stub would process schema=%s id=%s", msg.schema_name, msg.id)
    # TODO: validate against schemas/, call Claude, write response_json
    # HARD RULE: never construct OrderRequest or touch BrokerClient here.
    return True


def main() -> None:
    log.info("sentinel-llm worker stub — no Claude calls in Phase 0")
    process_one(LLMQueue())


if __name__ == "__main__":
    main()
