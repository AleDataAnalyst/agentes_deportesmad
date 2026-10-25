"""Adaptador multi-provider del proveedor de modelos y prompts por responsabilidad.

El modelo propone llamadas a tools; Python valida la allowlist y las ejecuta.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Protocol

from agentes import config
from agentes.tools.rag import rag_preguntar

INSTRUCCIONES_TOOLS = """Eres un asistente técnico. Responde en español.

Para cualquier pregunta sobre documentos, instalaciones, servicios, normas,
fechas, precios, horarios, requisitos o condiciones, llama SIEMPRE primero a
`rag_preguntar`.

Después de recibir el resultado:
- Usa únicamente `respuesta` y `fuentes` como base de tu respuesta.
- Cita las fuentes devueltas por la herramienta.
- Si `abstained` es true, responde exactamente que no dispones de información
  suficiente en los documentos y pide el documento o dato que falta.
- Si `error` no es null, informa de que la consulta no pudo completarse.
- Nunca completes huecos con conocimiento general, suposiciones ni fuentes inventadas.
- No repites el contenido de la herramienta literalmente si puedes resumirlo,
  pero no añadas datos que no estén en ella."""


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "rag_preguntar",
            "description": (
                "Consulta la base de conocimiento RAG y devuelve respuesta, "
                "fuentes, indicador de abstención y error si lo hubiera."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {
                        "type": "string",
                        "description": "Pregunta del usuario en lenguaje natural.",
                    }
                },
                "required": ["consulta"],
            },
        },
    }
]


TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "rag_preguntar": rag_preguntar,
}


def _preview(valor: Any, limite: int = 500) -> str:
    """Convierte el resultado de una tool en una cadena acotada para la traza."""
    if isinstance(valor, str):
        texto = valor
    else:
        try:
            texto = json.dumps(valor, ensure_ascii=False, default=str)
        except Exception:
            texto = str(valor)
    return texto[:limite]


def _ejecutar_tool(nombre: str, args: dict[str, Any]) -> Any:
    """Ejecuta solo una tool de la allowlist; nunca propaga excepciones al modelo."""
    funcion = TOOL_REGISTRY.get(nombre)

    if funcion is None:
        return {
            "error": f"Tool no autorizada o desconocida: '{nombre}'"
        }

    try:
        return funcion(**args)
    except TypeError as exc:
        return {"error": f"Argumentos inválidos para '{nombre}': {exc}"}
    except Exception as exc:
        return {"error": f"Error ejecutando '{nombre}': {exc}"}

@dataclass
class LlmMessage:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LlmResponse:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LlmAdapter(Protocol):
    def generate(
        self,
        messages: list[LlmMessage],
        tools: list[dict[str, Any]],
        *,
        temperature: float,
        max_output_tokens: int,
        timeout: int,
    ) -> LlmResponse:
        ...

def crear_adapter() -> LlmAdapter:
    provider = str(config.GEN_PROVIDER).lower()

    if provider == "google":
        from agentes.llm_google import GoogleAdapter
        return GoogleAdapter()

    if provider == "ollama":
        from agentes.llm_ollama import OllamaAdapter
        return OllamaAdapter()

    if provider == "huggingface":
        from agentes.llm_huggingface import HuggingFaceAdapter
        return HuggingFaceAdapter()

    raise ValueError(f"GEN_PROVIDER no soportado: '{provider}'")

def run_tool_rag(
    mensaje_usuario: str,
    max_steps: int | None = None,
    *,
    adapter: LlmAdapter | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(mensaje_usuario, str) or not mensaje_usuario.strip():
        raise ValueError("El mensaje del usuario debe ser texto no vacío")

    limit = max_steps if max_steps is not None else config.MAX_STEPS
    if type(limit) is not int or limit < 1:
        raise ValueError("max_steps debe ser un entero positivo")

    adapter = adapter or crear_adapter()

    messages = [
        LlmMessage(role="system", content=INSTRUCCIONES_TOOLS),
        LlmMessage(role="user", content=mensaje_usuario),
    ]

    traza: list[dict[str, Any]] = []

    for paso in range(limit):
        response = adapter.generate(
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=config.GEN_TEMPERATURE,
            max_output_tokens=config.GEN_MAX_TOKENS,
            timeout=config.GEN_TIMEOUT,
        )

        if response.tool_calls:
            messages.append(
                LlmMessage(role="assistant", tool_calls=response.tool_calls)
            )

            for call in response.tool_calls:
                nombre = call["name"]
                args = call.get("arguments") or {}

                if not isinstance(args, dict):
                    resultado = {"error": f"Argumentos no estructurados para '{nombre}'"}
                else:
                    resultado = _ejecutar_tool(nombre, args)

                traza.append(
                    {
                        "paso": paso + 1,
                        "tool": nombre,
                        "args": args,
                        "resultado_preview": _preview(resultado),
                    }
                )

                messages.append(
                    LlmMessage(
                        role="tool",
                        name=nombre,
                        tool_call_id=call.get("id"),
                        content=json.dumps(
                            resultado, ensure_ascii=False, default=str
                        ),
                    )
                )

            continue

        if response.text.strip():
            return response.text.strip(), traza

        break

    return (
        "No he podido completar la consulta con la información disponible.",
        traza,
    )