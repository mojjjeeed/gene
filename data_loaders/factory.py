"""
Unified Data Loader Factory.
Dispatches queries concurrently across all 6 data ingestion sources:
PubMed, bioRxiv, arXiv, ChEMBL, PubChem, and Web Search (ClinicalTrials/Serper).
"""

from typing import List, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from core.state import DocumentModel
from data_loaders.pubmed_loader import PubMedLoader
from data_loaders.biorxiv_loader import BioRxivLoader
from data_loaders.arxiv_loader import ArxivLoader
from data_loaders.chembl_loader import ChEMBLLoader
from data_loaders.pubchem_loader import PubChemLoader
from data_loaders.web_search_loader import WebSearchLoader


class DataLoaderFactory:
    """Orchestrates concurrent multi-source biomedical literature and data ingestion."""

    def __init__(self):
        self.pubmed = PubMedLoader()
        self.biorxiv = BioRxivLoader()
        self.arxiv = ArxivLoader()
        self.chembl = ChEMBLLoader()
        self.pubchem = PubChemLoader()
        self.web = WebSearchLoader()

    def fetch_all_sources(
        self,
        query: str,
        limit_per_source: int = 6,
        progress_callback: Callable[[str, str], None] = None
    ) -> List[DocumentModel]:
        """Query all 6 sources concurrently using a thread pool."""
        all_docs: List[DocumentModel] = []
        sources = {
            "PubMed": (self.pubmed.search, limit_per_source),
            "bioRxiv": (self.biorxiv.search, limit_per_source),
            "arXiv": (self.arxiv.search, limit_per_source),
            "ChEMBL": (self.chembl.search, limit_per_source),
            "PubChem": (self.pubchem.search, min(limit_per_source, 4)),
            "WebSearch": (self.web.search, min(limit_per_source, 4))
        }

        start_time = time.time()
        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_source = {
                executor.submit(func, query, limit): name
                for name, (func, limit) in sources.items()
            }

            for future in as_completed(future_to_source):
                src_name = future_to_source[future]
                try:
                    docs = future.result()
                    all_docs.extend(docs)
                    if progress_callback:
                        progress_callback(src_name, f"Retrieved {len(docs)} records")
                except Exception as e:
                    print(f"[DataLoaderFactory] Error fetching from {src_name}: {e}")
                    if progress_callback:
                        progress_callback(src_name, f"Failed: {e}")

        # Remove duplicate titles / IDs
        seen_ids = set()
        seen_titles = set()
        deduplicated: List[DocumentModel] = []

        for doc in all_docs:
            title_norm = doc.title.lower().strip()
            if doc.id and doc.id in seen_ids:
                continue
            if title_norm in seen_titles:
                continue

            seen_ids.add(doc.id)
            seen_titles.add(title_norm)
            deduplicated.append(doc)

        elapsed = round(time.time() - start_time, 2)
        print(f"[DataLoaderFactory] Ingested {len(deduplicated)} unique documents across 6 sources in {elapsed}s")
        return deduplicated
