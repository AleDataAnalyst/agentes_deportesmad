"""Bucle común de los especialistas: el LLM propone tools y Python decide.

Cada especialista aporta su prompt de sistema y su allowlist (lista de
Herramienta). Python ejecuta solo las tools de esa lista, corta al llegar a
max_steps llamadas y registra cada llamada con nombre, argumentos, estado y
una vista previa del resultado. Una tool fuera de la lista no se ejecuta.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from agentes import config
from agentes.llm import LlmAdapter, LlmMessage, _preview, crear_adapter

MODOS = {"reglas", "llm"}


@dataclass(frozen=True)
class Herramienta:
    """Tool autorizada para un especialista."""

    nombre: str
    descripcion: str
    parametros: dict[str, Any]
    funcion: Callable[..., dict[str, Any]]

    def esquema(self) -> dict[str, Any]:
        return {"name": self.nombre, "description": self.descripcion, "parameters": self.parametros}


def modo_especialistas() -> str:
    """Lee ESPECIALISTAS_MODO (reglas | llm). Por defecto, reglas."""
    modo = os.getenv("ESPECIALISTAS_MODO", "reglas").strip().lower()
    if modo not in MODOS:
        raise ValueError("ESPECIALISTAS_MODO debe ser reglas o llm")
    return modo


class FalloPlanificacion(RuntimeError):
    """Conserva las herramientas ejecutadas antes de fallar el modelo."""

    def __init__(self, llamadas):
        super().__init__("No se pudo completar la planificación LLM")
        self.llamadas = list(llamadas)


def ejecutar_especialista(
    *,
    prompt_sistema: str,
    mensaje: str,
    herramientas: list[Herramienta],
    max_steps: int,
    adapter: LlmAdapter | None = None,
) -> list[dict[str, Any]]:
    """Deja que el modelo proponga tools y ejecuta solo las permitidas.

    Devuelve una entrada por llamada propuesta:
    {"paso", "tool", "args", "status", "preview", "resultado"}.
    status es ok, error, bloqueada (fuera de la allowlist) o args_invalidos.
    max_steps limita el número total de llamadas ejecutadas o bloqueadas.
    """
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps debe ser un entero positivo")

    permitidas = {h.nombre: h for h in herramientas}
    adapter = adapter or crear_adapter()
    mensajes = [
        LlmMessage(role="system", content=prompt_sistema),
        LlmMessage(role="user", content=mensaje),
    ]
    llamadas: list[dict[str, Any]] = []

    while len(llamadas) < max_steps:
        try:
            respuesta = adapter.generate(
                messages=mensajes,
                tools=[h.esquema() for h in herramientas],
                temperature=config.GEN_TEMPERATURE,
                max_output_tokens=config.GEN_MAX_TOKENS,
                timeout=config.GEN_TIMEOUT,
            )
        except Exception as exc:
            # Entregar al nodo las llamadas ya realizadas.
            raise FalloPlanificacion(llamadas) from exc
            
        if not respuesta.tool_calls:
                    break

        mensajes.append(LlmMessage(role="assistant", tool_calls=respuesta.tool_calls))
        for call in respuesta.tool_calls:
            if len(llamadas) >= max_steps:
                break
            nombre = str(call.get("name", ""))
            args = call.get("arguments") or {}
            herramienta = permitidas.get(nombre)

            if herramienta is None:
                status, resultado = "bloqueada", {"error": f"Tool no autorizada: '{nombre}'"}
            elif not isinstance(args, dict):
                status, resultado = "args_invalidos", {"error": "Argumentos no estructurados"}
            else:
                try:
                    resultado = herramienta.funcion(**args)
                    status = "error" if resultado.get("error") else "ok"
                except TypeError as exc:
                    status, resultado = "args_invalidos", {"error": f"{type(exc).__name__}: {exc}"}
                except Exception as exc:  # noqa: BLE001 - la tool nunca rompe el nodo
                    status, resultado = "error", {"error": f"{type(exc).__name__}: {exc}"}

            llamadas.append({
                "paso": len(llamadas) + 1,
                "tool": nombre,
                "args": args if isinstance(args, dict) else {},
                "status": status,
                "preview": _preview(resultado, 200),
                "resultado": resultado,
            })
            mensajes.append(LlmMessage(
                role="tool", name=nombre, tool_call_id=call.get("id"),
                content=json.dumps(resultado, ensure_ascii=False, default=str),
            ))

    return llamadas
