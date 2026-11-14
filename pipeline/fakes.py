"""Offline chat models: a placeholder for --dry-run and a scripted model for tests."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class PlaceholderChatModel(BaseChatModel):
    """Lets the full agent graph compile without a key. Any call raises."""

    model_name: str = "placeholder"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        raise RuntimeError("dry-run placeholder model: no model calls are made")

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> PlaceholderChatModel:  # type: ignore[override]
        return self

    @property
    def _llm_type(self) -> str:
        return "placeholder"


def tool_call(name: str, args: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    return {"name": name, "args": args, "id": call_id or f"call_{uuid.uuid4().hex[:10]}", "type": "tool_call"}


def ai(content: str = "", *calls: dict[str, Any]) -> AIMessage:
    return AIMessage(content=content, tool_calls=list(calls))


Step = AIMessage | Callable[[list[BaseMessage]], AIMessage]


class ScriptedChatModel(BaseChatModel):
    """Returns pre-scripted AIMessages (or the result of callables given the messages), in order."""

    script: list[Any]
    model_name: str = "scripted"
    calls: int = 0
    seen: list[list[BaseMessage]] = []

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        if self.calls >= len(self.script):
            raise RuntimeError(f"{self.model_name}: script exhausted after {self.calls} calls")
        step = self.script[self.calls]
        self.calls += 1
        self.seen.append(list(messages))
        msg = step(messages) if callable(step) else step
        msg = msg.model_copy(update={"id": f"msg_{uuid.uuid4().hex[:10]}"})
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> ScriptedChatModel:  # type: ignore[override]
        return self

    @property
    def _llm_type(self) -> str:
        return "scripted"
