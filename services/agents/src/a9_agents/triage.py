"""Screening papers against a search plan's criteria.

`HeuristicTriager` is a keyword screen, not a model: it reports what it can verify (which concepts
appear in the title and abstract) and says 'unsure' for the rest. `LlmTriager` asks a cheap model for
a schema-constrained verdict and reason. The LLM path has NOT been run against a real model, and
nothing here has been measured against expert labels yet (see evals/README.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from a9_contracts.screening_verdict import ScreeningVerdict
from a9_contracts.search_plan import SearchPlan

from a9_agents.llm import AnthropicModelClient, ModelClient, ModelError
from a9_agents.sources.base import concept_terms


@dataclass(frozen=True)
class TriageInput:
    title: str
    abstract: str | None
    year: int | None = None
    journal: str | None = None
    is_preprint: bool = False


class Triager(Protocol):
    name: str

    async def triage(self, plan: SearchPlan, paper: TriageInput) -> ScreeningVerdict: ...


def _verdict(verdict: str, reason: str, model: str) -> ScreeningVerdict:
    return ScreeningVerdict.model_validate(
        {"verdict": verdict, "reason": reason, "decided_by": "model", "model": model}
    )


class HeuristicTriager:
    """Concept coverage in the title and abstract. Deterministic, free, and deliberately modest."""

    name = "heuristic-v1"

    async def triage(self, plan: SearchPlan, paper: TriageInput) -> ScreeningVerdict:
        text = f"{paper.title} {paper.abstract or ''}".lower()
        covered: list[str] = []
        missing: list[str] = []
        for concept in plan.concepts:
            hit = any(t.strip('"').lower() in text for t in concept_terms(concept))
            (covered if hit else missing).append(concept.label)
        if not covered:
            where = "title" if not paper.abstract else "title or abstract"
            return _verdict(
                "exclude", f"none of the plan's concepts appear in the {where}", self.name
            )
        if not missing:
            return _verdict(
                "include", f"all {len(covered)} concepts appear: {', '.join(covered)}", self.name
            )
        return _verdict(
            "unsure",
            f"covers {len(covered)} of {len(covered) + len(missing)} concepts; missing {', '.join(missing)}",
            self.name,
        )


_SYSTEM = (
    "You screen papers for a systematic literature review. Given the review's inclusion and exclusion "
    "criteria and one paper's title and abstract, decide include, exclude or unsure, and give a one "
    "sentence reason that cites the criterion. Say unsure when the abstract is missing or does not "
    "settle it: do not guess."
)


class LlmTriager:
    def __init__(self, client: ModelClient, model_name: str):
        self._client, self.name = client, model_name

    async def triage(self, plan: SearchPlan, paper: TriageInput) -> ScreeningVerdict:
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["include", "exclude", "unsure"]},
                "reason": {"type": "string"},
            },
            "required": ["verdict", "reason"],
        }
        prompt = (
            f"Topic: {plan.topic}\nInclude if: {'; '.join(plan.include_criteria) or '(none given)'}\n"
            f"Exclude if: {'; '.join(plan.exclude_criteria) or '(none given)'}\n\n"
            f"Title: {paper.title}\nAbstract: {paper.abstract or '(no abstract available)'}"
        )
        raw = await self._client.structured(
            system=_SYSTEM, prompt=prompt, tool_name="submit_verdict", json_schema=schema
        )
        try:
            return ScreeningVerdict.model_validate(
                {**raw, "decided_by": "model", "model": self.name}
            )
        except ValueError as exc:
            raise ModelError(f"model returned an invalid verdict: {exc}") from exc


def make_triager() -> Triager:
    provider = os.environ.get("A9_MODEL_PROVIDER", "stub")
    if provider == "stub":
        return HeuristicTriager()
    if provider == "anthropic":
        model = os.environ.get("A9_TRIAGE_MODEL", "claude-haiku-5-5")
        return LlmTriager(AnthropicModelClient(model=model, max_tokens=300), model)
    raise ValueError(f"unknown A9_MODEL_PROVIDER {provider!r} (expected 'stub' or 'anthropic')")
