# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Source(StrEnum):
    europe_pmc = 'europe_pmc'
    pubmed = 'pubmed'
    openalex = 'openalex'
    crossref = 'crossref'
    arxiv = 'arxiv'
    biorxiv = 'biorxiv'
    medrxiv = 'medrxiv'
    fixture = 'fixture'


class LiteratureRecord(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: Source
    source_id: Annotated[
        str,
        Field(description="The source's own identifier for the record.", min_length=1),
    ]
    title: Annotated[str, Field(min_length=1)]
    abstract: str | None
    authors: list[str]
    year: int | None
    journal: str | None
    doi: Annotated[str | None, Field(description='Lower-case, no URL prefix.')]
    pmid: str | None
    pmcid: Annotated[
        str | None,
        Field(description='Upper-case with the PMC prefix, e.g. PMC1234567.'),
    ]
    arxiv_id: Annotated[str | None, Field(description='Without version suffix.')]
    url: Annotated[
        str,
        Field(
            description='Where a reader can open the record. Must resolve.',
            min_length=1,
        ),
    ]
    licence: Annotated[
        str | None,
        Field(
            description='As reported by the source. null means unknown, never assumed open.'
        ),
    ]
    is_open_access: bool | None
    is_preprint: bool
    publication_types: list[str]
