# Correspondencia del backend con el PB02

Actualización local del backend: 17/10/2026. Se mantienen las referencias
recogidas en la revisión del 13/10; no se han vuelto a verificar los enlaces
externos en esta continuación.

Referencias del bootcamp:

- [README del PB02](https://github.com/AleDataAnalyst/NEWAlejandra_AIEngineeringBootcamp/blob/main/Project_Break/PB_02_Agentes_LangGraph/README.md).
- [Guía HTML del PB02](https://github.com/AleDataAnalyst/NEWAlejandra_AIEngineeringBootcamp/blob/main/Project_Break/PB_02_Agentes_LangGraph/guia_pb02_agentes.html).
- [Live Review de calidad del aire](https://github.com/AleDataAnalyst/NEWAlejandra_AIEngineeringBootcamp/tree/main/06_AI_Agents_Engineering/Sprint_13/Practica_live_review/01_agente_langgraph_calidad_aire).

El README y el HTML del PB02 definen el entregable. La Live Review orienta el
patrón técnico; sus dobles y su mini-RAG no sustituyen las tools reales del PB02.
Los nombres de módulos y funciones son orientativos; se evalúa comportamiento.
El reparto del README local sigue vigente. Lo implementado por petición en esta
sesión no reasigna automáticamente las tareas pendientes del resto del equipo.

| Requisito | Evidencia actual | Pendiente para entrega |
|---|---|---|
| Supervisor + dos especialistas + síntesis + aplicar | Montaje secuencial con nodos inyectados; síntesis/aplicar deterministas implementados y probados con especialistas dobles | Resultados y herramientas reales de los especialistas; validación conjunta de fuentes y restricciones |
| Supervisor con fallback y topes en Python | Reglas deterministas, proveedor inyectable y MAX_ITER validado | Adaptador LLM acordado con Héctor; límites de tools por especialista |
| Plan y pausa antes de aplicar | Validación de respuesta/plan, MemorySaver e interrupt_before | Plan útil sustentado en fuentes reales |
| Aprobar/rechazar; done tras decisión humana | Servicio valida booleano y plan vigente; grafo exige done acorde con la decisión | Botones Streamlit y comandos CLI contra la misma API |
| Continuidad por thread_id | Grafo compartido por instancia, checkpoint por hilo y nueva conversación con UUID | Integración de la instancia en el ciclo de vida de ambos clientes |
| Traza visible de supervisor, tools y HITL | debug_trace del supervisor y de la decisión humana | Registro de tools con nombre, argumentos, status y preview; presentación en los clientes |
| RAG completo de magnitud PB1 | RAG recibido en `rag/`; traducción provisional documental con callable inyectable, probada con dobles | Coordinar puerta pública y entorno reproducible; indexado, consulta in-corpus, abstención y fuentes con RAG real |
| API + fallback, auxiliar y multimodal | Interfaces externas aún pendientes | Cuatro categorías reales, allowlist, validación y pruebas aisladas |
| Configuración y reproducibilidad | MAX_ITER en settings; dependencias del backend declaradas; pruebas sin claves | Dependencias de módulos reales, carga .env del punto de entrada, comandos CLI/Streamlit e indexado |
| Informe, presentación y Git | Síntesis/aplicar en commit `1b5c250`; exportador de evidencia simulada con 10 recorridos y 269 pruebas del backend superadas | Evidencias de especialistas y clientes reales, informe, presentación y revisión de PR hacia develop |

## Límites del alcance actual

El [handoff de integración](handoff_backend_integracion.md) permite avanzar con
David sin activar especialistas reales. La falta de dependencias de una `.venv`
incompleta no demuestra incompatibilidad ni un fallo del RAG del compañero.

- Los formatos ToolResult y Evidence son internos y provisionales. No fijan
  todavía entradas/salidas públicas de los especialistas.
- El servicio síncrono no implica ejecución paralela de especialistas. Los
  locks protegen el mismo hilo; no implementan fan-out/fan-in ni asincronía.
- MemorySaver e identificadores de plan viven en el proceso. Persistencia en
  disco, despliegue y multiagente de producción no se añaden como requisito.
- Registro de imagen, request_id y traza de tools requieren concretar sus
  contratos antes de integrar. No se consideran terminados por tener placeholders.
- La comprobación con dobles acredita integración del backend, no el cierre del
  PB02. Las herramientas reales y la demostración en CLI y Streamlit son obligatorias.
