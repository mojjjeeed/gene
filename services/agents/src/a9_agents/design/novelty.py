"""Novelty against ChEMBL: has this exact structure (by InChIKey) already been reported?"""

from __future__ import annotations

from a9_agents.sources.base import SourceError
from a9_agents.sources.http import PolicedClient, Policy


class ChemblNovelty:
    def __init__(self, client: PolicedClient | None = None):
        self._client = client or PolicedClient(
            Policy("chembl", min_interval=0.3, max_concurrency=2)
        )

    async def is_known(self, inchikey: str) -> bool | None:
        """True/False, or None if ChEMBL could not be asked: unknown is never reported as novel."""
        try:
            r = await self._client.get(
                "https://www.ebi.ac.uk/chembl/api/data/molecule.json",
                {"molecule_structures__standard_inchi_key": inchikey, "limit": 1},
            )
            return int(r.json()["page_meta"]["total_count"]) > 0
        except (SourceError, KeyError, ValueError):
            return None
