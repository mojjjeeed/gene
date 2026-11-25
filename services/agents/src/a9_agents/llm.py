"""Model access behind one interface.

Nothing in the pipeline imports a provider SDK directly. There is no model access in development
today, so every feature has a deterministic stub; the Anthropic adapter below is written against the
documented tool-use API but has NOT been exercised against the real service.
"""

from __future__ import annotations

import os
from typing import Any, Protocol


class ModelError(Exception):
    """The model call failed or returned something unusable."""


class ModelClient(Protocol):
    async def structured(
        self, *, system: str, prompt: str, tool_name: str, json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Return one JSON object matching `json_schema`."""
        ...


class AnthropicModelClient:
    """Forces a single tool call whose input schema is `json_schema`, and returns its input."""

    def __init__(self, model: str | None = None, client: Any | None = None, max_tokens: int = 2048):
        self.model = model or os.environ.get("A9_PLANNER_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens
        if client is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ModelError("ANTHROPIC_API_KEY is not set; use A9_MODEL_PROVIDER=stub")
            import anthropic

            client = anthropic.AsyncAnthropic()
        self._client: Any = client

    async def structured(
        self, *, system: str, prompt: str, tool_name: str, json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        response: Any = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": tool_name,
                    "description": "Return the result.",
                    "input_schema": json_schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                if not isinstance(block.input, dict):
                    raise ModelError("tool input was not an object")
                return dict(block.input)
        raise ModelError("model did not call the requested tool")
