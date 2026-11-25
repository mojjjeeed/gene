"""Triage: the heuristic and LLM triagers, Cohen's kappa, the eval harness, and verdict storage."""

from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from a9_agents.db import owner, scoped
from a9_agents.evals import triage as triage_eval
from a9_agents.evals.kappa import cohens_kappa
from a9_agents.llm import ModelError
from a9_agents.triage import HeuristicTriager, LlmTriager, TriageInput, make_triager
from a9_agents.verdicts import (
    clear_user_verdict,
    paper_verdicts,
    save_model_verdict,
    set_user_verdict,
)
from a9_contracts.screening_verdict import ScreeningVerdict
from a9_contracts.search_plan import SearchPlan
from sources_fixtures import EGFR_PLAN

# --- Cohen's kappa ------------------------------------------------------------------------------


def test_kappa_matches_the_textbook_example() -> None:
    # 20 both-yes, 5 yes/no, 10 no/yes, 15 both-no: p_o = 0.70, p_e = 0.50, kappa = 0.40
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert cohens_kappa(a, b) == pytest.approx(0.40)


def test_kappa_extremes() -> None:
    labels = ["include", "exclude", "include", "exclude"]
    assert cohens_kappa(labels, labels) == 1.0
    assert cohens_kappa(labels, ["exclude", "include", "exclude", "include"]) == pytest.approx(-1.0)
    assert cohens_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)


def test_kappa_is_not_fooled_by_a_model_that_says_the_majority_class_every_time() -> None:
    expert = ["include"] * 90 + ["exclude"] * 10
    lazy = ["include"] * 100
    assert sum(x == y for x, y in zip(expert, lazy, strict=True)) / 100 == 0.90  # 90% accurate...
    assert cohens_kappa(expert, lazy) == pytest.approx(0.0)  # ...and worth nothing


def test_kappa_counts_a_third_label_the_expert_never_uses_as_disagreement() -> None:
    expert = ["include", "exclude"] * 5
    model = ["unsure"] * 10
    assert cohens_kappa(expert, model) == pytest.approx(0.0)


def test_kappa_refuses_to_guess() -> None:
    with pytest.raises(ValueError, match="different numbers"):
        cohens_kappa(["a"], ["a", "b"])
    with pytest.raises(ValueError, match="no items"):
        cohens_kappa([], [])


# --- triagers -----------------------------------------------------------------------------------


async def test_heuristic_triager_reports_what_it_can_verify() -> None:
    t = HeuristicTriager()
    full = await t.triage(EGFR_PLAN, TriageInput("EGFR T790M in osimertinib resistance", "..."))
    assert (
        full.verdict.value == "include" and "EGFR" in full.reason and full.model == "heuristic-v1"
    )
    part = await t.triage(EGFR_PLAN, TriageInput("EGFR signalling in kidneys", "no mutation named"))
    assert part.verdict.value == "unsure" and "missing T790M" in part.reason
    none = await t.triage(EGFR_PLAN, TriageInput("Kidney function in elderly cohorts", "a study"))
    assert none.verdict.value == "exclude" and "title or abstract" in none.reason
    title_only = await t.triage(EGFR_PLAN, TriageInput("Kidney function", None))
    assert (
        title_only.verdict.value == "exclude"
        and "in the title" in title_only.reason
        and "abstract" not in title_only.reason.replace("title or abstract", "")
    )


async def test_heuristic_triager_uses_synonyms() -> None:
    v = await HeuristicTriager().triage(EGFR_PLAN, TriageInput("ERBB1 and T790M", None))
    assert v.verdict.value == "include"


class FakeModel:
    def __init__(self, reply: dict[str, Any]):
        self.reply, self.calls = reply, []  # type: ignore[var-annotated]

    async def structured(self, **kw: Any) -> dict[str, Any]:
        self.calls.append(kw)
        return self.reply


