"""Runtime behaviour of the generated Pydantic models: valid payloads load, invalid ones raise."""

import pytest
from a9_contracts.provenance_envelope import ProvenanceEnvelope
from a9_contracts.run_event import RunEvent
from pydantic import TypeAdapter, ValidationError

ENVELOPE = {
    "paper_id": "p1",
    "section_path": ["Methods", "Assay"],
    "page": 3,
    "char_start": 10,
    "char_end": 99,
    "parser_version": "grobid-0.8",
    "extraction_model": "claude",
    "prompt_version": "v1",
    "run_id": "r1",
}


def test_envelope_round_trips() -> None:
    assert ProvenanceEnvelope(**ENVELOPE).model_dump() == ENVELOPE  # type: ignore[arg-type]


@pytest.mark.parametrize("missing", sorted(ENVELOPE))
def test_envelope_without_any_field_raises(missing: str) -> None:
    payload = {k: v for k, v in ENVELOPE.items() if k != missing}
    with pytest.raises(ValidationError):
        ProvenanceEnvelope.model_validate(payload)


def test_event_union_dispatches_on_type() -> None:
    adapter = TypeAdapter(RunEvent)
    event = adapter.validate_python(
        {
            "type": "progress",
            "run_id": "r",
            "seq": 4,
            "ts": "2026-01-01T00:00:00Z",
            "stage": "search",
            "done": 3,
            "total": None,
        }
    )
    assert event.root.type == "progress"  # type: ignore[union-attr]


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(RunEvent).validate_python(
            {"type": "spinner", "run_id": "r", "seq": 0, "ts": "2026-01-01T00:00:00Z"}
        )
