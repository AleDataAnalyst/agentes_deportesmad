"""agentes/grafo_documental.py — puerta de entrada del especialista documental."""
from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END

from agentes.nodes.documental import nodo_documental
from agentes.tools import imagen_preguntar

resultado = imagen_preguntar.invoke(
    {
        "image_id": "assets/imagen_demo.jpg",
        "pregunta": "¿Qué texto aparece en la imagen?",
    }
)

class EstadoDocumental(TypedDict, total=False):
    # entradas (el cliente puede dar solo las que tenga)
    request_id: str
    pedido: str
    contexto_permitido: list[str] | None
    image_id: str | None
    presupuesto_tools: int
    preparar_borrador: bool
    # salida (la escribe el nodo)
    documental: dict[str, Any]


def construir_grafo_documental():
    builder = StateGraph(EstadoDocumental)
    builder.add_node("documental", nodo_documental)
    builder.set_entry_point("documental")
    builder.add_edge("documental", END)
    return builder.compile()


_grafo = None

def obtener_grafo_documental():
    """El cliente usa esto, nunca nodo_documental directamente."""
    global _grafo
    if _grafo is None:
        _grafo = construir_grafo_documental()
    return _grafo