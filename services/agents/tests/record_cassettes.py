"""Record real responses for the adapter contract tests. Network required; run on purpose, not in CI.

A9_RECORD_CASSETTES=1 .venv-a9/bin/python services/agents/tests/record_cassettes.py [source ...]
"""

from __future__ import annotations

import asyncio
import os
import sys

from cassette import CassetteTransport
from sources_fixtures import CASSETTES, LIMIT, adapters


async def main(only: list[str]) -> None:
    if os.environ.get("A9_RECORD_CASSETTES") != "1":
        raise SystemExit("set A9_RECORD_CASSETTES=1 to confirm you want to hit the live APIs")
    transports: dict[str, CassetteTransport] = {}

    def transport_for(name: str) -> CassetteTransport:
        transports[name] = CassetteTransport(CASSETTES / f"{name}.json", record=True)
        return transports[name]

    for name, (adapter, plan) in adapters(transport_for).items():
        if only and name not in only:
            continue
        # Real pacing while recording: be a polite client.
        outcome = await adapter.search(plan, limit=LIMIT)
        transports[name].save()
        print(
            f"{name:11} {len(outcome.records)} records, {len(transports[name].entries)} responses  partial={outcome.partial_reason}"
        )


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
