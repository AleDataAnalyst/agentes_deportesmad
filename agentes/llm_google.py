from __future__ import annotations

import os
import json
from typing import Any

from google import genai
from google.genai import types

from agentes.llm import LlmAdapter, LlmMessage, LlmResponse


class GoogleAdapter(LlmAdapter):
    def __init__(self, client: Any | None = None, model: str | None = None):
        self.client = client or genai.Client(
            api_key=os.environ["GOOGLE_API_KEY"]
        )
        self.model = model or os.getenv("GOOGLE_GEN_MODEL")

        if not self.model:
            raise RuntimeError("Falta GOOGLE_GEN_MODEL")

    def generate(
        self,
        messages: list[LlmMessage],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        max_output_tokens: int,
        timeout: int,
    ) -> LlmResponse:
        instrucciones = [
            message.content
            for message in messages
            if message.role == "system"
        ]
        contents = [
            self._to_gemini(message)
            for message in messages
            if message.role != "system"
        ]

        # Acepta el esquema plano y el anidado estilo OpenAI ({"function": {...}}).
        planos = [tool.get("function", tool) for tool in tools]
        declaraciones = [
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters_json_schema=tool["parameters"],
            )
            for tool in planos
        ]

        if timeout <= 0:
            raise ValueError("timeout debe ser positivo")

        opciones = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "http_options": types.HttpOptions(
                timeout=timeout * 1000,
            ),
        }

        if instrucciones:
            opciones["system_instruction"] = "\n\n".join(instrucciones)

        if declaraciones:
            opciones["tools"] = [
                types.Tool(function_declarations=declaraciones)
            ]

        config = types.GenerateContentConfig(**opciones)

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        return self._parse(response)

    @staticmethod
    def _to_gemini(message: LlmMessage) -> types.Content:
        if message.role == "tool":
            return types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(
                        name=message.name or "",
                        response=json.loads(message.content or "{}"),
                    )
                ],
            )

        if message.role == "assistant" and message.tool_calls:
            return types.Content(
                role="model",
                parts=[
                    types.Part.from_function_call(
                        name=call["name"],
                        args=call.get("arguments", {}),
                    )
                    for call in message.tool_calls
                ],
            )

        return types.Content(
            role="user" if message.role in {"system", "user"} else "model",
            parts=[types.Part.from_text(text=message.content)],
        )

    @staticmethod
    def _parse(response: Any) -> LlmResponse:
        candidate = response.candidates[0] if response.candidates else None
        parts = candidate.content.parts if candidate and candidate.content else []

        tool_calls = [
            {
                "id": f"call_{index}",
                "name": part.function_call.name,
                "arguments": dict(part.function_call.args or {}),
            }
            for index, part in enumerate(parts)
            if getattr(part, "function_call", None) is not None
        ]

        return LlmResponse(
            text=response.text or "",
            tool_calls=tool_calls,
        )
