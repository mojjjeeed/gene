"""
PubChem Chemical Properties Data Loader.
Resolves compound names to Canonical SMILES, 2D/3D structure, molecular weight, LogP, and IUPAC names via PUG REST API.
"""

from typing import List, Dict, Any, Optional
import urllib.parse
import requests

from core.state import DocumentModel


class PubChemLoader:
    """Connector for NCBI PubChem PUG REST API."""

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BioResearchAI/1.0 (PubChem-Chemical-Resolver)"
        })

    def resolve_compound(self, name_or_cid: str) -> Optional[Dict[str, Any]]:
        """Look up chemical properties and SMILES for a compound name."""
        encoded = urllib.parse.quote(name_or_cid.strip())
        url = (
            f"{self.BASE_URL}/compound/name/{encoded}/property/"
            f"CanonicalSMILES,ConnectivitySMILES,IUPACName,MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,MolecularFormula/JSON"
        )
        try:
            resp = self.session.get(url, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                props = data.get("PropertyTable", {}).get("Properties", [])
                if props:
                    prop = props[0]
                    # Ensure CanonicalSMILES key is populated if ConnectivitySMILES is returned
                    if "CanonicalSMILES" not in prop and "ConnectivitySMILES" in prop:
                        prop["CanonicalSMILES"] = prop["ConnectivitySMILES"]
                    return prop
        except Exception as e:
            print(f"[PubChemLoader] Lookup error for '{name_or_cid}': {e}")
        return None

    def search(self, query: str, limit: int = 5) -> List[DocumentModel]:
        """Search PubChem compound records for query."""
        results: List[DocumentModel] = []
        
        # 1. Try direct resolution of query or extracted terms
        compound_info = self.resolve_compound(query)
        if compound_info:
            cid = compound_info.get("CID", "")
            smiles = compound_info.get("CanonicalSMILES") or compound_info.get("ConnectivitySMILES", "")
            iupac = compound_info.get("IUPACName", query)
            mw = compound_info.get("MolecularWeight", "N/A")
            logp = compound_info.get("XLogP", "N/A")
            formula = compound_info.get("MolecularFormula", "")

            abstract = (
                f"PubChem Compound Record: {query.title()} (CID: {cid})\n"
                f"Formula: {formula}, MW: {mw} g/mol, XLogP: {logp}\n"
                f"IUPAC Name: {iupac}\n"
                f"Canonical SMILES: {smiles}"
            )

            doc = DocumentModel(
                id=f"PubChem:CID{cid}",
                title=f"PubChem Chemical Entry: {query.title()} ({formula})",
                abstract=abstract,
                source="PubChem",
                url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                year="2024",
                authors=["NCBI PubChem"],
                chemical_entities=[smiles],
                bioactivity_data={"cid": cid, "smiles": smiles, "mw": mw, "logp": logp}
            )
            results.append(doc)

        # 2. Try fast text search across PubChem autocomplete / synonyms if limit > 1
        try:
            auto_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound/{urllib.parse.quote(query)}/json?limit={limit}"
            resp = self.session.get(auto_url, timeout=6)
            if resp.status_code == 200:
                suggestions = resp.json().get("dictionary_terms", {}).get("compound", [])
                for term in suggestions[:limit]:
                    if term.lower() != query.lower():
                        term_info = self.resolve_compound(term)
                        if term_info:
                            cid = term_info.get("CID", "")
                            smiles = term_info.get("CanonicalSMILES", "")
                            formula = term_info.get("MolecularFormula", "")
                            doc = DocumentModel(
                                id=f"PubChem:CID{cid}",
                                title=f"PubChem Chemical Entry: {term} ({formula})",
                                abstract=f"Compound: {term} (CID {cid}). SMILES: {smiles}",
                                source="PubChem",
                                url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
                                year="2024",
                                authors=["NCBI PubChem"],
                                chemical_entities=[smiles]
                            )
                            results.append(doc)
                            if len(results) >= limit:
                                break
        except Exception:
            pass

        return results[:limit]
