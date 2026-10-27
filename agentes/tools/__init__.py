# agentes/tools/__init__.py
from typing import Any

__all__ = ["rag_preguntar", "imagen_preguntar", "hora_actual"]


def __getattr__(name: str) -> Any:
    if name == "rag_preguntar":
        from agentes.tools.rag import rag_preguntar

        return rag_preguntar

    if name == "imagen_preguntar":
        from agentes.tools.vision import imagen_preguntar

        return imagen_preguntar

    if name == "hora_actual":
        from agentes.tools.auxiliares import hora_actual

        return hora_actual

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)