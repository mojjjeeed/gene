# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class Verdict(StrEnum):
    include = 'include'
    exclude = 'exclude'
    unsure = 'unsure'


class DecidedBy(StrEnum):
    model = 'model'
    user = 'user'


class ScreeningVerdict(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    verdict: Verdict
    reason: Annotated[str, Field(min_length=1)]
    decided_by: DecidedBy
    model: Annotated[
        str | None,
        Field(
            description='Which model or heuristic decided. Required when decided_by is model.'
        ),
    ]
