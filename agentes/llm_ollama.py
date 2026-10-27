from __future__ import annotations

import json
import os
import time
from typing import Any

import requests

from agentes.llm import LlmAdapter, LlmMessage, LlmResponse


class OllamaAdapter(LlmAdapter):
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        intentos: int = 3,
    ):
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.model = model or os.getenv("OLLAMA_GEN_MODEL")
        self.intentos = intentos

        if not self.model:
            raise RuntimeError("Falta OLLAMA_GEN_MODEL")

    def generate(
        self,
        messages: list[LlmMessage],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        max_output_tokens: int,
        timeout: int,
    ) -> LlmResponse:
        payload = {
            "model": self.model,
            "messages": [self._to_ollama(m) for m in messages],
            # Ollama espera el formato anidado {"type": "function", "function": {...}}.
            "tools": [
                tool if "function" in tool else {"type": "function", "function": tool}
                for tool in tools
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_output_tokens,
            },
        }

        ultimo_error: Exception | None = None

        for intento in range(self.intentos):
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                return self._parse(data)

            except Exception as exc:
                ultimo_error = exc
                if intento == self.intentos - 1:
                    raise
                time.sleep(2 ** intento)

        raise ultimo_error  # pragma: no cover

    @staticmethod
    def _to_ollama(message: LlmMessage) -> dict[str, Any]:
        if message.role == "tool":
            return {
                "role": "tool",
                "content": message.content,
            }

        if message.role == "assistant" and message.tool_calls:
            return {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "function": {
                            "name": call["name"],
                            "arguments": call.get("arguments", {}),
                        }
                    }
                    for call in message.tool_calls
                ],
            }

        return {
            "role": message.role,
            "content": message.content,
        }

    @staticmethod
    def _parse(data: dict[str, Any]) -> LlmResponse:
        message = data.get("message") or {}
        raw_calls = message.get("tool_calls") or []

        tool_calls = [
            {
                "id": f"call_{index}",
                "name": call["function"]["name"],
                "arguments": call["function"].get("arguments") or {},
            }
            for index, call in enumerate(raw_calls)
            if isinstance(call, dict) and "function" in call
        ]

        return LlmResponse(
            text=str(message.get("content") or ""),
            tool_calls=tool_calls,
        )