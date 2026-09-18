"""
Web Search & Clinical Trials Data Loader.
Searches clinical trials, FDA approvals, and medical news via Serper API, Tavily, or public search endpoints.
"""

from typing import List
import urllib.parse
import requests

import config
from core.state import DocumentModel


class WebSearchLoader:
    """Connector for general biomedical web search and clinical trial news."""

    def __init__(self, serper_api_key: str = config.SERPER_API_KEY):
        self.serper_api_key = serper_api_key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "BioResearchAI/1.0 (Clinical-News-Crawler)"
        })

    def search(self, query: str, limit: int = 5) -> List[DocumentModel]:
        """Execute web search for clinical trials and regulatory updates."""
        results: List[DocumentModel] = []
        
        # 1. Try Serper API if key is configured
        if self.serper_api_key:
            try:
                url = "https://google.serper.dev/search"
                payload = {
                    "q": f"{query} clinical trials FDA therapeutic drug discovery",
                    "num": limit
                }
                headers = {
                    "X-API-KEY": self.serper_api_key,
                    "Content-Type": "application/json"
                }
                resp = self.session.post(url, json=payload, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("organic", [])[:limit]:
                        doc = DocumentModel(
                            id=f"Web:{item.get('link', '')}",
                            title=item.get("title", "Clinical Update"),
                            abstract=item.get("snippet", ""),
                            source="WebSearch",
                            url=item.get("link", ""),
                            year="2024",
                            authors=[item.get("source", "Web News")]
                        )
                        results.append(doc)
                    if results:
                        return results
            except Exception as e:
                print(f"[WebSearchLoader] Serper API error: {e}")

        # 2. Public ClinicalTrials.gov API (v2) fallback
        try:
            ct_url = "https://clinicaltrials.gov/api/v2/studies"
            params = {
                "query.term": query,
                "pageSize": limit,
                "format": "json"
            }
            resp = self.session.get(ct_url, params=params, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                studies = data.get("studies", [])
                for study in studies:
                    protocol = study.get("protocolSection", {})
                    ident = protocol.get("identificationModule", {})
                    nct_id = ident.get("nctId", "")
                    brief_title = ident.get("briefTitle", "Clinical Study")
                    
                    status_mod = protocol.get("statusModule", {})
                    overall_status = status_mod.get("overallStatus", "Unknown")
                    
                    desc_mod = protocol.get("descriptionModule", {})
                    brief_summary = desc_mod.get("briefSummary", "")

                    doc = DocumentModel(
                        id=f"ClinicalTrials:{nct_id}",
                        title=f"Clinical Trial {nct_id}: {brief_title}",
                        abstract=f"Status: {overall_status}\nSummary: {brief_summary}",
                        source="WebSearch",
                        url=f"https://clinicaltrials.gov/study/{nct_id}",
                        year="2024",
                        authors=["ClinicalTrials.gov"]
                    )
                    results.append(doc)
        except Exception as e:
            print(f"[WebSearchLoader] ClinicalTrials.gov search error: {e}")

        return results[:limit]
