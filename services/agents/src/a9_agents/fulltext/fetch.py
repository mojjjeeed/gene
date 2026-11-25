"""Open-access full-text routes. A route returns bytes, their format and the licence the SOURCE states
(which beats whatever a search record said). Nothing here decides whether we may keep the text: the
licence evaluator does that, before anything is stored."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from defusedxml import ElementTree

from a9_agents.sources.base import SourceError
from a9_agents.sources.http import PolicedClient, Policy

NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"


class NoFullText(Exception):
    """No open route exists for this paper (not an error: most papers are not open access)."""


@dataclass(frozen=True)
class FullText:
    data: bytes
    format: Literal["jats", "pdf"]
    route: str
    licence_raw: str | None


class FullTextRoute(Protocol):
    name: str

    async def fetch(self, paper: dict[str, object]) -> FullText: ...


class PmcJats:
    """PubMed Central JATS XML via NCBI efetch (fast, ~1.5 s), falling back to Europe PMC (slow, flaky)."""

    name = "pmc_jats"

    def __init__(self, ncbi: PolicedClient | None = None, epmc: PolicedClient | None = None):
        interval = 0.12 if os.environ.get("NCBI_API_KEY") else 0.36
        self._ncbi = ncbi or PolicedClient(Policy("pmc", min_interval=interval, max_concurrency=2))
        self._epmc = epmc or PolicedClient(
            Policy("europe_pmc_fulltext", min_interval=0.3, max_concurrency=2, timeout=90)
        )

    @staticmethod
    def _licence(xml: bytes) -> str | None:
        from a9_agents.fulltext.jats import _licence

        return _licence(ElementTree.fromstring(xml))

    @staticmethod
    def _usable(xml: bytes) -> bool:
        root = ElementTree.fromstring(xml)
        article = root if root.tag == "article" else root.find(".//article")
        return article is not None and article.find("body") is not None

    async def fetch(self, paper: dict[str, object]) -> FullText:
        pmcid = paper.get("pmcid")
        if not pmcid:
            raise NoFullText("no PMCID")
        params = {"db": "pmc", "id": str(pmcid), "rettype": "xml"}
        if key := os.environ.get("NCBI_API_KEY"):
            params["api_key"] = key
        errors: list[str] = []
        for client, url, p in (
            (self._ncbi, NCBI_EFETCH, params),
            (self._epmc, EPMC_FULLTEXT.format(pmcid=pmcid), None),
        ):
            try:
                xml = (await client.get(url, p)).content
                if self._usable(xml):
                    return FullText(xml, "jats", self.name, self._licence(xml))
                errors.append("no full text body (not in the open-access subset)")
            except SourceError as exc:
                errors.append(exc.reason)
            except Exception as exc:  # malformed XML from one route must not stop the fallback
                errors.append(f"unreadable ({type(exc).__name__})")
        raise NoFullText("; ".join(errors))


_ARXIV_LICENCE = re.compile(
    r'href="(https?://(?:creativecommons\.org/[^"]+|arxiv\.org/licenses/[^"]+))"', re.IGNORECASE
)


class ArxivPdf:
    """arXiv PDFs. The per-paper licence is only on the abstract page, so read that FIRST; the PDF is
    downloaded only if the caller asks for it after the licence check (see `licence_of`)."""

    name = "arxiv_pdf"

    def __init__(self, client: PolicedClient | None = None):
        self._client = client or PolicedClient(
            Policy("arxiv_files", min_interval=3.1, max_concurrency=1, timeout=60)
        )

    async def licence_of(self, arxiv_id: str) -> str | None:
        page = (await self._client.get(f"https://arxiv.org/abs/{arxiv_id}")).text
        m = _ARXIV_LICENCE.search(page)
        return m.group(1) if m else None

    async def fetch_pdf(self, arxiv_id: str) -> bytes:
        return (await self._client.get(f"https://arxiv.org/pdf/{arxiv_id}")).content
