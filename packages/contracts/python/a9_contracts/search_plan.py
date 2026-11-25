# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class GeneratedBy(StrEnum):
    stub = 'stub'
    llm = 'llm'


class Concept(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    label: Annotated[str, Field(min_length=1)]
    synonyms: list[str]
    mesh_terms: list[str]


class SearchPlan(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    topic: Annotated[str, Field(min_length=1)]
    concepts: Annotated[list[Concept], Field(min_length=1)]
    include_criteria: list[str]
    exclude_criteria: list[str]
    date_from: date | None
    date_to: date | None
    generated_by: Annotated[
        GeneratedBy,
        Field(
            description='Which planner produced this plan. A stub plan is a placeholder and is labelled as such in the UI.'
        ),
    ]
    model: str | None = None
