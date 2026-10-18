"""
agentes/tools/rag.py
Tool RAG para agentes de IA.

Envuelve el pipeline RAG (rag/logic.py::responder) y expone al agente el  contrato
de resultado completo: respuesta, fuentes, abstención y control de errores.

Contrato:
    rag_preguntar(consulta: str) -> dict
        {
            "respuesta": str,
            "fuentes": list[str]
            "abstained": bool,
            "error": str | None,
        }
---
La tool nunca lanza excepción: los errores se devuelven en el dict.
"""


from __future__ import annotations

from typing import Any

def responder(consulta: str):
    """Carga el pipeline al consultar; importar o compilar no abre Chroma.

    Mantiene el punto sustituible en pruebas. Un fallo de importación queda
    dentro del manejo de errores de rag_preguntar, sin recurrir a una demo.
    """
    from rag.logic import responder as ejecutar
    return ejecutar(consulta)


def rag_preguntar(consulta: str) -> dict[str, Any]:
    """Busca en el corpus RAG y devuelve el resultado completo.

    Args:
        consulta: pregunta del agente (texto).

    Returns:
        dict con respuesta, fuentes, abstained y error.
    """
    try:
        resultado = responder(consulta)
    except Exception as e:  # noqa: BLE001 — la tool no rompe al agente
        return {
            "respuesta": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error interno del RAG: {e}",
        }

    return {
        "respuesta": resultado.get("respuesta", ""),
        "fuentes": list(resultado.get("fuentes", [])),
        "abstained": bool(resultado.get("abstained", False)),
        "error": resultado.get("error"),
    }


