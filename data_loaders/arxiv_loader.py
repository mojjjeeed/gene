"""
arXiv Data Loader (Quantitative Biology & Bioinformatics).
Fetches computational biology papers, machine learning drug discovery methods, and algorithms via arXiv API.
"""

import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Optional
import requests

from core.state import DocumentModel


class ArxivLoader:
    """Connector for arXiv quantitative biology (q-bio) and bioinformatics publications."""

    BASE_URL = "http://export.arxiv.org/api/query"
    ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BioResearchAI/1.0 (arXiv-Bioinformatics-Client)"
        })

    def search(self, query: str, limit: int = 10) -> List[DocumentModel]:
        """Search arXiv for biology, genomics, neuroscience, and molecular modeling papers."""
        results: List[DocumentModel] = []
        
        clean_query = query.replace('"', '').strip()
        search_query = f"(all:{clean_query}) AND (cat:q-bio.* OR cat:stat.ML OR cat:cs.AI OR cat:physics.chem-ph)"
        
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=12)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for entry in root.findall("atom:entry", self.ATOM_NS):
                    doc = self._parse_entry(entry)
                    if doc:
                        results.append(doc)
        except Exception as e:
            print(f"[ArxivLoader] Error querying arXiv: {e}")

        # Fallback: if category filter yielded no results, search without strict category filter
        if not results:
            try:
                params["search_query"] = f"all:{clean_query}"
                resp = self.session.get(self.BASE_URL, params=params, timeout=12)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    for entry in root.findall("atom:entry", self.ATOM_NS):
                        doc = self._parse_entry(entry)
                        if doc:
                            results.append(doc)
            except Exception as e:
                print(f"[ArxivLoader] Fallback search error: {e}")

        return results[:limit]

    def _parse_entry(self, entry: ET.Element) -> Optional[DocumentModel]:
        """Parse an arXiv Atom entry."""
        try:
            id_elem = entry.find("atom:id", self.ATOM_NS)
            raw_id = id_elem.text.strip() if id_elem is not None else ""
            arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

            title_elem = entry.find("atom:title", self.ATOM_NS)
            title = " ".join(title_elem.text.strip().split()) if title_elem is not None else "Untitled arXiv paper"

            summary_elem = entry.find("atom:summary", self.ATOM_NS)
            abstract = " ".join(summary_elem.text.strip().split()) if summary_elem is not None else ""

            published_elem = entry.find("atom:published", self.ATOM_NS)
            year = published_elem.text[:4] if published_elem is not None and published_elem.text else "Recent"

            authors: List[str] = []
            for author in entry.findall("atom:author", self.ATOM_NS):
                name_elem = author.find("atom:name", self.ATOM_NS)
                if name_elem is not None and name_elem.text:
                    authors.append(name_elem.text.strip())

            # URL
            url = f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else raw_id

            return DocumentModel(
                id=f"arXiv:{arxiv_id}",
                title=title,
                abstract=abstract,
                source="arXiv",
                url=url,
                year=year,
                authors=authors[:5],
                doi=None
            )
        except Exception as e:
            print(f"[ArxivLoader] Parse error: {e}")
            return None
