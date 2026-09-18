"""
Preprint Servers Data Loader (bioRxiv & medRxiv).
Fetches unpublished manuscripts, preprints, authors, and abstracts via bioRxiv REST API and RSS feeds.
"""

from typing import List, Optional
import urllib.parse
from datetime import datetime, timedelta
import requests
import feedparser

from core.state import DocumentModel


class BioRxivLoader:
    """Connector for bioRxiv and medRxiv preprint servers."""

    BIORXIV_API = "https://api.biorxiv.org/details/biorxiv"
    MEDRXIV_API = "https://api.biorxiv.org/details/medrxiv"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BioResearchAI/1.0 (Preprint-Research-Engine)"
        })

    def search(self, query: str, limit: int = 10) -> List[DocumentModel]:
        """Search bioRxiv/medRxiv preprints matching query."""
        results: List[DocumentModel] = []
        
        # 1. Try bioRxiv REST API with recent date window
        try:
            today = datetime.now()
            start_date = (today - timedelta(days=120)).strftime("%Y-%m-%d")
            end_date = today.strftime("%Y-%m-%d")
            
            url = f"{self.BIORXIV_API}/{start_date}/{end_date}/0/json"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                collection = data.get("collection", [])
                
                query_tokens = [t.lower() for t in query.split() if len(t) > 2]
                for item in collection:
                    title = item.get("title", "")
                    abstract = item.get("abstract", "")
                    text_blob = f"{title} {abstract}".lower()
                    
                    # Match query tokens
                    if any(t in text_blob for t in query_tokens):
                        doi = item.get("doi", "")
                        authors_str = item.get("authors", "")
                        authors = [a.strip() for a in authors_str.split(";") if a.strip()][:5]
                        year = item.get("date", "2024")[:4]

                        doc = DocumentModel(
                            id=f"bioRxiv:{doi}",
                            title=title.strip(),
                            abstract=abstract.strip(),
                            source="bioRxiv",
                            url=f"https://doi.org/{doi}" if doi else "https://www.biorxiv.org",
                            year=year,
                            authors=authors,
                            doi=doi
                        )
                        results.append(doc)
                        if len(results) >= limit:
                            break
        except Exception as e:
            print(f"[BioRxivLoader] API search error: {e}")

        # 2. Fallback / supplement with RSS feed search if needed
        if len(results) < limit:
            try:
                rss_url = f"https://connect.biorxiv.org/biorxiv_xml.php?subject=all"
                feed = feedparser.parse(rss_url)
                query_tokens = [t.lower() for t in query.split() if len(t) > 2]

                for entry in feed.entries:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    text_blob = f"{title} {summary}".lower()

                    if any(t in text_blob for t in query_tokens):
                        link = entry.get("link", "")
                        published = entry.get("published", "Recent")
                        authors = [a.get("name", "") for a in entry.get("authors", [])][:5]

                        doc = DocumentModel(
                            id=f"bioRxiv:{entry.get('id', link)}",
                            title=title,
                            abstract=summary,
                            source="bioRxiv",
                            url=link,
                            year=published[:4] if len(published) >= 4 else "2024",
                            authors=authors
                        )
                        results.append(doc)
                        if len(results) >= limit:
                            break
            except Exception as e:
                print(f"[BioRxivLoader] RSS fallback error: {e}")

        return results[:limit]
