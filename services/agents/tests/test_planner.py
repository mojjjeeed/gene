"""Planners and the model adapter. No network and no API key: the Anthropic client is a fake."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from a9_agents.llm import AnthropicModelClient, ModelError
from a9_agents.planner import LlmPlanner, StubPlanner, make_planner

TODAY = date(2026, 11, 25)


async def test_stub_planner_is_deterministic_and_labelled() -> None:
    planner = StubPlanner(today=TODAY)
    a = await planner.plan("Find novel EGFR inhibitors for T790M resistance")
    b = await planner.plan("Find novel EGFR inhibitors for T790M resistance")
    assert a == b
    assert a.generated_by.value == "stub" and a.model is None
    assert [c.label for c in a.concepts] == ["EGFR", "inhibitors", "T790M", "resistance"]
    assert all(
        c.synonyms == [] and c.mesh_terms == [] for c in a.concepts
    )  # the stub invents nothing
    assert (a.date_from, a.date_to) == (date(2016, 11, 25), TODAY)
    assert a.include_criteria and a.exclude_criteria


async def test_stub_planner_dedupes_caps_and_falls_back() -> None:
    planner = StubPlanner(today=TODAY)
    many = await planner.plan("alpha beta gamma delta epsilon zeta eta theta alpha")
    assert len(many.concepts) == 6
    assert len({c.label.lower() for c in many.concepts}) == 6
    only_stopwords = await planner.plan("the of and")
    assert [c.label for c in only_stopwords.concepts] == ["the of and"]
    with pytest.raises(ValueError):
        await planner.plan("   ")


async def test_stub_planner_handles_leap_day() -> None:
    plan = await StubPlanner(today=date(2024, 2, 29)).plan("x-ray")
    assert plan.date_from == date(2014, 2, 28)


class FakeModel:
    def __init__(self, reply: dict[str, Any]):
        self.reply, self.calls = reply, []  # type: ignore[var-annotated]

    async def structured(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.reply


VALID = {
    "concepts": [{"label": "EGFR", "synonyms": ["ERBB1"], "mesh_terms": ["ErbB Receptors"]}],
    "include_criteria": ["Primary research"],
    "exclude_criteria": ["Editorials"],
    "date_from": "2020-01-01",
    "date_to": None,
}


async def test_llm_planner_sends_the_plan_schema_and_stamps_provenance() -> None:
    model = FakeModel(
        {**VALID, "generated_by": "stub", "topic": "ignored"}
    )  # model cannot spoof these
    plan = await LlmPlanner(model, model_name="claude-sonnet-5-5").plan("  EGFR in NSCLC ")
    assert plan.generated_by.value == "llm" and plan.model == "claude-sonnet-5-5"
    assert plan.topic == "EGFR in NSCLC"
    assert plan.concepts[0].mesh_terms == ["ErbB Receptors"]
    call = model.calls[0]
    assert call["tool_name"] == "submit_search_plan"
    assert "concepts" in call["json_schema"]["properties"]
    assert "Topic: EGFR in NSCLC" in call["prompt"]
    assert "Do not invent MeSH" in call["system"]


async def test_llm_planner_rejects_an_invalid_plan() -> None:
    with pytest.raises(ModelError):
        await LlmPlanner(FakeModel({"concepts": []})).plan("EGFR")


class FakeAnthropic:
    def __init__(self, blocks: list[Any]):
        self.calls: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)
        self._blocks = blocks

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(content=self._blocks)


async def test_anthropic_adapter_forces_one_tool_call_and_returns_its_input() -> None:
    fake = FakeAnthropic(
        [
            SimpleNamespace(type="text", text="ok"),
            SimpleNamespace(type="tool_use", name="t", input={"a": 1}),
        ]
    )
    out = await AnthropicModelClient(model="m", client=fake).structured(
        system="s", prompt="p", tool_name="t", json_schema={"type": "object"}
    )
    assert out == {"a": 1}
    sent = fake.calls[0]
    assert sent["tool_choice"] == {"type": "tool", "name": "t"}
    assert sent["tools"][0]["input_schema"] == {"type": "object"}
    assert sent["model"] == "m" and sent["system"] == "s"


async def test_anthropic_adapter_errors_when_no_tool_call_comes_back() -> None:
    client = AnthropicModelClient(
        model="m", client=FakeAnthropic([SimpleNamespace(type="text", text="hi")])
    )
    with pytest.raises(ModelError, match="did not call"):
        await client.structured(system="s", prompt="p", tool_name="t", json_schema={})


def test_anthropic_adapter_needs_a_key_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ModelError, match="ANTHROPIC_API_KEY"):
        AnthropicModelClient()


def test_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("A9_MODEL_PROVIDER", raising=False)
    assert isinstance(make_planner(), StubPlanner)  # no credentials needed by default
    monkeypatch.setenv("A9_MODEL_PROVIDER", "nope")
    with pytest.raises(ValueError, match="nope"):
        make_planner()
