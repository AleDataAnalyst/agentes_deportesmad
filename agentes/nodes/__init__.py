"""Nodos del grafo con responsabilidades y actualizaciones delimitadas.

Cada nodo recibe estado y dependencias; devuelve una actualización parcial.
Los clientes no llaman directamente a los nodos.
"""
# agentes/nodes/__init__.py
"""agentes.nodes — nodos del grafo del agente (LangGraph).

API pública:
    nodo_documental(...) -> dict
"""
__all__ = ["nodo_documental"]


def __getattr__(name: str):
    """Carga el especialista solo cuando se solicita su API pública.

    Importar aplicar, sintetizar o supervisor no necesita el RAG ni sus modelos.
    Se conserva el callable original para los clientes del paquete.
    """
    if name == "nodo_documental":
        from .documental import nodo_documental

        return nodo_documental
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
