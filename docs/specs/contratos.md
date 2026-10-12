# Coordinación de integración: supervisor, grafo y RAG

## Trabajo actual
Alejandra está preparando `contracts.py`, `state.py` y el supervisor para avanzar en la construcción del grafo. 

Las estructuras relacionadas con el RAG son provisionales y se revisarán cuando Héctor aporte el contrato del conector.

## Contrato RAG pendiente

Héctor aportará la interfaz del RAG a partir de su implementación real:

- Cómo se realiza una consulta.
- Qué devuelve y cómo incluye las fuentes.
- Cómo comunica la falta de evidencia.
- Cómo comunica los errores.
- Si la llamada es síncrona o asíncrona.

## Necesidades del supervisor y del grafo

Para integrar el especialista documental necesitamos poder:

- Enviarle una consulta.
- Incorporar su resultado al estado compartido.
- Conservar las fuentes disponibles.
- Distinguir una respuesta válida, falta de evidencia y fallo técnico.

Estas necesidades no fijan todavía la estructura de entrada y salida del conector.

## LLM compartido

Queda pendiente acordar con Héctor cómo consumirá el supervisor la interfaz de `llm.py`.

## Siguiente paso

Cuando esté disponible el contrato RAG, revisaremos juntos su encaje con `contracts.py` y `state.py`, y ajustaremos la integración necesaria.

