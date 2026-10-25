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
La tool nunca lanza excepción: los errores se devuelven en el dict como dato,
y ahora incorpora campos de diagnóstico (distancia_mejor, respuesta_llm, motivo).
"""


from __future__ import annotations

from typing import Any

from rag.logic import responder
import os
con_diagnostico = os.environ.get("RAG_CON_DIAGNOSTICO", "").lower() in {"1", "true", "yes"}

def rag_preguntar(consulta: str, con_diagnostico: bool | None = None) -> dict[str, Any]:
    """Devuelve el dict de contrato (4 claves) por defecto.
    
    Si con_diagnostico=True (o RAG_CON_DIAGNOSTICO=1/true/yes) se añaden 3 campos extra para depurar
    abstenciones. Nunca se eliminan las 4 claves del contrato.
    """
    if con_diagnostico is None:
        con_diagnostico = os.environ.get(
            "RAG_CON_DIAGNOSTICO", ""
        ).lower() in {"1", "true", "yes"}
    
    try:
        resultado = responder(consulta)
    except Exception as e:
        return {
            "respuesta": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error interno del RAG: {e}",
        }

    # Camino de éxito: SIEMPRE las 4 claves del contrato
    r = {
        "respuesta": resultado.get("respuesta", ""),
        "fuentes": list(resultado.get("fuentes", [])),
        "abstained": bool(resultado.get("abstained", False)),
        "error": resultado.get("error"),
    }

    # Campos de diagnóstico: solo si el agente los pide explícitamente
    if con_diagnostico:
        r["distancia_mejor"] = resultado.get("distancia_mejor")
        r["respuesta_llm"] = resultado.get("respuesta_llm")
        r["motivo"] = resultado.get("motivo_abstencion")

    return r
