"""Nodos del grafo con responsabilidades y actualizaciones delimitadas.

Cada nodo recibe estado y dependencias; devuelve una actualización parcial.
Los clientes no llaman directamente a los nodos.
"""
# agentes/nodes/__init__.py
"""agentes.nodes — nodos del grafo del agente (LangGraph).

API pública:
    nodo_documental(...) -> dict
"""
from .documental import nodo_documental

__all__ = ["nodo_documental"]