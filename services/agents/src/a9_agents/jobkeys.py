"""Deterministic job keys: the same inputs always give the same key, so a retry is a no-op."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def job_key(kind: str, **inputs: Any) -> str:
    """`kind:` plus a hash of the canonical JSON of the inputs (key order never matters)."""
    canonical = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return f"{kind}:{digest}"
