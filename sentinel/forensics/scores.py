"""Forensics score wrapper — red-flag gate on candidates."""

from __future__ import annotations

from typing import Any

from sentinel.forensics.statements import ForensicFlags, scan_forensics


def red_flag_gate(candidates: list[str] | None = None) -> dict[str, Any]:
    """Return pass/block map for candidate symbols.

    Slim Phase 1 gate: blocked names must not proceed to planner later;
    alerts may still surface with a forensics warning.
    """
    results = scan_forensics()
    by_sym = {r.symbol: r for r in results if r.symbol}
    if candidates is None:
        candidates = sorted(by_sym)
    out: dict[str, Any] = {"passed": [], "blocked": [], "warnings": {}}
    for sym in candidates:
        flags = by_sym.get(sym)
        if flags is None:
            out["passed"].append(sym)
            continue
        if flags.blocked:
            out["blocked"].append(sym)
        else:
            out["passed"].append(sym)
        if flags.flags:
            out["warnings"][sym] = flags.flags
    return out


def score_forensics(flags: ForensicFlags) -> float:
    """0..100 higher is cleaner."""
    penalty = 15.0 * len(flags.flags)
    if flags.blocked:
        penalty += 40.0
    return max(0.0, 100.0 - penalty)
