"""Topic -> search plan.

`StubPlanner` is deterministic and makes no biomedical claims: it splits the topic into concepts and
fills generic criteria, and its output says `generated_by: "stub"` so the UI can label it. `LlmPlanner`
asks a model for the structured plan (concepts, synonyms, MeSH terms, criteria, date bounds).
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Any, Protocol

from a9_contracts.search_plan import SearchPlan

from a9_agents.llm import AnthropicModelClient, ModelClient, ModelError

_STOPWORDS = frozenset(
    "a an and are as at be by for from how in into is it of on or that the their this to using "
    "use via what which with without about novel new find explain why each".split()
)


class Planner(Protocol):
    async def plan(self, topic: str) -> SearchPlan: ...


def _shift_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February
        return d.replace(year=d.year - years, day=28)


class StubPlanner:
    def __init__(self, today: date | None = None):
        self._today = today

    async def plan(self, topic: str) -> SearchPlan:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic must not be empty")
        today = self._today or date.today()
        seen: set[str] = set()
        labels: list[str] = []
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']*", topic):
            key = token.lower()
            if len(key) < 3 or key in _STOPWORDS or key in seen:
                continue
            seen.add(key)
            labels.append(token)
        labels = labels[:6] or [topic]
        return SearchPlan.model_validate(
            {
                "topic": topic,
                "concepts": [
                    {"label": label, "synonyms": [], "mesh_terms": []} for label in labels
                ],
                "include_criteria": [
                    "Primary research or systematic review that addresses the topic"
                ],
                "exclude_criteria": [
                    "Not relevant to the topic",
                    "Retracted work is flagged, not excluded",
                ],
                "date_from": _shift_years(today, 10).isoformat(),
                "date_to": today.isoformat(),
                "generated_by": "stub",
                "model": None,
            }
        )


_SYSTEM = (
    "You plan literature searches for biomedical researchers. Given a topic, return a structured plan: "
    "the key concepts, synonyms and MeSH terms for each, include and exclude criteria, and date bounds. "
    "Do not invent MeSH terms; leave the list empty when you are not sure one exists."
)


class LlmPlanner:
    def __init__(self, client: ModelClient, model_name: str | None = None):
        self._client = client
        self._model_name = model_name

    async def plan(self, topic: str) -> SearchPlan:
        schema: dict[str, Any] = SearchPlan.model_json_schema()
        raw = await self._client.structured(
            system=_SYSTEM,
            prompt=f"Topic: {topic.strip()}",
            tool_name="submit_search_plan",
            json_schema=schema,
        )
        raw = {**raw, "topic": topic.strip(), "generated_by": "llm", "model": self._model_name}
        try:
            return SearchPlan.model_validate(raw)
        except ValueError as exc:
            raise ModelError(f"model returned an invalid plan: {exc}") from exc


def make_planner() -> Planner:
    provider = os.environ.get("A9_MODEL_PROVIDER", "stub")
    if provider == "stub":
        return StubPlanner()
    if provider == "anthropic":
        client = AnthropicModelClient()
        return LlmPlanner(client, model_name=client.model)
    raise ValueError(f"unknown A9_MODEL_PROVIDER {provider!r} (expected 'stub' or 'anthropic')")