async def test_llm_triager_sends_the_criteria_and_stamps_who_decided() -> None:
    model = FakeModel(
        {
            "verdict": "exclude",
            "reason": "Matches exclusion criterion 1: kidney function.",
            "decided_by": "user",
        }
    )
    plan = SearchPlan.model_validate(
        {
            **EGFR_PLAN.model_dump(mode="json"),
            "include_criteria": ["lung cancer"],
            "exclude_criteria": ["kidney"],
        }
    )
    v = await LlmTriager(model, "claude-haiku-5-5").triage(
        plan, TriageInput("eGFR decline", "kidney")
    )
    assert (v.verdict.value, v.decided_by.value, v.model) == (
        "exclude",
        "model",
        "claude-haiku-5-5",
    )  # the model cannot claim to be the user
    sent = model.calls[0]
    assert "Include if: lung cancer" in sent["prompt"] and "Exclude if: kidney" in sent["prompt"]
    assert "no abstract" not in sent["prompt"]
    assert "do not guess" in sent["system"]
    again = await LlmTriager(model, "m").triage(plan, TriageInput("t", None))
    assert again and "(no abstract available)" in model.calls[1]["prompt"]


async def test_llm_triager_rejects_an_invalid_verdict() -> None:
    with pytest.raises(ModelError):
        await LlmTriager(FakeModel({"verdict": "maybe", "reason": "x"}), "m").triage(
            EGFR_PLAN, TriageInput("t", None)
        )


def test_triager_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("A9_MODEL_PROVIDER", raising=False)
    assert isinstance(make_triager(), HeuristicTriager)
    monkeypatch.setenv("A9_MODEL_PROVIDER", "nope")
    with pytest.raises(ValueError):
        make_triager()


# --- the eval harness ---------------------------------------------------------------------------


def write_golden(path: Path, labels: list[str]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["id", "topic", "doi", "year", "title", "abstract", "label"]
        )
        w.writeheader()
        for i, label in enumerate(labels):
            relevant = i % 2 == 0
            w.writerow({"id": f"r{i}", "topic": "t", "doi": "", "year": 2024,
                        "title": "EGFR T790M study" if relevant else "Kidney function cohort", "abstract": "", "label": label})  # fmt: skip


@pytest.fixture()
def eval_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    paths = {
        "golden": tmp_path / "g.csv",
        "plans": tmp_path / "p.json",
        "baseline": tmp_path / "b.json",
    }
    paths["plans"].write_text(json.dumps({"t": EGFR_PLAN.model_dump(mode="json")}))
    monkeypatch.setattr(triage_eval, "GOLDEN", paths["golden"])
    monkeypatch.setattr(triage_eval, "PLANS", paths["plans"])
    monkeypatch.setattr(triage_eval, "BASELINE", paths["baseline"])
    monkeypatch.delenv("A9_MODEL_PROVIDER", raising=False)
    return paths


