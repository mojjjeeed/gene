"""The shared HTTP policy (rate limit, bounded concurrency, retry with backoff) and the pagination
rules that turn a flaky source into an honest outcome. Time and the network are both fake."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
import pytest
from a9_agents.sources.base import SourceError, collect
from a9_agents.sources.biorxiv import BioRxiv
from a9_agents.sources.europepmc import EuropePmc
from a9_agents.sources.http import PolicedClient, Policy
from sources_fixtures import EGFR_PLAN, PREPRINT_PLAN


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def client(
    handler: Callable[[httpx.Request], httpx.Response], time: FakeTime, **policy: Any
) -> PolicedClient:
    defaults: dict[str, Any] = {
        "min_interval": 0.0,
        "max_concurrency": 4,
        "max_attempts": 4,
        "backoff_initial": 1.0,
        "backoff_max": 20.0,
    }
    return PolicedClient(
        Policy("test", **{**defaults, **policy}),
        transport=httpx.MockTransport(handler),
        sleep=time.sleep,
        clock=time.clock,
    )


async def test_retries_transient_statuses_with_growing_backoff_then_succeeds() -> None:
    t, calls = FakeTime(), 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls < 3 else httpx.Response(200, json={"ok": True})

    response = await client(handler, t).get("https://x.test/a")
    assert response.json() == {"ok": True} and calls == 3
    assert len(t.sleeps) == 2 and 0 < t.sleeps[0] <= t.sleeps[1] + 1.0  # backed off, did not hammer


def throttled_once(retry_after: str) -> Callable[[httpx.Request], httpx.Response]:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return (
            httpx.Response(429, headers={"Retry-After": retry_after})
            if calls == 1
            else httpx.Response(200, json={})
        )

    return handler


async def test_honours_retry_after() -> None:
    t = FakeTime()
    await client(throttled_once("7"), t, backoff_initial=0.1).get("https://x.test/a")
    assert t.sleeps[0] == 7.0


async def test_a_hostile_retry_after_is_capped() -> None:
    t = FakeTime()
    await client(throttled_once("900"), t, backoff_max=20.0).get("https://x.test/a")
    assert t.sleeps[0] == 20.0  # a source cannot park a run for 15 minutes


async def test_gives_up_after_max_attempts_with_a_transient_named_error() -> None:
    t, calls = FakeTime(), 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    with pytest.raises(SourceError) as info:
        await client(handler, t, max_attempts=3).get("https://x.test/a")
    assert calls == 3 and info.value.transient and info.value.source == "test"
    assert "HTTP 500" in info.value.reason and "3 attempts" in info.value.reason


async def test_retries_network_errors_too() -> None:
    t, calls = FakeTime(), 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={})

    await client(handler, t).get("https://x.test/a")
    assert calls == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_client_errors_are_not_retried(status: int) -> None:
    t, calls = FakeTime(), 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status)

    with pytest.raises(SourceError) as info:
        await client(handler, t).get("https://x.test/a")
    assert calls == 1 and not info.value.transient and f"HTTP {status}" in info.value.reason


async def test_rate_limit_spaces_request_starts() -> None:
    t = FakeTime()
    c = client(lambda r: httpx.Response(200, json={}), t, min_interval=3.0)
    await asyncio.gather(*(c.get(f"https://x.test/{i}") for i in range(4)))
    assert t.now == pytest.approx(9.0)  # 4 requests, 3 intervals: the first is free
    assert all(s == pytest.approx(3.0) for s in t.sleeps)


async def test_concurrency_is_bounded() -> None:
    t, in_flight, peak = FakeTime(), 0, 0

    class Slow(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return httpx.Response(200, json={})

    c = PolicedClient(
        Policy("test", min_interval=0.0, max_concurrency=2),
        transport=Slow(),
        sleep=t.sleep,
        clock=t.clock,
    )
    await asyncio.gather(*(c.get(f"https://x.test/{i}") for i in range(8)))
    assert peak == 2


async def test_default_headers_carry_no_personal_contact_details() -> None:
    seen: list[httpx.Request] = []

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        return httpx.Response(200, json={})

    await client(handler, FakeTime()).get("https://x.test/a")
    ua = seen[0].headers["user-agent"]
    assert "@" not in ua and "A9" in ua


# --- pagination and degrade-don't-fail ---------------------------------------------------------


def epmc_page(n: int, start: int, next_cursor: str | None) -> dict[str, Any]:
    return {
        "resultList": {"result": [
            {"id": str(start + i), "source": "MED", "title": f"Paper {start + i}", "pubYear": "2022", "doi": f"10.1/p{start + i}"}
            for i in range(n)
        ]},
        "nextCursorMark": next_cursor,
    }  # fmt: skip


async def test_a_source_that_dies_mid_run_keeps_what_it_returned_and_says_why() -> None:
    t, calls = FakeTime(), 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return (
            httpx.Response(200, json=epmc_page(3, 0, "c2")) if calls == 1 else httpx.Response(503)
        )

    adapter = EuropePmc(client(handler, t, max_attempts=2), page_size=3)
    outcome = await adapter.search(EGFR_PLAN, limit=10)
    assert [r.title for r in outcome.records] == ["Paper 0", "Paper 1", "Paper 2"]
    assert outcome.partial_reason and "stopped early after 3 records" in outcome.partial_reason
    assert "HTTP 503" in outcome.partial_reason


async def test_a_source_that_is_down_from_the_start_raises_a_named_error() -> None:
    adapter = EuropePmc(client(lambda r: httpx.Response(503), FakeTime(), max_attempts=2))
    with pytest.raises(SourceError) as info:
        await adapter.search(EGFR_PLAN, limit=10)
    assert info.value.source == "test" or info.value.source == "europe_pmc"
    assert info.value.transient


def serving(response: httpx.Response) -> Callable[[httpx.Request], httpx.Response]:
    return lambda _request: response


async def test_an_unexpected_json_shape_is_an_error_not_an_empty_success() -> None:
    adapter = EuropePmc(client(serving(httpx.Response(200, json={"surprise": 1})), FakeTime()))
    with pytest.raises(SourceError, match="unexpected response"):
        await adapter.search(EGFR_PLAN, limit=5)


async def test_a_non_json_body_is_an_error_not_an_empty_success() -> None:
    adapter = EuropePmc(
        client(serving(httpx.Response(200, content=b"<html>not json</html>")), FakeTime())
    )
    with pytest.raises(SourceError, match="unreadable response"):
        await adapter.search(EGFR_PLAN, limit=5)


async def test_pages_are_followed_until_the_limit_and_the_limit_is_exact() -> None:
    t, cursors = FakeTime(), []

    def handler(r: httpx.Request) -> httpx.Response:
        cursor = r.url.params["cursorMark"]
        cursors.append(cursor)
        start = {"*": 0, "c2": 4, "c3": 8}[cursor]
        return httpx.Response(
            200, json=epmc_page(4, start, {"*": "c2", "c2": "c3", "c3": "c4"}[cursor])
        )

    outcome = await EuropePmc(client(handler, t), page_size=4).search(EGFR_PLAN, limit=10)
    assert len(outcome.records) == 10 and cursors == ["*", "c2", "c3"]
    assert outcome.partial_reason is None


async def test_records_without_a_title_are_counted_not_silently_dropped() -> None:
    page = epmc_page(3, 0, None)
    page["resultList"]["result"][1]["title"] = ""
    outcome = await EuropePmc(client(lambda r: httpx.Response(200, json=page), FakeTime())).search(
        EGFR_PLAN, limit=10
    )
    assert len(outcome.records) == 2
    assert outcome.partial_reason == "skipped 1 records without a title"


async def test_collect_stops_at_the_limit_without_reading_further_pages() -> None:
    pulled = 0

    async def pages() -> Any:
        nonlocal pulled
        for _ in range(10):
            pulled += 1
            yield []

    out = await collect("s", pages(), limit=0)
    assert out.records == [] and pulled == 1


# --- bioRxiv: the cursor is an offset, pages are not a fixed size ------------------------------


async def test_biorxiv_advances_its_cursor_by_what_it_received_not_by_a_fixed_page_size() -> None:
    """Regression: the API returned 30 per page while the adapter stepped by 100, skipping 70 of every
    100 records without any error."""
    t, cursors = FakeTime(), []

    def item(i: int) -> dict[str, str]:
        return {"doi": f"10.1101/{i}", "title": f"cancer study {i}", "abstract": "about cancer", "authors": "A, B.",
                "date": "2024-06-01", "server": "bioRxiv", "version": "1", "license": "cc_by"}  # fmt: skip

    def handler(r: httpx.Request) -> httpx.Response:
        cursor = int(r.url.path.split("/")[-2])
        cursors.append(cursor)
        items = [item(i) for i in range(cursor, min(cursor + 30, 100))]
        return httpx.Response(
            200,
            json={
                "messages": [{"status": "ok", "total": "100", "count": len(items)}],
                "collection": items,
            },
        )

    adapter = BioRxiv("biorxiv", client(handler, t), max_pages=10, today=date(2024, 6, 30))
    outcome = await adapter.search(PREPRINT_PLAN, limit=1000)
    assert cursors == [0, 30, 60, 90]
    assert len(outcome.records) == 100 and len({r.source_id for r in outcome.records}) == 100
    assert not re.search(
        r"scanned \d+ of", outcome.partial_reason or ""
    )  # fully scanned: no false 'partial' claim


async def test_biorxiv_reports_when_it_stopped_scanning_early() -> None:
    def handler(r: httpx.Request) -> httpx.Response:
        body = {"messages": [{"status": "ok", "total": "5000", "count": 1}],
                "collection": [{"doi": "10.1101/1", "title": "cancer", "abstract": "", "authors": "", "date": "2024-06-01", "server": "bioRxiv", "version": "1"}]}  # fmt: skip
        return httpx.Response(200, content=json.dumps(body))

    outcome = await BioRxiv(
        "biorxiv", client(handler, FakeTime()), max_pages=2, today=date(2024, 6, 30)
    ).search(PREPRINT_PLAN, limit=100)
    assert "scanned 2 of 5000" in (outcome.partial_reason or "")
