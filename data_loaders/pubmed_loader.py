"""
PubMed and PubMed Central (PMC) Data Loader.
Fetches research abstracts, PMIDs, authors, journal names, and publication dates via NCBI Entrez E-utilities.
"""

import time
import urllib.parse
from typing import List, Dict, Any, Optional
import xml.etree.ElementTree as ET
import requests

import config
from core.state import DocumentModel


class PubMedLoader:
    """Connector for NCBI PubMed / PMC via E-utilities API."""

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str = config.NCBI_EMAIL, api_key: str = config.NCBI_API_KEY):
        self.email = email
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"BioResearchAI/1.0 ({self.email})"
        })

    def search_pmids(self, query: str, max_results: int = 10) -> List[str]:
        """Search PubMed for PMIDs matching query with robust fallback."""
        clean_q = query.replace('"', '').strip()
        # Search title/abstract and mesh terms for maximum semantic relevance
        search_terms = f"({clean_q}[Title/Abstract]) OR ({clean_q})"
        params = {
            "db": "pubmed",
            "term": search_terms,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "email": self.email
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            url = f"{self.BASE_URL}/esearch.fcgi"
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                id_list = data.get("esearchresult", {}).get("idlist", [])
                if id_list:
                    return id_list
        except Exception as e:
            print(f"[PubMedLoader] Error during search: {e}")

        # Fallback to simple term search if title/abstract filter was too strict
        try:
            params["term"] = clean_q
            params["sort"] = "pub_date"
            url = f"{self.BASE_URL}/esearch.fcgi"
            resp = self.session.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("esearchresult", {}).get("idlist", [])
        except Exception:
            pass

        return []

    def fetch_summaries(self, pmids: List[str]) -> List[DocumentModel]:
        """Fetch summary and abstract data for given PMIDs."""
        if not pmids:
            return []

        docs: List[DocumentModel] = []
        try:
            # Using efetch to get full XML records including structured abstracts
            params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "email": self.email
            }
            if self.api_key:
                params["api_key"] = self.api_key

            url = f"{self.BASE_URL}/efetch.fcgi"
            resp = self.session.get(url, params=params, timeout=12)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for article in root.findall(".//PubmedArticle"):
                    doc = self._parse_pubmed_article(article)
                    if doc:
                        docs.append(doc)
        except Exception as e:
            print(f"[PubMedLoader] Error fetching summaries: {e}")

        return docs

    def _parse_pubmed_article(self, article: ET.Element) -> Optional[DocumentModel]:
        """Parse PubmedArticle XML into normalized DocumentModel."""
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                return None

            pmid_elem = medline.find("PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            article_elem = medline.find("Article")
            if article_elem is None:
                return None

            # Title
            title_elem = article_elem.find("ArticleTitle")
            title = "".join(title_elem.itertext()).strip() if title_elem is not None else "Untitled Paper"

            # Abstract
            abstract_parts = []
            abstract_elem = article_elem.find("Abstract")
            if abstract_elem is not None:
                for text_elem in abstract_elem.findall("AbstractText"):
                    label = text_elem.get("Label", "")
                    content = "".join(text_elem.itertext()).strip()
                    if label:
                        abstract_parts.append(f"{label}: {content}")
                    else:
                        abstract_parts.append(content)
            abstract = "\n".join(abstract_parts) if abstract_parts else "Abstract not available."

            # Year / Date
            journal_elem = article_elem.find("Journal")
            year = "Recent"
            if journal_elem is not None:
                pub_date = journal_elem.find(".//JournalIssue/PubDate")
                if pub_date is not None:
                    year_elem = pub_date.find("Year")
                    if year_elem is not None and year_elem.text:
                        year = year_elem.text
                    else:
                        medline_date = pub_date.find("MedlineDate")
                        if medline_date is not None and medline_date.text:
                            year = medline_date.text[:4]

            # Authors
            authors: List[str] = []
            author_list = article_elem.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None and last_name.text:
                        name = f"{last_name.text} {fore_name.text[0]}" if (fore_name is not None and fore_name.text) else last_name.text
                        authors.append(name)

            # DOI
            doi = None
            article_id_list = article.find(".//PubmedData/ArticleIdList")
            if article_id_list is not None:
                for article_id in article_id_list.findall("ArticleId"):
                    if article_id.get("IdType") == "doi":
                        doi = article_id.text
                        break

            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else (f"https://doi.org/{doi}" if doi else "")

            return DocumentModel(
                id=f"PMID:{pmid}",
                title=title,
                abstract=abstract,
                source="PubMed",
                url=url,
                year=str(year),
                authors=authors[:5],
                doi=doi,
                pmid=pmid,
                chemical_entities=[],
                bioactivity_data={}
            )
        except Exception as e:
            print(f"[PubMedLoader] Error parsing article XML: {e}")
            return None

    def search(self, query: str, limit: int = 10) -> List[DocumentModel]:
        """Perform end-to-end PubMed search."""
        pmids = self.search_pmids(query, max_results=limit)
        return self.fetch_summaries(pmids)
