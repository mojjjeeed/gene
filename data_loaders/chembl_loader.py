"""
ChEMBL Bioactivity Database Data Loader.
Fetches bioactivity data, IC50/Ki/EC50 values, target proteins, and clinical candidate information via ChEMBL REST API.
"""

from typing import List, Dict, Any, Optional
import urllib.parse
import requests

from core.state import DocumentModel


class ChEMBLLoader:
    """Connector for European Bioinformatics Institute (EMBL-EBI) ChEMBL database."""

    BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BioResearchAI/1.0 (ChEMBL-Bioactivity-Explorer)",
            "Accept": "application/json"
        })

    def search(self, query: str, limit: int = 10) -> List[DocumentModel]:
        """Search ChEMBL targets and associated bioactivities for a query."""
        results: List[DocumentModel] = []
        
        # 1. Search targets
        try:
            target_url = f"{self.BASE_URL}/target/search.json"
            resp = self.session.get(target_url, params={"q": query, "limit": min(limit, 5)}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                targets = data.get("targets", [])

                for target in targets:
                    target_chembl_id = target.get("target_chembl_id", "")
                    pref_name = target.get("pref_name", "Target Protein")
                    organism = target.get("organism", "Homo sapiens")
                    target_type = target.get("target_type", "SINGLE PROTEIN")

                    # Fetch bioactivities for this target
                    bioactivities = self._fetch_target_activities(target_chembl_id, limit=3)
                    
                    # Create summary document
                    activity_summary_lines = []
                    molecules = []
                    for act in bioactivities:
                        std_type = act.get("standard_type", "IC50")
                        std_value = act.get("standard_value", "N/A")
                        std_units = act.get("standard_units", "nM")
                        mol_name = act.get("molecule_chembl_id", "Compound")
                        activity_summary_lines.append(f"- Molecule {mol_name}: {std_type} = {std_value} {std_units}")
                        molecules.append(mol_name)

                    act_text = "\n".join(activity_summary_lines) if activity_summary_lines else "No direct bioactivity assays recorded."
                    abstract = (
                        f"ChEMBL Target Record: {pref_name} ({organism}) [{target_type}]\n"
                        f"Target ID: {target_chembl_id}\n\n"
                        f"Assay Bioactivity Measurements:\n{act_text}"
                    )

                    doc = DocumentModel(
                        id=f"ChEMBL:{target_chembl_id}",
                        title=f"ChEMBL Bioactivity Profile: {pref_name} ({organism})",
                        abstract=abstract,
                        source="ChEMBL",
                        url=f"https://www.ebi.ac.uk/chembl/target_report_card/{target_chembl_id}/",
                        year="2024",
                        authors=["EMBL-EBI ChEMBL Database"],
                        chemical_entities=molecules,
                        bioactivity_data={"target_id": target_chembl_id, "activities": bioactivities}
                    )
                    results.append(doc)
        except Exception as e:
            print(f"[ChEMBLLoader] Target search error: {e}")

        # 2. Search drug molecules if needed
        if len(results) < limit:
            try:
                mol_url = f"{self.BASE_URL}/molecule/search.json"
                resp = self.session.get(mol_url, params={"q": query, "limit": limit - len(results)}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    molecules = data.get("molecules", [])
                    for mol in molecules:
                        mol_chembl_id = mol.get("molecule_chembl_id", "")
                        pref_name = mol.get("pref_name") or mol_chembl_id
                        max_phase = mol.get("max_phase", "0")
                        mol_props = mol.get("molecule_properties", {}) or {}
                        mw = mol_props.get("full_mwt", "N/A")
                        logp = mol_props.get("cx_logp", "N/A")

                        abstract = (
                            f"ChEMBL Compound Record: {pref_name} (Max Clinical Phase: {max_phase})\n"
                            f"Molecular Weight: {mw} Da, LogP: {logp}\n"
                            f"Mechanism / Description: {mol.get('molecule_type', 'Small molecule')}"
                        )

                        doc = DocumentModel(
                            id=f"ChEMBL:{mol_chembl_id}",
                            title=f"ChEMBL Compound: {pref_name} (Phase {max_phase})",
                            abstract=abstract,
                            source="ChEMBL",
                            url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{mol_chembl_id}/",
                            year="2024",
                            authors=["ChEMBL"],
                            chemical_entities=[pref_name]
                        )
                        results.append(doc)
            except Exception as e:
                print(f"[ChEMBLLoader] Molecule search error: {e}")

        return results[:limit]

    def _fetch_target_activities(self, target_chembl_id: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch bioactivity assays (IC50 / Ki) for a specific target."""
        try:
            url = f"{self.BASE_URL}/activity.json"
            params = {
                "target_chembl_id": target_chembl_id,
                "standard_type__in": "IC50,Ki,EC50,Kd",
                "limit": limit
            }
            resp = self.session.get(url, params=params, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("activities", [])
        except Exception:
            pass
        return []
