# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel


class SectionPathItem(RootModel[str]):
    root: Annotated[str, Field(min_length=1)]


class ProvenanceEnvelope(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper_id: Annotated[str, Field(min_length=1)]
    section_path: Annotated[
        list[SectionPathItem],
        Field(
            description='Heading path from the document root, e.g. ["Methods", "Assay"].',
            min_length=1,
        ),
    ]
    page: Annotated[int, Field(ge=1)]
    char_start: Annotated[int, Field(ge=0)]
    char_end: Annotated[int, Field(ge=0)]
    parser_version: Annotated[str, Field(min_length=1)]
    extraction_model: Annotated[str, Field(min_length=1)]
    prompt_version: Annotated[str, Field(min_length=1)]
    run_id: Annotated[str, Field(min_length=1)]
