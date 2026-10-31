"""Composite confluence scoring stubs.

Alerts may fire from a single family. Planner-bound plans (Phase 2) should
require confluence_min_families (≥2) — this module wires the stub.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sentinel.config import load_signals


@dataclass
class SymbolScore:
    symbol: str
    family_scores: dict[str, float] = field(default_factory=dict)
    weighted_score: float = 0.0
    families_hit: list[str] = field(default_factory=list)
    confluence_ok: bool = False
    regime_multiplier: float = 1.0
    forensics_blocked: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compose_scores(
    *,
    high_low: list[dict[str, Any]] | None = None,
    insider: list[dict[str, Any]] | None = None,
    catalysts: list[dict[str, Any]] | None = None,
    forensics: dict[str, Any] | None = None,
    regime_multiplier: float = 1.0,
    cfg: dict[str, Any] | None = None,
) -> list[SymbolScore]:
    cfg = cfg or load_signals()
    weights = cfg.get("weights") or {}
    min_families = int(cfg.get("confluence_min_families", 2))
    blocked = set((forensics or {}).get("blocked") or [])

    by_sym: dict[str, SymbolScore] = {}

    def bump(symbol: str, family: str, score: float) -> None:
        row = by_sym.setdefault(symbol, SymbolScore(symbol=symbol))
        row.family_scores[family] = max(row.family_scores.get(family, 0.0), float(score))
        if family not in row.families_hit:
            row.families_hit.append(family)

    for a in high_low or []:
        bump(str(a["symbol"]), "high_low", float(a.get("score") or 0))
    for a in insider or []:
        bump(str(a["symbol"]), "insider", float(a.get("score") or 0))
    for a in catalysts or []:
        bump(str(a["symbol"]), "catalysts", float(a.get("score") or 0))

    out: list[SymbolScore] = []
    for sym, row in sorted(by_sym.items()):
        wsum = 0.0
        wtot = 0.0
        for fam, sc in row.family_scores.items():
            w = float(weights.get(fam, 0.1))
            wsum += w * sc
            wtot += w
        base = (wsum / wtot) if wtot else 0.0
        row.regime_multiplier = regime_multiplier
        row.weighted_score = round(base * regime_multiplier, 2)
        row.confluence_ok = len(row.families_hit) >= min_families
        row.forensics_blocked = sym in blocked
        if not row.confluence_ok:
            row.notes.append("below_confluence_for_plans")
        if row.forensics_blocked:
            row.notes.append("forensics_blocked")
        out.append(row)
    out.sort(key=lambda r: r.weighted_score, reverse=True)
    return out
