"""Record real UniProt / HGNC / MONDO (OLS) / PubChem responses for the normaliser tests (network)."""

import asyncio
import os

from cassette import CassetteTransport
from sources_fixtures import CASSETTES, fast_client

REQUESTS: dict[str, list[tuple[str, dict[str, object] | None]]] = {
    "uniprot": [
        (
            "https://rest.uniprot.org/uniprotkb/search",
            {
                "query": "gene_exact:EGFR AND organism_id:9606 AND reviewed:true",
                "format": "json",
                "fields": "accession,gene_primary",
                "size": 3,
            },
        )
    ],
    "hgnc": [
        ("https://rest.genenames.org/fetch/symbol/EGFR", None),
        ("https://rest.genenames.org/fetch/symbol/NOTAGENE1", None),
    ],
    "mondo": [
        (
            "https://www.ebi.ac.uk/ols4/api/search",
            {"q": "lung adenocarcinoma", "ontology": "mondo", "exact": "false", "rows": 3},
        ),
        (
            "https://www.ebi.ac.uk/ols4/api/search",
            {
                "q": "lung adenocarcinoma of unknown origin",
                "ontology": "mondo",
                "exact": "false",
                "rows": 3,
            },
        ),
    ],
    "pubchem": [
        (
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/osimertinib/property/CanonicalSMILES,InChIKey/JSON",
            None,
        )
    ],
}


async def main() -> None:
    assert os.environ.get("A9_RECORD_CASSETTES") == "1"
    for name, reqs in REQUESTS.items():
        t = CassetteTransport(CASSETTES / f"entities_{name}.json", record=True)
        client = fast_client(name, t)
        for url, params in reqs:
            try:
                await client.get(
                    url, params, headers={"Accept": "application/json"}
                ) if False else await client.get(url, params)
            except Exception as exc:
                print(name, url[-40:], "->", exc)
        t.save()
        print(name, len(t.entries), "responses")


asyncio.run(main())
