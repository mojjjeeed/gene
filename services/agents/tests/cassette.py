"""Record-and-replay for HTTP, so adapter contract tests run against real responses offline.

A cassette is a JSON file of {request key -> response}. Replay is strict: a request with no recording
fails loudly instead of silently reaching the network. Credentials never enter a key or a file.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl

import httpx

SECRET_PARAMS = {"api_key", "email", "mailto", "apikey"}


def request_key(request: httpx.Request) -> str:
    query = sorted(
        (k, v) for k, v in parse_qsl(request.url.query.decode()) if k.lower() not in SECRET_PARAMS
    )
    q = "&".join(f"{k}={v}" for k, v in query)
    return f"{request.method} {request.url.scheme}://{request.url.host}{request.url.path}?{q}"


class CassetteTransport(httpx.AsyncBaseTransport):
    def __init__(self, path: Path, *, record: bool = False):
        self.path, self.record = path, record
        self.entries: dict[str, dict[str, object]] = {}
        self.served: list[str] = []
        if path.exists() and not record:
            self.entries = json.loads(path.read_text())
        self._real = httpx.AsyncHTTPTransport() if record else None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = request_key(request)
        if self.record:
            assert self._real is not None
            response = await self._real.handle_async_request(request)
            body = await response.aread()
            self.entries[key] = {
                "status": response.status_code,
                "content_type": response.headers.get("content-type", "application/json"),
                "body": body.decode("utf-8", errors="replace"),
            }
            return httpx.Response(
                response.status_code,
                headers={"content-type": str(self.entries[key]["content_type"])},
                content=body,
            )
        if key not in self.entries:
            raise AssertionError(f"no recorded response in {self.path.name} for:\n  {key}")
        entry = self.entries[key]
        self.served.append(key)
        return httpx.Response(
            int(str(entry["status"])),
            headers={"content-type": str(entry["content_type"])},
            content=str(entry["body"]).encode(),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=1, sort_keys=True) + "\n")
