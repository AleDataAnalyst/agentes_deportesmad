"""Paquete rag — pipeline RAG de Deporte Municipal Madrid.

API pública:
    responder(pregunta, top_k=None) -> dict   (pipeline online completo)
    rag_ask(consulta) -> str                  (solo texto)
    ejecutar_pipeline(rutas, ...) -> dict     (indexado offline)
"""
from importlib import import_module

__all__ = ["responder", "rag_ask", "ejecutar_pipeline", "_formato_documento"]


def __getattr__(nombre):
    """Resolver la API pública sin cargar modelos al importar utilidades."""
    modulos = {
        "responder": ".logic", "rag_ask": ".logic",
        "ejecutar_pipeline": ".pipeline", "_formato_documento": ".load",
    }
    if nombre not in modulos:
        raise AttributeError(f"module {__name__!r} has no attribute {nombre!r}")
    return getattr(import_module(modulos[nombre], __name__), nombre)
