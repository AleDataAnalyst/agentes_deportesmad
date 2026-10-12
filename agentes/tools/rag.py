"""Conector al RAG PB1 colocado en otra carpeta del mismo repositorio.

Entrada: query y top_k validados. Dependencia configurable: función importable
como rag.src.logic:responder con firma responder(pregunta, top_k=None).
Salida: ToolResult conservando respuesta, fuentes, fragmentos, abstained,
error y métricas relevantes. Distinguir ausencia de evidencia de fallo técnico.
Acotar contexto sin perder procedencia. No incluir corpus, embeddings, índice
ni implementación RAG. No indexar durante cada consulta ni alterar sys.path.
"""