def test_no_golden_set_means_not_measured_not_a_pass(
    eval_env: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert triage_eval.main([]) == 0
    assert "NOT MEASURED" in capsys.readouterr().out


def test_an_unlabelled_template_is_not_measured(
    eval_env: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    write_golden(eval_env["golden"], [""] * 100)
    assert triage_eval.main([]) == 0
    out = capsys.readouterr().out
    assert "NOT MEASURED" in out and "0 labelled rows (100 blank)" in out and "kappa=" not in out


def test_a_bad_label_is_an_error_not_silently_skipped(eval_env: dict[str, Path]) -> None:
    write_golden(eval_env["golden"], ["include", "yes"])
    with pytest.raises(ValueError, match="must be include or exclude"):
        triage_eval.load_golden(eval_env["golden"])


def test_scoring_records_a_baseline_then_gates_on_regression(
    eval_env: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    perfect = ["include", "exclude"] * 20  # the heuristic agrees with this labelling exactly
    write_golden(eval_env["golden"], perfect)
    assert triage_eval.main([]) == 0
    assert "kappa=1.000" in capsys.readouterr().out and eval_env["baseline"].exists()
    assert triage_eval.main([]) == 0 and "no regression" in capsys.readouterr().out

    flipped = ["exclude", "include"] * 20  # now the expert disagrees with everything
    write_golden(eval_env["golden"], flipped)
    assert triage_eval.main([]) == 1
    out = capsys.readouterr().out
    assert "REGRESSION" in out and "NOT MET" in out
    assert triage_eval.main(["--update"]) == 0  # accepting a lower baseline is a deliberate act


def test_the_committed_golden_template_is_well_formed() -> None:
    path = Path(__file__).resolve().parents[1] / "evals" / "triage_golden.csv"
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    plans = json.loads((path.parent / "triage_plans.json").read_text())
    assert len(rows) == 100 and len({r["id"] for r in rows}) == 100
    assert {r["topic"] for r in rows} == set(plans) and all(
        sum(1 for r in rows if r["topic"] == t) == 50 for t in plans
    )
    assert all(r["title"].strip() for r in rows)
    assert {r["label"] for r in rows} <= {"", "include", "exclude"}


# --- verdict storage ----------------------------------------------------------------------------


async def _one(c: Any, sql: str, *params: object) -> Any:
    row = await (await c.execute(sql, params)).fetchone()
    assert row is not None
    return row["id"]


async def seed(pool: Any) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user, paper = uuid.uuid4(), uuid.uuid4()
    async with owner(pool) as c:
        await c.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user, f"{user}@x.org"))
        await c.execute("INSERT INTO papers (id, title, source) VALUES (%s, 'p', 's')", (paper,))
    async with scoped(pool, role="a9_app", user_id=user) as c:
        project = await _one(
            c, "INSERT INTO projects (user_id, name) VALUES (%s, 'p') RETURNING id", user
        )
        conv = await _one(
            c,
            "INSERT INTO conversations (user_id, project_id) VALUES (%s, %s) RETURNING id",
            user,
            project,
        )
    return user, conv, paper


def model_verdict(v: str = "exclude") -> ScreeningVerdict:
    return ScreeningVerdict.model_validate(
        {"verdict": v, "reason": "because", "decided_by": "model", "model": "heuristic-v1"}
    )


async def test_a_user_override_sits_beside_the_model_verdict_and_wins(pool: Any) -> None:
    user, conv, paper = await seed(pool)
    async with scoped(pool, role="a9_worker") as c:
        await save_model_verdict(
            c, user_id=user, conversation_id=conv, paper_id=paper, verdict=model_verdict("exclude")
        )
        await save_model_verdict(
            c, user_id=user, conversation_id=conv, paper_id=paper, verdict=model_verdict("include")
        )  # a re-run: ignored
    async with scoped(pool, role="a9_app", user_id=user) as c:
        before = await paper_verdicts(c, conv, paper)
        assert (before["effective"], before["model"]["verdict"], before["user"]) == (
            "exclude",
            "exclude",
            None,
        )
        await set_user_verdict(
            c,
            user_id=user,
            conversation_id=conv,
            paper_id=paper,
            verdict="include",
            reason="I read it",
        )
        await set_user_verdict(
            c,
            user_id=user,
            conversation_id=conv,
            paper_id=paper,
            verdict="unsure",
            reason="changed my mind",
        )
        after = await paper_verdicts(c, conv, paper)
        assert after["effective"] == "unsure" and after["user"]["reason"] == "changed my mind"
        assert after["model"]["verdict"] == "exclude", "the model's verdict is never overwritten"
        assert await clear_user_verdict(c, conversation_id=conv, paper_id=paper) is True
        assert (await paper_verdicts(c, conv, paper))[
            "effective"
        ] == "exclude"  # the model's call applies again
        assert await clear_user_verdict(c, conversation_id=conv, paper_id=paper) is False


async def test_verdicts_are_private_to_their_owner(pool: Any) -> None:
    user, conv, paper = await seed(pool)
    other, _, _ = await seed(pool)
    async with scoped(pool, role="a9_worker") as c:
        await save_model_verdict(
            c, user_id=user, conversation_id=conv, paper_id=paper, verdict=model_verdict()
        )
    async with scoped(pool, role="a9_app", user_id=other) as c:
        assert (await paper_verdicts(c, conv, paper))["effective"] == "unscreened"
