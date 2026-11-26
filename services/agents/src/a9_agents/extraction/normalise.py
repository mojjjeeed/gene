"""Ground extracted entities to stable identifiers: compounds to InChIKey, genes to UniProt and HGNC,
diseases to MONDO. An entity that will not normalise is kept as the raw string and FLAGGED, never guessed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from rdkit import Chem as _Chem
from rdkit import RDLogger as _RDLogger
from rdkit.Chem import inchi as _inchi

from a9_agents.sources.base import SourceError
from a9_agents.sources.http import PolicedClient, Policy

Chem: Any = _Chem  # RDKit ships no type information
inchi: Any = _inchi
RDLogger: Any = _RDLogger
RDLogger.DisableLog("rdApp.*")


@dataclass(frozen=True)
class Normalised:
    raw: str
    system: str  # inchikey | uniprot | hgnc | mondo
    identifier: str | None
    label: str | None = None
    #: None when normalised; otherwise why it was not (the entity is then stored raw and flagged).
    flag: str | None = None

    @property
    def ok(self) -> bool:
        return self.identifier is not None


def _unresolved(raw: str, system: str, why: str) -> Normalised:
    return Normalised(raw, system, None, None, why)


def smiles_to_inchikey(smiles: str) -> Normalised:
    """Offline and exact. Anything that is not a valid, non-trivial SMILES is not normalised."""
    s = smiles.strip()
    mol = Chem.MolFromSmiles(s) if s and " " not in s else None
    if mol is None or mol.GetNumAtoms() < 2:
        return _unresolved(smiles, "inchikey", "not a valid SMILES")
    return Normalised(smiles, "inchikey", inchi.MolToInchiKey(mol), Chem.MolToSmiles(mol))


class Normaliser:
    def __init__(
        self,
        uniprot: PolicedClient | None = None,
        hgnc: PolicedClient | None = None,
        ols: PolicedClient | None = None,
        pubchem: PolicedClient | None = None,
    ):
        self._uniprot = uniprot or PolicedClient(Policy("uniprot", min_interval=0.1))
        self._hgnc = hgnc or PolicedClient(Policy("hgnc", min_interval=0.2))
        self._ols = ols or PolicedClient(Policy("ols", min_interval=0.2))
        self._pubchem = pubchem or PolicedClient(Policy("pubchem", min_interval=0.25))

    async def compound(self, raw: str) -> Normalised:
        """A SMILES parses locally; a name goes to PubChem. No guess is made when neither resolves."""
        local = smiles_to_inchikey(raw)
        if local.ok and re.search(r"[=#()\[\]@/\\]|\d", raw):
            return local  # contains structure syntax, so it was a SMILES, not a short word
        try:
            r = await self._pubchem.get(
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(raw)}/property/CanonicalSMILES,InChIKey/JSON"
            )
            props = r.json()["PropertyTable"]["Properties"]
            return Normalised(raw, "inchikey", props[0]["InChIKey"], str(props[0].get("CID")))
        except SourceError as exc:
            return _unresolved(raw, "inchikey", f"PubChem: {exc.reason}")
        except (KeyError, IndexError, ValueError):
            return _unresolved(raw, "inchikey", "PubChem returned nothing usable")

    async def gene_uniprot(self, symbol: str) -> Normalised:
        try:
            r = await self._uniprot.get(
                "https://rest.uniprot.org/uniprotkb/search",
                {
                    "query": f"gene_exact:{symbol} AND organism_id:9606 AND reviewed:true",
                    "format": "json",
                    "fields": "accession,gene_primary",
                    "size": 3,
                },
            )
            results = r.json()["results"]
        except (SourceError, KeyError, ValueError) as exc:
            return _unresolved(symbol, "uniprot", f"UniProt: {exc}")
        if len(results) != 1:
            return _unresolved(
                symbol,
                "uniprot",
                "no unique reviewed human entry"
                if not results
                else "ambiguous: several reviewed entries",
            )
        return Normalised(symbol, "uniprot", results[0]["primaryAccession"], symbol)

    async def gene_hgnc(self, symbol: str) -> Normalised:
        try:
            root = ElementTree.fromstring(
                (
                    await self._hgnc.get(f"https://rest.genenames.org/fetch/symbol/{quote(symbol)}")
                ).content
            )
        except (SourceError, ValueError) as exc:
            return _unresolved(symbol, "hgnc", f"HGNC: {exc}")
        doc: Element | None = root.find(".//doc")
        if doc is None:
            return _unresolved(symbol, "hgnc", "no approved HGNC symbol")
        fields = {e.get("name"): (e.text or "") for e in doc}
        return Normalised(symbol, "hgnc", fields.get("hgnc_id") or None, fields.get("symbol"))

    async def disease(self, term: str) -> Normalised:
        """MONDO, accepted only on an exact label or synonym match: a fuzzy neighbour is not the disease."""
        try:
            r = await self._ols.get(
                "https://www.ebi.ac.uk/ols4/api/search",
                {"q": term, "ontology": "mondo", "exact": "false", "rows": 3},
            )
            docs = r.json()["response"]["docs"]
        except (SourceError, KeyError, ValueError) as exc:
            return _unresolved(term, "mondo", f"OLS: {exc}")
        want = term.strip().lower()
        for d in docs:
            names = {
                str(d.get("label", "")).lower(),
                *(str(x).lower() for x in d.get("synonym", []) or []),
            }
            if want in names:
                return Normalised(term, "mondo", str(d["obo_id"]), d.get("label"))
        return _unresolved(term, "mondo", "no exact MONDO label or synonym match")
