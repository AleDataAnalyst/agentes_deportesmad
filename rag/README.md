# Incorporación del RAG

Aquí irá el RAG PB1 del equipo, sin contenido añadido en este cascarón.
El conector previsto está en agentes/tools/rag.py. No existe aún implementación.

Al mover el RAG, revisar imports (config/src → rag.config/rag.src o relativos),
rutas del corpus y Chroma y dependencias. Contrato previsto:
`responder(pregunta, top_k=None) -> dict`.
