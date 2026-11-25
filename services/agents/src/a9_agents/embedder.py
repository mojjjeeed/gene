"""Text embeddings for the last dedup rung (preprint vs journal version).

SPECTER2 is the intended model for this. It needs torch and a ~440 MB download, so it is an optional
extra and `Specter2Embedder` has NOT been run in development. `HashingEmbedder` is a deterministic,
dependency-free stand-in (character n-gram hashing): good enough to catch a lightly retitled
preprint, and labelled as what it is. The similarity rung is guarded so neither can merge two
unrelated papers on similarity alone.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Protocol


class Embedder(Protocol):
    name: str
    #: Cosine similarity at which a preprint/journal pair may merge. Model-specific.
    default_threshold: float

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class HashingEmbedder:
    name = "hashing-ngram"
    #: A starting point, not a tuned value: no labelled preprint/journal pairs exist yet to tune it on.
    default_threshold = 0.80

    def __init__(self, dims: int = 512, n: int = 4):
        self._dims, self._n = dims, n

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            normalised = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            vec = [0.0] * self._dims
            for i in range(max(len(normalised) - self._n + 1, 1)):
                gram = normalised[i : i + self._n]
                vec[int(hashlib.md5(gram.encode()).hexdigest(), 16) % self._dims] += 1.0
            out.append(vec)
        return out


class Specter2Embedder:
    """allenai/specter2 via `transformers` + `adapters`. Untested here: install the `specter2` extra."""

    name = "specter2"
    default_threshold = 0.92

    def __init__(self) -> None:
        import importlib.util

        if (
            importlib.util.find_spec("torch") is None
            or importlib.util.find_spec("transformers") is None
        ):
            raise RuntimeError("SPECTER2 needs `torch` and `transformers` (the specter2 extra)")
        raise NotImplementedError("SPECTER2 loading is not wired up yet; use A9_EMBEDDER=hashing")

    async def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover
        raise NotImplementedError


def make_embedder() -> Embedder:
    kind = os.environ.get("A9_EMBEDDER", "hashing")
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "specter2":
        return Specter2Embedder()
    raise ValueError(f"unknown A9_EMBEDDER {kind!r} (expected 'hashing' or 'specter2')")
