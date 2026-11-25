"""Record the real responses behind the identity and retraction tests (network required)."""

from __future__ import annotations

import asyncio
import os

from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client

PUBLISHED = "10.1093/nargab/lqae190"  # journal version of bioRxiv 10.1101/2024.03.31.587463
DOIS = [
    "10.1016/s0140-6736(97)11096-0",  # Wakefield et al. 1998, retracted in 2010
    PUBLISHED,  # an ordinary paper
    "10.1101/2024.03.31.587463",  # the preprint
    "10.5555/a9-no-such-doi",  # not in Crossref
]


async def main() -> None:
    assert os.environ.get("A9_RECORD_CASSETTES") == "1", "set A9_RECORD_CASSETTES=1"
    epmc = CassetteTransport(CASSETTES / "identity_europepmc.json", record=True)
    client = fast_client("europe_pmc", epmc)
    await client.get(
        "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
        {"query": f'DOI:"{PUBLISHED}"', "format": "json", "resultType": "core"},
    )
    epmc.save()

    cr = CassetteTransport(CASSETTES / "crossref_retractions.json", record=True)
    client = fast_client("crossref", cr)
    from a9_agents.sources.base import SourceError

    for doi in DOIS:
        try:
            await client.get(f"https://api.crossref.org/works/{doi}")
        except SourceError as exc:
            print(doi, "->", exc.reason)  # the 404 is recorded too
    cr.save()
    print("recorded", len(epmc.entries), "+", len(cr.entries), "responses")


asyncio.run(main())
