"""Licence evaluation: may we STORE full text, and derive chunks and claims from it?

Default is conservative. Only licences that permit copying AND derivatives are allowed (CC0, CC BY,
CC BY-SA, public domain). NonCommercial and NoDerivatives variants are refused (chunking and extraction
are derivative works, and this is not guaranteed to stay non-commercial). Anything unrecognised or
missing is refused: unknown is never read as open. Override with A9_ALLOWED_LICENCES (comma list of
normalised names) if the project decides otherwise.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

DEFAULT_ALLOWED = ("cc0", "cc-by", "cc-by-sa", "public-domain")

_URL = re.compile(r"creativecommons\.org/(?:licenses|publicdomain)/([a-z\-]+)/", re.IGNORECASE)


@dataclass(frozen=True)
class LicenceDecision:
    permitted: bool
    #: Normalised name (cc0, cc-by, cc-by-nc-nd, ...) or None if unrecognised.
    normalised: str | None
    raw: str | None
    reason: str


def normalise(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    text = raw.strip().lower()
    if m := _URL.search(text):
        kind = m.group(1)
        return "cc0" if kind in ("zero", "mark") else f"cc-{kind}"
    if "publicdomain" in text or text in {"pd", "public domain", "public-domain"}:
        return "public-domain"
    if re.fullmatch(r"cc0(?:[ \-_]?1\.0)?", text):
        return "cc0"
    m = re.fullmatch(
        r"cc[ \-_]?((?:by)(?:[ \-_]?(?:nc|nd|sa))*)(?:[ \-_]?\d\.\d)?(?:[ \-_]?[a-z]{2,3})?", text
    )
    if m:
        return "cc-" + re.sub(r"[ _]", "-", m.group(1))
    return None


def allowed_licences() -> set[str]:
    raw = os.environ.get("A9_ALLOWED_LICENCES")
    return (
        {x.strip() for x in raw.split(",") if x.strip()}
        if raw is not None
        else set(DEFAULT_ALLOWED)
    )


def evaluate_licence(raw: str | None) -> LicenceDecision:
    if raw is None or not raw.strip():
        return LicenceDecision(False, None, raw, "no licence recorded: metadata only")
    norm = normalise(raw)
    if norm is None:
        return LicenceDecision(False, None, raw, f"unrecognised licence {raw!r}: metadata only")
    if norm in allowed_licences():
        return LicenceDecision(True, norm, raw, f"{norm} permits storing full text")
    return LicenceDecision(
        False, norm, raw, f"{norm} does not permit storing derived full text: metadata only"
    )
