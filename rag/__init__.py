"""Paquete rag — pipeline RAG de Deporte Municipal Madrid.

API pública:
    responder(pregunta, top_k=None) -> dict   (pipeline online completo)
    rag_ask(consulta) -> str                  (solo texto)
    ejecutar_pipeline(rutas, ...) -> dict     (indexado offline)
"""
from .logic import rag_ask, responder
from .pipeline import ejecutar_pipeline

__all__ = ["responder", "rag_ask", "ejecutar_pipeline"]


