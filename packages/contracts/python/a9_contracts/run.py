# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Kind(StrEnum):
    ingest = 'ingest'
    design = 'design'
    dossier = 'dossier'


class Status(StrEnum):
    queued = 'queued'
    running = 'running'
    needs_input = 'needs_input'
    failed = 'failed'
    finished = 'finished'


class CoverageNote(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: Annotated[
        str, Field(description='Named source, e.g. europe_pmc.', min_length=1)
    ]
    reason: Annotated[str, Field(min_length=1)]


class Run(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: Annotated[str, Field(min_length=1)]
    conversation_id: Annotated[str, Field(min_length=1)]
    kind: Kind
    status: Status
    created_at: AwareDatetime
    coverage_notes: Annotated[
        list[CoverageNote],
        Field(
            description='Named reduced-coverage notes. A source outage appears here, never as a run failure.'
        ),
    ]
