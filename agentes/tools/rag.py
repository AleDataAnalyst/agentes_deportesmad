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

import os
