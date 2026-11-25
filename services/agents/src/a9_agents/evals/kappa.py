"""Cohen's kappa: agreement between two raters beyond what chance alone would give."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence


def cohens_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """kappa = (p_observed - p_expected) / (1 - p_expected). 1 is perfect, 0 is chance, below 0 is worse.

    Raises on empty or unequal inputs rather than returning a misleading number. If both raters use a
    single identical label there is no variation to measure and kappa is undefined; we return 1.0 only
    when they agree on everything and say so, because 0/0 should not read as a failure.
    """
    if len(a) != len(b):
        raise ValueError(f"raters labelled different numbers of items ({len(a)} vs {len(b)})")
    if not a:
        raise ValueError("no items to compare")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in ca.keys() | cb.keys()) / (n * n)
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1 - expected)
