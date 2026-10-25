"""Configuración mínima del servicio síncrono, independiente del RAG y del LLM.

MAX_ITER limita la coordinación del supervisor y se lee del entorno al crear
el servicio. Es distinto de max_steps, que limitará las tools de cada
especialista. Si MAX_ITER falta o está vacío, se usa MAX_ITER_DEFAULT.

La selección LLM/reglas y los límites del proveedor pertenecen a
supervisor_llm_real; runtime carga .env antes de construirlos. Este módulo
solo lee MAX_ITER del entorno y no carga .env ni necesita claves.
"""

from dataclasses import dataclass
from os import environ

MAX_ITER_DEFAULT = 8


@dataclass(frozen=True)
class AgentSettings:
    """Configuración inmutable del servicio síncrono; no acepta booleanos."""

    max_iter: int = MAX_ITER_DEFAULT

    def __post_init__(self) -> None:
        if type(self.max_iter) is not int or self.max_iter < 1:
            raise ValueError("MAX_ITER debe ser un entero positivo")


def load_settings() -> AgentSettings:
    """Lee MAX_ITER al llamar, sin guardar configuración global del entorno.

    AgentService llama a esta función al construirse si no recibe settings.
    Los valores no enteros o no positivos producen ValueError.
    """
    raw = environ.get("MAX_ITER", "").strip()
    if not raw:
        return AgentSettings()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("MAX_ITER debe ser un entero positivo") from exc
    return AgentSettings(max_iter=value)
