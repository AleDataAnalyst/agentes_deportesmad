# Criterios de aceptación

Estado del 25/10/2026. Las pruebas offline verifican implementación y montaje;
la aceptación con servicios reales se registra por separado.

## Implementación verificada offline

| Criterio | Evidencia reproducible |
| --- | --- |
| Supervisor LLM/reglas, adaptadores Google/Ollama, modelo y límites configurados | `tests/test_llm_supervisor_real.py`, `tests/test_runtime.py` |
| Rutas permitidas, fallback, contador y límite en Python | `tests/test_supervisor.py`, `tests/test_supervisor_llm.py` |
| Construcción sin inferencia, consultas ni carga RAG/Chroma | `tests/test_import_boundaries.py` |
| Montaje de ambos especialistas, síntesis y cierre informativo | `tests/test_runtime.py`, `tests/test_sync_integration.py`, `tests/test_sintetizar_aplicar.py` |
| Pausa humana, plan vigente, aprobación/rechazo e idempotencia | `tests/test_agent_service.py`, `tests/test_backend_cierre.py` |
| Aislamiento del estado, validación de actualizaciones y serialización de pedidos del mismo hilo | `tests/test_node_guards.py`, `tests/test_state.py`, `tests/test_agent_service.py` |

## Aceptación real pendiente

- Router supervisor: selección de rutas con un modelo disponible y parámetros
  configurados. Puede validarse sin RAG ni fuentes externas; todavía no ejecutada.
- RAG: consulta de corpus con respuesta/fuente esperadas, abstención y fallo
  controlado sobre un índice compatible.
- Instalaciones: catálogo/avisos por HTTP, fallback fechado y auxiliar acordada.
- Multimodal: transporte de `image_id` hasta el documental, tool de imagen y
  presentación de evidencia visual con sus limitaciones.
- CLI y Streamlit: recorridos equivalentes con fuentes reales, fallo controlado
  y decisión humana sobre el mismo hilo y plan.

La serialización de pedidos del mismo hilo probada con dobles no acredita
paralelismo de especialistas, persistencia duradera ni aislamiento entre procesos.
El cierre informativo no realiza operaciones externas.
