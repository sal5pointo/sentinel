"""MVP signal scanners — high_low, insider, catalysts, regime."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sentinel.forensics.scores import red_flag_gate
from sentinel.scoring.composite import compose_scores
from sentinel.signals.catalysts import scan_catalysts
from sentinel.signals.high_low import scan_high_low
from sentinel.signals.insider import scan_insider_clusters
from sentinel.signals.regime import evaluate_regime
from sentinel.storage.db import Database


def run_all_scanners(*, as_of_insider: str = "2025-10-15") -> dict[str, Any]:
    """Deterministic offline scan bundle used by CLI and tests."""
    from datetime import date

    hl = [a.to_dict() for a in scan_high_low()]
    insider = [
        a.to_dict()
        for a in scan_insider_clusters(as_of=date.fromisoformat(as_of_insider))
    ]
    cats = [a.to_dict() for a in scan_catalysts()]
    regime = evaluate_regime().to_dict()
    forensics = red_flag_gate()
    composite = [
        s.to_dict()
        for s in compose_scores(
            high_low=hl,
            insider=insider,
            catalysts=cats,
            forensics=forensics,
            regime_multiplier=float(regime.get("multiplier") or 1.0),
        )
    ]
    return {
        "high_low": hl,
        "insider": insider,
        "catalysts": cats,
        "regime": regime,
        "forensics": forensics,
        "composite": composite,
        "generated_at": datetime.now(tz=UTC).isoformat(),
    }


def persist_alerts(db: Database, bundle: dict[str, Any]) -> int:
    now = datetime.now(tz=UTC).isoformat()
    n = 0
    for family in ("high_low", "insider", "catalysts"):
        for a in bundle.get(family) or []:
            db.execute(
                "INSERT INTO signal_alerts(symbol, family, direction, score, detail_json, as_of, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    a.get("symbol"),
                    family,
                    a.get("direction"),
                    a.get("score"),
                    json.dumps(a),
                    a.get("as_of") or now,
                    now,
                ),
            )
            n += 1
    return n
