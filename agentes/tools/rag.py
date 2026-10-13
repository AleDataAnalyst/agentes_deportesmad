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

Entrada: query y top_k validados. Dependencia configurable: función importable
como rag.src.logic:responder con firma responder(pregunta, top_k=None).
Salida: ToolResult conservando respuesta, fuentes, fragmentos, abstained,
error y métricas relevantes. Distinguir ausencia de evidencia de fallo técnico.
Acotar contexto sin perder procedencia. No incluir corpus, embeddings, índice
ni implementación RAG. No indexar durante cada consulta ni alterar sys.path.
"""


from __future__ import annotations

from typing import Any

from rag.logic import responder


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
    
    