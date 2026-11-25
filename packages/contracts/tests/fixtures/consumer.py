"""Stand-in consumer of the generated Pydantic contract.

If a schema change removes or renames a field used here, `mypy --strict` must fail.
"""

from datetime import UTC, datetime

from a9_contracts.provenance_envelope import ProvenanceEnvelope
from a9_contracts.run import Run
from a9_contracts.run_event import StageStarted


def seq_of(event: StageStarted) -> int:
    return event.seq


def make_event() -> StageStarted:
    return StageStarted(
        type="stage_started", run_id="r1", seq=0, ts=datetime.now(UTC), stage="plan"
    )


def run_id_of(run: Run) -> str:
    return run.id


def page_of(envelope: ProvenanceEnvelope) -> int:
    return envelope.page
