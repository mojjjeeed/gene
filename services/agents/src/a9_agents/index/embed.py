"""Dense embeddings and reranking with open ONNX models (fastembed; no torch).

STAND-INS: the plan names BGE-M3 (or Voyage) for chunks and bge-reranker-v2-m3 (or Cohere) for rerank.
fastembed does not ship BGE-M3, so this uses BAAI/bge-small-en-v1.5 (384-d) and a MiniLM cross-encoder.
Both are real models, much smaller than the planned ones; swap behind these two protocols.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Protocol

DENSE_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"


class DenseEmbedder(Protocol):
    name: str
    dims: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...


class Reranker(Protocol):
    name: str

    async def rerank(self, query: str, passages: list[str]) -> list[float]: ...


_lock = threading.Lock()
_models: dict[tuple[str, str], Any] = {}


def _load(kind: str, name: str) -> Any:
    with _lock:
        if (kind, name) not in _models:
            if kind == "dense":
                from fastembed import TextEmbedding

                _models[(kind, name)] = TextEmbedding(name)
            else:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                _models[(kind, name)] = TextCrossEncoder(name)
        return _models[(kind, name)]


class FastEmbedDense:
    dims = 384

    def __init__(self, model: str = DENSE_MODEL):
        self.name = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = await asyncio.to_thread(_load, "dense", self.name)
        return [
            [float(x) for x in v]
            for v in await asyncio.to_thread(lambda: list(model.embed(texts, batch_size=32)))
        ]

    async def embed_query(self, text: str) -> list[float]:
        model = await asyncio.to_thread(_load, "dense", self.name)
        vec = await asyncio.to_thread(lambda: next(iter(model.query_embed(text))))
        return [float(x) for x in vec]


class FastEmbedReranker:
    def __init__(self, model: str = RERANK_MODEL):
        self.name = model

    async def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        model = await asyncio.to_thread(_load, "rerank", self.name)
        return [
            float(x) for x in await asyncio.to_thread(lambda: list(model.rerank(query, passages)))
        ]
