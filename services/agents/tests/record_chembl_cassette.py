"""Record real ChEMBL novelty lookups (network)."""

import asyncio
import os

from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client

KEYS = [
    "DUYJMQONPNNFPI-UHFFFAOYSA-N",
    "NYDVZIHTURABKH-UHFFFAOYSA-N",
]  # osimertinib; an unlikely molecule


async def main() -> None:
    assert os.environ.get("A9_RECORD_CASSETTES") == "1"
    t = CassetteTransport(CASSETTES / "chembl.json", record=True)
    client = fast_client("chembl", t)
    for k in KEYS:
        await client.get(
            "https://www.ebi.ac.uk/chembl/api/data/molecule.json",
            {"molecule_structures__standard_inchi_key": k, "limit": 1},
        )
    t.save()
    print(len(t.entries), "responses")


asyncio.run(main())
