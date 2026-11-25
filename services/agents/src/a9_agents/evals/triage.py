"""Evaluate a triager against the expert-labelled golden set.

    .venv-a9/bin/python -m a9_agents.evals.triage            # score; fail on regression
    .venv-a9/bin/python -m a9_agents.evals.triage --update   # accept the current score as the baseline

The golden set is evals/triage_golden.csv (labelled by a person, see evals/README.md). Until it has
labels this prints that nothing was measured; it never reports a score it did not compute.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from a9_contracts.search_plan import SearchPlan

from a9_agents.evals.kappa import cohens_kappa
from a9_agents.triage import TriageInput, Triager, make_triager

EVALS = Path(__file__).resolve().parents[3] / "evals"
GOLDEN = EVALS / "triage_golden.csv"
PLANS = EVALS / "triage_plans.json"
BASELINE = EVALS / "triage_baseline.json"
#: A change may not lower kappa by more than this against the recorded baseline.
ALLOWED_DROP = 0.02
TARGET = 0.70  # the PRD's gate


@dataclass
class Row:
    id: str
    topic: str
    title: str
    abstract: str | None
    year: int | None
    label: str


def load_golden(path: Path) -> tuple[list[Row], int]:
    """Returns (labelled rows, number of rows still unlabelled)."""
    labelled, blank = [], 0
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            label = (r.get("label") or "").strip().lower()
            if not label:
                blank += 1
                continue
            if label not in {"include", "exclude"}:
                raise ValueError(f"row {r['id']}: label must be include or exclude, got {label!r}")
            labelled.append(
                Row(
                    r["id"],
                    r["topic"],
                    r["title"],
                    r.get("abstract") or None,
                    int(r["year"]) if r.get("year") else None,
                    label,
                )
            )
    return labelled, blank


def load_plans(path: Path) -> dict[str, SearchPlan]:
    return {k: SearchPlan.model_validate(v) for k, v in json.loads(path.read_text()).items()}


async def score(
    triager: Triager, rows: list[Row], plans: dict[str, SearchPlan]
) -> tuple[float, dict[str, int]]:
    verdicts = await asyncio.gather(
        *(triager.triage(plans[r.topic], TriageInput(r.title, r.abstract, r.year)) for r in rows)
    )
    model = [v.verdict.value for v in verdicts]
    expert = [r.label for r in rows]
    return cohens_kappa(expert, model), {
        k: model.count(k) for k in ("include", "exclude", "unsure")
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update", action="store_true", help="accept the current score as the new baseline"
    )
    args = parser.parse_args(argv)

    if not GOLDEN.exists():
        print(
            "triage eval: NOT MEASURED. No golden set at evals/triage_golden.csv (see evals/README.md)."
        )
        return 0
    rows, blank = load_golden(GOLDEN)
    if len(rows) < 30:
        print(
            f"triage eval: NOT MEASURED. {len(rows)} labelled rows ({blank} blank); need the full set of labels first."
        )
        return 0

    triager = make_triager()
    kappa, counts = asyncio.run(score(triager, rows, load_plans(PLANS)))
    print(
        f"triage eval: kappa={kappa:.3f} over {len(rows)} labelled rows; {triager.name}; model verdicts {counts}"
    )
    print(f"             PRD gate is kappa >= {TARGET}: {'MET' if kappa >= TARGET else 'NOT MET'}")

    baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() else None
    if args.update or baseline is None:
        BASELINE.write_text(
            json.dumps(
                {"triager": triager.name, "kappa": round(kappa, 4), "rows": len(rows)}, indent=2
            )
            + "\n"
        )
        print(
            "             baseline recorded."
            if baseline is None
            else "             baseline updated."
        )
        return 0
    if baseline["triager"] != triager.name:
        print(
            f"             baseline was recorded for {baseline['triager']}; re-run with --update to compare {triager.name}."
        )
        return 0
    if kappa < baseline["kappa"] - ALLOWED_DROP:
        print(
            f"             REGRESSION: baseline {baseline['kappa']:.3f}, now {kappa:.3f} (allowed drop {ALLOWED_DROP})."
        )
        return 1
    print(f"             no regression against baseline {baseline['kappa']:.3f}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
