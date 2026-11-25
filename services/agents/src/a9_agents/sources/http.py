"""One HTTP client policy for every source: a rate limit, a bounded semaphore, and retry with
exponential backoff (honouring Retry-After). All of it is injectable so tests run instantly."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from a9_agents.sources.base import SourceError

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "A9-research-tool/0.1 (literature search; research use)"


@dataclass(frozen=True)
class Policy:
    source: str
    #: Minimum seconds between request starts (the source's documented limit, with margin).
    min_interval: float
    #: Requests in flight at once.
    max_concurrency: int = 2
    max_attempts: int = 4
    backoff_initial: float = 0.5
    backoff_max: float = 20.0
    timeout: float = 30.0


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return max(float(value), 0.0) if value is not None else None
    except ValueError:
        return None  # an HTTP-date; fall back to our own backoff


class PolicedClient:
    def __init__(
        self,
        policy: Policy,
        *,
        headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.policy = policy
        self._sleep = sleep
        self._clock = clock
        self._client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            timeout=policy.timeout,
            transport=transport,
            follow_redirects=True,
        )
        self._semaphore = asyncio.Semaphore(policy.max_concurrency)
        self._pace_lock = asyncio.Lock()
        self._next_start = 0.0
        self.requests_made = 0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _pace(self) -> None:
        async with self._pace_lock:
            now = self._clock()
            start = max(now, self._next_start)
            if start > now:
                await self._sleep(start - now)
            self._next_start = start + self.policy.min_interval

    def _wait(self, state: RetryCallState) -> float:
        exc = state.outcome.exception() if state.outcome else None
        base = wait_exponential_jitter(
            multiplier=self.policy.backoff_initial, max=self.policy.backoff_max
        )(state)
        if isinstance(exc, _Retryable) and exc.retry_after is not None:
            return min(max(exc.retry_after, base), self.policy.backoff_max)
        return base

    async def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        p = self.policy

        async def attempt() -> httpx.Response:
            await self._pace()
            async with self._semaphore:
                self.requests_made += 1
                try:
                    response = await self._client.get(url, params=params)
                except httpx.TransportError as exc:  # timeouts, resets, DNS, refused
                    raise _Retryable(f"{type(exc).__name__}") from exc
            if response.status_code in RETRY_STATUSES:
                raise _Retryable(f"HTTP {response.status_code}", _retry_after(response))
            if response.status_code != 200:
                raise SourceError(
                    p.source, f"HTTP {response.status_code}"
                )  # our request is wrong; do not retry
            return response

        try:
            async for step in AsyncRetrying(
                stop=stop_after_attempt(p.max_attempts),
                wait=self._wait,
                retry=retry_if_exception_type(_Retryable),
                sleep=self._sleep,
                reraise=True,
            ):
                with step:
                    return await attempt()
        except _Retryable as exc:
            raise SourceError(
                p.source,
                f"unavailable after {p.max_attempts} attempts ({exc.reason})",
                transient=True,
            ) from exc
        raise AssertionError("unreachable")  # pragma: no cover
