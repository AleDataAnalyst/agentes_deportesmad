# Golden dataset de regresión del grafo, versión 1

Este conjunto fija expectativas revisables sobre la orquestación. No modifica el grafo, servicio, especialistas, clientes ni la puerta pública documental.
Las respuestas y fuentes son sintéticas; no son normativa ni datos municipales.

## Datos y ejecutor

- `tests/data/golden_graph_v1.json`: consultas, fixtures de especialistas y expectativas de rutas, fuentes, restricciones y fallos. Usa `test://` y marca las preguntas como simuladas. Las expectativas se escriben explícitamente;
  no se regeneran desde una respuesta del sistema.
- `tests/test_golden_graph.py`: carga el JSON y ejecuta `AgentService`, el grafo, la traducción documental, `sintetizar` y `aplicar` reales. Inyecta únicamente
  especialistas/proveedor de rutas dobles y decisiones de prueba.

La política por defecto consulta documental e instalaciones en ese orden para estos casos. Las preguntas aportan contexto; no se evalúa comprensión del texto ni clasificación semántica de un supervisor LLM. Las rutas del proveedor se simulan explícitamente cuando el caso lo indica.

## Escenarios y oráculos

| Caso | Expectativa principal |
|---|---|
| Dos resultados con fuentes | Conserva ambas referencias y restricciones, sin inventar fragmentos |
| Documental útil y catálogo con error | Respuesta parcial; conserva el fallo del catálogo |
| Documental se abstiene y catálogo útil | Respuesta parcial; conserva la limitación documental |
| Error documental con abstención declarada | Prevalece error y se conserva también la abstención |
| Ambos se abstienen | No hay resultados útiles; plan informativo |
| Ambos devuelven error | No se convierten los errores en respuesta afirmativa |
| Fallback histórico con fecha parcial | Señala antigüedad; no completa el año ausente |
| Documental con texto vacío | La traducción lo trata como abstención |
| Límite antes de especialistas | Prepara síntesis sin inventar resultados de roles no ejecutados |
| Ruta desconocida del proveedor | Activa fallback y registra la causa |
| FINISH temprano sin plan | Pasa por síntesis antes de la pausa |
| Excepción del callable documental | Propaga el error y protege el pedido incompleto |

Los once escenarios que llegan a la pausa se ejecutan con aprobación y rechazo:
22 recorridos. El caso de excepción se ejecuta una vez; otra prueba comprueba la consistencia básica del catálogo: **24 pruebas nuevas**.

Para cada recorrido normal se comprueban fuentes exactas, expresiones requeridas y prohibidas, ruta ordenada, número de resultados útiles, pausa antes de aplicar, aplicación única, idempotencia, limpieza al rechazar, nuevo pedido en el mismo
hilo, rechazo del plan antiguo y aislamiento respecto de un hilo sin ejecutar.
También se verifica que no se modifica el dataset cargado.

No se fija toda la redacción de `final_answer` ni UUID concretos. Así se permiten mejoras de texto sin aceptar pérdida de referencias o restricciones. Algunos
fragmentos como «Fallback histórico» son condiciones de presentación deliberadas:
si cambia esa política, revisar el oráculo y su motivo; no actualizarlo para hacer pasar una regresión sin analizarla.

## Ejecución

```powershell
python -m pytest -q -p no:cacheprovider tests/test_golden_graph.py
```

Resultado de la versión inicial: **24 pruebas superadas**. La selección completa del backend, que incluye las 269 comprobaciones anteriores, pasa **293 pruebas**:

```powershell
python -m pytest -q -p no:cacheprovider tests/test_golden_graph.py tests/test_export_evidence.py tests/test_sintetizar_aplicar.py tests/test_documental_adapter.py tests/test_infra_sintetizar_aplicar.py tests/test_import_boundaries.py tests/test_sync_integration.py tests/test_agent_service.py tests/test_state.py tests/test_supervisor.py tests/test_demo.py tests/test_contracts.py tests/test_async.py tests/test_graph_hitl.py tests/test_clients.py
```

En esta revisión se usa una carpeta temporal nueva del workspace con `--basetemp` para evitar los permisos del directorio temporal del proceso.
Esta selección no recoge los tests que acceden al índice RAG durante colección.

## Relación con las 22 preguntas del RAG

`tests/evaluation_questions.json` se conserva intacto. Contiene preguntas, categorías y referencias esperadas, pero no constituye por sí solo un oráculo de respuesta completa, vigencia, evidencia o ciclo de vida de `AgentService`.
No se han confirmado aquí esas expectativas con el corpus real.

Para una segunda evaluación con especialistas reales, Héctor y Miguel deberán revisar cada caso contra una versión identificada del corpus/captura: fragmentos que sustentan la respuesta, fecha y alcance, abstenciones justificadas y restricciones que deben mostrarse. Las respuestas pueden variar de redacción, pero deben conservar esos hechos y referencias. Los errores técnicos inducidos se prueban por separado de los casos de calidad sobre evidencia disponible.

La elección nodo directo/subgrafo, el entorno reproducible y la preparación del índice siguen pendientes de coordinación. El dataset actual no resuelve esos bloqueos ni valida retrieval, API real, permisos de contexto, disponibilidad,
calidad de un LLM o la interfaz Streamlit. Aprobar en un test no equivale a una decisión humana en el producto.

## Mantenimiento

Cada caso nuevo necesita identificador estable, motivo, entrada, resultados simulados y expectativas independientes del código. Para pruebas de calidad real, añadir procedencia verificable y responsable de revisión antes de llamarlo
golden. Registrar cambios de política y versión del conjunto; conservar los casos negativos cuando llegue el RAG real. Este avance queda local y no se ha publicado automáticamente en la PR.
