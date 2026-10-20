# agentes/tools/__init__.py
"""agentes.tools — tools para el agente de IA, accesibles mediante
registro autorizado.

API pública:
    rag_preguntar(consulta: str) -> dict
"""
__all__ = ["rag_preguntar"]


def __getattr__(name: str):
    """Evita cargar el RAG al importar otras herramientas del paquete."""
    if name == "rag_preguntar":
        from .rag import rag_preguntar

        return rag_preguntar
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
