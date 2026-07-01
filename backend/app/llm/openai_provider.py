"""OpenAI-backed LLMProvider.

Also works unchanged against any OpenAI-compatible server (vLLM / Ollama / TGI)
by pointing base_url at it -- this is the migration path to a self-hosted
small model.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

from openai import OpenAI

from .base import ChatResult, Message, ToolCall, ToolSpec


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embed_model: str,
    ) -> None:
        # api_key may be a placeholder for local servers that don't check it.
        self._client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)
        self._chat_model = chat_model
        self._embed_model = embed_model

    def _to_openai(self, messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m.role == "tool":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": m.content,
                    }
                )
            elif m.tool_calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": m.content or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in m.tool_calls
                        ],
                    }
                )
            else:
                out.append({"role": m.role, "content": m.content})
        return out

    def _to_openai_tools(self, tools: list[ToolSpec] | None) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    def chat(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        tool_choice: Any = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ChatResult:
        kwargs: dict = {
            "model": self._chat_model,
            "messages": self._to_openai(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        oai_tools = self._to_openai_tools(tools)
        if oai_tools:
            kwargs["tools"] = oai_tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args)
            )

        return ChatResult(
            content=msg.content or "",
            model=resp.model,
            tool_calls=tool_calls,
            raw=resp.model_dump(),
        )

    def stream_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._chat_model,
            messages=self._to_openai(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._embed_model, input=texts)
        return [item.embedding for item in resp.data]
