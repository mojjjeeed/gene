"""PubMed via NCBI E-utilities: MeSH-aware search and the authoritative publication types."""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from typing import Any
from xml.etree.ElementTree import Element

from a9_contracts.literature_record import LiteratureRecord
from a9_contracts.search_plan import SearchPlan
from defusedxml import ElementTree

from a9_agents.sources.base import (
    SearchOutcome,
    SourceError,
    boolean_query,
    clean_text,
    collect,
    norm_doi,
    norm_pmcid,
    year_of,
)
from a9_agents.sources.http import PolicedClient, Policy

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _text(el: Element | None) -> str | None:
    return clean_text("".join(el.itertext())) if el is not None else None


class PubMed:
    name = "pubmed"

    def __init__(self, client: PolicedClient | None = None, *, page_size: int = 100):
        # 3 requests/second without an API key (10 with one).
        interval = 0.12 if os.environ.get("NCBI_API_KEY") else 0.36
        self._client = client or PolicedClient(
            Policy("pubmed", min_interval=interval, max_concurrency=2)
        )
        self._page_size = page_size

    @staticmethod
    def build_term(plan: SearchPlan) -> str:
        return boolean_query(plan, field_suffix="[Title/Abstract]", mesh_format='"{}"[MeSH Terms]')

    def _common(self) -> dict[str, Any]:
        params: dict[str, Any] = {"tool": "a9-research"}
        if key := os.environ.get("NCBI_API_KEY"):
            params["api_key"] = key
        if email := os.environ.get("A9_CONTACT_EMAIL"):  # opt-in only
            params["email"] = email
        return params

    async def search(self, plan: SearchPlan, *, limit: int = 100) -> SearchOutcome:
        return await collect(self.name, self._pages(plan, limit), limit)

    async def _pages(
        self, plan: SearchPlan, limit: int
    ) -> AsyncIterator[list[LiteratureRecord | None]]:
        start = 0
        while start < limit:
            size = min(self._page_size, limit - start)
            params: dict[str, Any] = {
                **self._common(),
                "db": "pubmed",
                "term": self.build_term(plan),
                "retstart": start,
                "retmax": size,
                "retmode": "json",
                "sort": "relevance",
            }
            if plan.date_from or plan.date_to:
                params["datetype"] = "pdat"
                params["mindate"] = (
                    plan.date_from.isoformat() if plan.date_from else "1900/01/01"
                ).replace("-", "/")
                params["maxdate"] = (
                    plan.date_to.isoformat() if plan.date_to else "3000/12/31"
                ).replace("-", "/")
            found = (await self._client.get(ESEARCH, params)).json()
            if "esearchresult" not in found:
                raise SourceError(self.name, f"unexpected response: {str(found)[:120]}")
            result = found["esearchresult"]
            if "ERROR" in result:
                raise SourceError(self.name, f"search rejected: {result['ERROR']}")
            ids: list[str] = result["idlist"]
            if not ids:
                return
            fetched = await self._client.get(
                EFETCH,
                {
                    **self._common(),
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "xml",
                    "rettype": "abstract",
                },
            )
            root = ElementTree.fromstring(fetched.content)
            articles = root.findall("PubmedArticle")
            if not articles:
                raise SourceError(self.name, "efetch returned no articles for the ids it was given")
            yield [self.to_record(a) for a in articles]
            start += len(ids)
            if start >= int(result["count"]):
                return

    @staticmethod
    def to_record(article: Element) -> LiteratureRecord | None:
        cit = article.find("MedlineCitation")
        art = cit.find("Article") if cit is not None else None
        if cit is None or art is None:
            return None
        title = _text(art.find("ArticleTitle"))
        pmid = _text(cit.find("PMID"))
        if not title or not pmid:
            return None

        parts = []
        for node in art.findall("Abstract/AbstractText"):
            text = _text(node)
            if text:
                label = node.get("Label")
                parts.append(f"{label}: {text}" if label else text)

        authors = []
        for a in art.findall("AuthorList/Author"):
            if (collective := _text(a.find("CollectiveName"))) is not None:
                authors.append(collective)
            else:
                name = " ".join(
                    p for p in (_text(a.find("ForeName")), _text(a.find("LastName"))) if p
                )
                if name:
                    authors.append(name)

        pub_date = art.find("Journal/JournalIssue/PubDate")
        year = (
            year_of(_text(pub_date.find("Year")))
            if pub_date is not None and pub_date.find("Year") is not None
            else None
        )
        if year is None and pub_date is not None:
            year = year_of(_text(pub_date.find("MedlineDate")))
        if year is None:
            year = year_of(_text(art.find("ArticleDate/Year")))

        ids = {
            i.get("IdType"): _text(i) for i in article.findall("PubmedData/ArticleIdList/ArticleId")
        }
        doi = norm_doi(ids.get("doi"))
        types = [t for n in art.findall("PublicationTypeList/PublicationType") if (t := _text(n))]
        return LiteratureRecord.model_validate(
            {
                "source": "pubmed",
                "source_id": pmid,
                "title": title,
                "abstract": "\n".join(parts) or None,
                "authors": authors,
                "year": year,
                "journal": _text(art.find("Journal/Title")),
                "doi": doi,
                "related_dois": [],
                "pmid": re.sub(r"\D", "", pmid),
                "pmcid": norm_pmcid(ids.get("pmc")),
                "arxiv_id": None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "licence": None,
                "is_open_access": None,
                "is_preprint": "Preprint" in types,
                "publication_types": types,
            }
        )
