# agentes/tools/__init__.py
"""agentes.tools — tools para el agente de IA, accesibles mediante
registro autorizado.

API pública:
    rag_preguntar(consulta: str) -> dict
"""
from .rag import rag_preguntar

__all__ = ["rag_preguntar"]