"""Object storage for original files and parsed documents. Content-addressed by SHA-256 on write, so a
re-ingest of the same bytes does not duplicate them. Local filesystem here; an S3/R2 implementation
only needs the same three methods (it has not been written)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalObjectStore:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root or os.environ.get("A9_OBJECT_ROOT", ".objects")).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:  # a key can never escape the store
            raise ValueError(f"unsafe object key {key!r}")
        return path

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return digest

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()
