"""Construcción explícita del proveedor de rutas del supervisor."""

from __future__ import annotations

import os
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentes.llm import LlmAdapter
from agentes.supervisor_llm import crear_proveedor_rutas


def crear_proveedor_supervisor_real(
    *,
    adapter: LlmAdapter,
    temperature: float = 0,
    max_output_tokens: int = 256,
    timeout: int = 30,
):
    """Conecta un adaptador LLM al supervisor sin ejecutar inferencias."""
    from agentes.llm import LlmMessage
    return crear_proveedor_rutas(
        adapter=adapter,
        message_factory=LlmMessage,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )


def crear_proveedor_configurado():
    """Selección independiente de GEN_* del RAG, leída al construir el servicio."""
    modo = os.getenv("SUPERVISOR_MODE", "reglas").strip().lower()
    if modo == "reglas":
        return None
    if modo != "llm":
        raise ValueError("SUPERVISOR_MODE debe ser reglas o llm")
    provider = os.getenv("SUPERVISOR_PROVIDER", "").strip().lower()
    if provider not in {"google", "ollama"}:
        raise ValueError("SUPERVISOR_PROVIDER debe ser google u ollama")
    model = os.getenv("SUPERVISOR_MODEL", "").strip()
    if not model:
        raise ValueError("Falta SUPERVISOR_MODEL: indica un modelo disponible en el proveedor")

    def numero(name, default, convert, minimo, maximo):
        try:
            value = convert(os.getenv(name, default))
        except (ValueError, OverflowError):
            raise ValueError(f"{name} debe estar entre {minimo} y {maximo}") from None
        if not isfinite(value) or not minimo <= value <= maximo:
            raise ValueError(f"{name} debe estar entre {minimo} y {maximo}")
        return value

    temperature = numero("SUPERVISOR_TEMPERATURE", "0", float, 0, 2)
    tokens = numero("SUPERVISOR_MAX_OUTPUT_TOKENS", "256", int, 1, 4096)
    timeout = numero("SUPERVISOR_TIMEOUT", "30", int, 1, 240)
    if provider == "google":
        if not os.getenv("GOOGLE_API_KEY", "").strip():
            raise ValueError("Falta GOOGLE_API_KEY para el supervisor Google")
        from agentes.llm_google import GoogleAdapter
        adapter = GoogleAdapter(model=model)
    else:
        from agentes.llm_ollama import OllamaAdapter
        adapter = OllamaAdapter(model=model)
    return crear_proveedor_supervisor_real(
        adapter=adapter, temperature=temperature,
        max_output_tokens=tokens, timeout=timeout,
    )
