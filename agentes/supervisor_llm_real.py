"""Construcción explícita del proveedor de rutas del supervisor."""

from __future__ import annotations

from agentes.llm import LlmAdapter, LlmMessage
from agentes.supervisor_llm import crear_proveedor_rutas


def crear_proveedor_supervisor_real(
    *,
    adapter: LlmAdapter,
    temperature: float = 0,
    max_output_tokens: int = 256,
    timeout: int = 30,
):
    """Conecta un adaptador LLM al supervisor sin ejecutar inferencias."""
    return crear_proveedor_rutas(
        adapter=adapter,
        message_factory=LlmMessage,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )
