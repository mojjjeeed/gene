# GENERATED FROM packages/contracts/schemas - DO NOT EDIT. Run `pnpm generate`.

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, RootModel


class StageStarted(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['stage_started']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    stage: Annotated[str, Field(min_length=1)]


class Progress(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['progress']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    stage: Annotated[str, Field(min_length=1)]
    done: Annotated[int, Field(ge=0)]
    total: Annotated[int | None, Field(ge=0)]


class PartialResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['partial_result']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    stage: Annotated[str, Field(min_length=1)]
    payload: dict[str, Any]


class NeedsInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['needs_input']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    stage: Annotated[str, Field(min_length=1)]
    question: Annotated[
        dict[str, Any],
        Field(description='Interrupt payload; the answer resumes the same thread.'),
    ]


class StageFinished(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['stage_finished']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    stage: Annotated[str, Field(min_length=1)]


class RunFailed(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['run_failed']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    error: Annotated[str, Field(min_length=1)]


class CoverageNote(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]


class RunFinished(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    type: Literal['run_finished']
    run_id: Annotated[str, Field(min_length=1)]
    seq: Annotated[int, Field(ge=0)]
    ts: AwareDatetime
    trace_id: str | None = None
    coverage_notes: list[CoverageNote]


class RunEvent(
    RootModel[
        StageStarted
        | Progress
        | PartialResult
        | NeedsInput
        | StageFinished
        | RunFailed
        | RunFinished
    ]
):
    root: Annotated[
        StageStarted
        | Progress
        | PartialResult
        | NeedsInput
        | StageFinished
        | RunFailed
        | RunFinished,
        Field(
            description='The one event schema for every long run. seq is monotonic per run; the stream replays from Last-Event-ID.',
            title='RunEvent',
        ),
    ]
