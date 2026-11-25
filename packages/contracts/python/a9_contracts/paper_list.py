# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Status(StrEnum):
    queued = 'queued'
    running = 'running'
    needs_input = 'needs_input'
    failed = 'failed'
    finished = 'finished'


class ListedCoverageNote(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: str
    reason: str


class PaperCounts(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    total: Annotated[int, Field(ge=0)]
    include: Annotated[int, Field(ge=0)]
    exclude: Annotated[int, Field(ge=0)]
    unsure: Annotated[int, Field(ge=0)]
    unscreened: Annotated[int, Field(ge=0)]
    retracted: Annotated[
        int,
        Field(
            description='Papers with any retraction, withdrawal or expression of concern.',
            ge=0,
        ),
    ]


class Verdict(StrEnum):
    include = 'include'
    exclude = 'exclude'
    unsure = 'unsure'


class ListedVerdict(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    verdict: Verdict
    reason: str


class Status1(StrEnum):
    none = 'none'
    retracted = 'retracted'
    withdrawn = 'withdrawn'
    expression_of_concern = 'expression_of_concern'


class Retraction(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Status1
    checked: Annotated[
        bool,
        Field(description='false means not checked, which is different from clean.'),
    ]
    notice_dois: list[str]


class Effective(StrEnum):
    include = 'include'
    exclude = 'exclude'
    unsure = 'unsure'
    unscreened = 'unscreened'


class Verdict1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effective: Effective
    user: ListedVerdict | None
    model: ListedVerdict | None


class Paper(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: str
    title: Annotated[str, Field(min_length=1)]
    abstract: str | None
    authors: list[str]
    year: int | None
    journal: str | None
    doi: str | None
    url: Annotated[
        str,
        Field(
            description="Always present: a DOI link, else the source's own link.",
            min_length=1,
        ),
    ]
    sources: Annotated[
        list[str], Field(description='Every source that returned this paper.')
    ]
    licence: Annotated[
        str | None, Field(description='null means unknown, never assumed open.')
    ]
    is_open_access: bool | None
    is_preprint: bool
    retraction: Retraction
    verdict: Verdict1
    merge_reasons: Annotated[
        list[str], Field(description='Why several records became this one paper.')
    ]


class ListedRun(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: str
    status: Status
    coverage_notes: list[ListedCoverageNote]


class PaperList(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    conversation_id: str
    run: Annotated[
        ListedRun | None,
        Field(
            description="The latest ingest run, so the UI can show 'still searching' and name reduced coverage. null before any run."
        ),
    ]
    counts: PaperCounts
    papers: list[Paper]
