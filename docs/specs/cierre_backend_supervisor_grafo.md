# Cierre del backend: supervisor, grafo y montaje

Revisión local: 19/10/2026, `integration/pruebas-streamlit`, HEAD de partida `7465c02`. El alcance es el backend de Alejandra contra los contratos actuales; no se declara terminado el producto completo ni validada su conexión externa.

## Resultado del alcance

No se han encontrado pendientes de código de producto dentro del alcance revisado: supervisor/router, fallback/límites, estado/trazas, grafo síncrono, síntesis/aplicar informativos, checkpointer/HITL, servicio, montaje y adaptación del contrato documental vigente.

Se conserva la implementación existente. No se añaden interfaces hipotéticas para instalaciones ni abstracciones para suplir entregas pendientes. Los nodos
compatibles se inyectan en `AgentService`/`build_graph`; runtime ya utiliza la puerta pública documental y declara explícitamente instalaciones no disponibles.

Sí se han cubierto dos huecos de verificación versionada: checkpointer aportado
por el llamante y recorrido de un proveedor que propone `FINISH` antes de que
exista plan. El caso temprano del golden local previo no se usa como sustituto
de una prueba versionable de cierre y no se modifica ese trabajo previo.

## Lista de aceptación

Todos los puntos siguientes están **cumplidos en el alcance de backend**.
Las herramientas/especialistas externos se sustituyen por dobles explícitos
donde se indica; no se extrapola el resultado a recuperación, generación o HTTP.

| Criterio | Estado | Evidencia ejecutada |
|---|---|---|
| Supervisor y router con rutas controladas | Cumplido | `test_supervisor.py`: propuestas válidas/incorrectas y guardia del router; `test_sync_integration.py` |
| Fallback y límite en Python | Cumplido | Excepción/propuesta inválida/rol repetido, topes y presupuesto de recursión en `test_supervisor.py`, `test_agent_service.py` |
| Estado compartido y copias aisladas | Cumplido | `test_state.py`: reset operativo, colecciones nuevas, deepcopy y conversión |
| Traza acumulada solo con eventos nuevos | Cumplido | `test_real_graph_accumulates_events_once_in_order`; dos pedidos por hilo en `test_agent_service.py` y prueba nueva |
| Nodos inyectables sin rehacer el grafo | Cumplido | `test_documental_adapter.py`, `test_sintetizar_aplicar.py`, `test_runtime.py`; mismo builder recibe implementaciones concretas y dobles |
| Contrato conserva fuentes, abstención, errores y limitaciones | Cumplido | `test_mapping_preserves_all_information_and_only_updates_own_fields`; sobre completo en `ToolResult.data`, fuentes en `Evidence`, error prevalece |
| Especialista no disponible declarado | Cumplido | `test_mixed_lifecycle_and_preserved_envelope`: instalaciones `abstained`, `available=False`, limitación visible en síntesis |
| Modo real sin sustitución silenciosa por demo | Cumplido | `test_real_creation_failure_never_falls_back_to_demo`; excepciones de adaptador/guardias sin datos ficticios |
| Síntesis y aplicar concretos con guardias | Cumplido | `test_infra_sintetizar_aplicar.py`, `test_sintetizar_aplicar.py`: formato, fuentes/restricciones, decisión requerida y cierre acorde |
| FINISH conduce a síntesis si falta plan y pausa antes de aplicar | Cumplido | Prueba nueva con `FINISH` temprano válido y aplicar contado; casos de límite en `test_sync_integration.py` |
| Checkpointer por defecto e inyectado | Cumplido | Checkpoints/pausa del servicio en suites existentes; prueba nueva lee la instancia externa inyectada y sus checkpoints |
| Aprobar/rechazar reanudan el mismo hilo | Cumplido | Servicio y runtime existentes; prueba nueva comprueba `thread_id` en checkpoint antes/después |
| Rechazo permite un nuevo pedido | Cumplido | `test_service_lifecycle_and_idempotency`, `test_real_nodes_in_service_pause_resume_idempotency_new_request_and_isolation` y prueba nueva |
| Decisiones repetidas y contradictorias, planes antiguos | Cumplido | `test_service_lifecycle_and_idempotency`: repetición sin aplicar otra vez, contradicción rechazada; siguiente pedido invalida plan anterior |
| Conversaciones aisladas | Cumplido | `test_unknown_thread_and_isolation`, ciclos del servicio/runtime y prueba nueva con segundo hilo sin checkpoint |
| Imports del backend separados del RAG | Cumplido | `test_import_boundaries.py`, import aislado del adaptador; crear montaje real puede cargar dependencias y no promete lo contrario |

Los contratos `ToolResult`/`Evidence` son internos. No se presenta como cerrado
un adaptador específico de una interfaz de instalaciones que todavía no existe.
El mecanismo de inyección y el comportamiento ante su ausencia sí están cerrados.

## Cambio de pruebas, sin cambio de producto

Archivo nuevo: `tests/test_backend_cierre.py`, dos casos parametrizados
(`aprobado=True/False`) de
`test_injected_checkpoint_keeps_early_finish_pause_and_same_thread_resume`.

- Usa supervisor, router, grafo, servicio, síntesis y aplicar existentes.
- Inyecta `MemorySaver` y lee sus checkpoints mediante `get_tuple` para comprobar
  que el servicio conserva el estado en esa misma instancia.
- Un proveedor doble propone `FINISH` desde la primera visita, por debajo del
  límite. Ambos especialistas son dobles que fallarían si fueran invocados.
- Verifica síntesis sin resultados inventados, plan y pausa antes de aplicar,
  decisión explícita, continuación del mismo hilo y cierre acorde.
- Comprueba aplicación única, idempotencia, otro hilo vacío, nuevo pedido tras
  ambas decisiones, rechazo de plan antiguo y secuencia de traza sin duplicados.

No se modifica `tests/test_runtime.py`, las pruebas originales de ningún
compañero ni las pruebas previas del backend. No se añade código de producto
porque los dos casos ya funcionan con la implementación existente.

## Validación reproducible

Selección explícita de backend, sin recoger suites de herramientas/RAG:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  --basetemp=tmp/pytest-cierre-final-7465c02 `
  tests/test_contracts.py tests/test_state.py tests/test_supervisor.py `
  tests/test_sync_integration.py tests/test_agent_service.py `
  tests/test_infra_sintetizar_aplicar.py tests/test_sintetizar_aplicar.py `
  tests/test_documental_adapter.py tests/test_import_boundaries.py `
  tests/test_demo.py tests/test_export_evidence.py tests/test_runtime.py `
  tests/test_backend_cierre.py
```

Resultado final observado: **277 passed, 3 warnings en 15.76 s**. Los avisos son
de deprecación de dependencias de Google GenAI, Chroma y langchain-community.
No se han actualizado dependencias para esta revisión.

Antes de añadir la prueba nueva, la misma selección sin ese archivo pasó
275 casos. La ejecución final de 277 es la referencia del cierre; no se suman
ejecuciones distintas. No se incluye el golden local previo ni se exige
incorporarlo a este commit. `test_graph_hitl.py` y `test_clients.py` contienen
solo docstrings; no se usan como evidencia ejecutable de sus títulos.

Alcance de los dobles:

- Pruebas del servicio/grafo: especialistas o proveedores dobles identificados.
- Adaptador: sobres documentales dobles para validar traducción y errores.
- Runtime: grafo documental y nodo originales, con tool RAG sustituida
  explícitamente en `REGISTRY`; conserva síntesis/aplicar concretos.
- Prueba nueva: ningún import/ejecución del documental, RAG, tools o HTTP.

**No se han ejecutado consultas reales al RAG ni HTTP de instalaciones.**
No se ejecuta ingesta, `smoke_real` ni preparación de índices automáticamente.

Comprobación de requisitos de solo lectura con `rag.config`, sin abrir Chroma:

```text
CHROMA_DIR = ./output/chroma_db
COLLECTION_NAME = deporte_municipal
chroma.sqlite3 presente = False
EMBED_PROVIDER = ollama
GEN_PROVIDER = ollama
RAG ejecutado = False
```

Ese bloqueo pertenece a la validación externa y no se oculta ni cambia de
proveedor. `crear_servicio_real` monta componentes; no es un preflight de índice.

## Pendientes por responsable

| Responsable | Pendiente concreto | Entrega/aceptación esperada |
|---|---|---|
| David | Sustituir construcción directa de demo por `crear_servicio(modo=...)` con modo explícito y servicio conservado por sesión | Recorrido de UI con hilo/plan vigentes; no conservar una demo anterior al cambiar de modo |
| David | Refrescar UI después de aprobar/rechazar y capturar errores de construcción/resolución | Un clic resuelve, retira botones, habilita chat y actualiza debug; error presentado sin afirmar éxito ni activar demo |
| David | Presentar fuentes/limitaciones/eventos desde dataclasses y traza acotada | Consumir `ToolResult.evidence` y `data`, sin exigir campos raíz inexistentes; pruebas propias del cliente |
| Héctor | Índice y configuración reproducibles y validación de su documental/RAG | Corpus/índice, colección, modelos/dimensión, dependencias, consulta con fuente esperada, abstención/error y pruebas de su componente |
| Héctor | Revisar incidencias de su componente y pruebas registradas en el handoff | Presupuesto del documental, contexto permitido y suites de herramientas/RAG; no quedan validados por la tool doble |
| Miguel | Publicar/conectar el especialista de instalaciones y sus herramientas | Callable síncrono importable, firma real, patch o sobre acordado, fuentes, fechas, fallback, abstención/error y pruebas de su bloque |
| Miguel / integrador que acuerde el equipo | Sustituir en el montaje la ausencia explícita cuando exista la interfaz real | Inyectar nodo compatible o adaptador acordado; conservar resultados mutuos y eventos nuevos sin rehacer aristas |

El handoff de interfaz con David ya está en
`docs/specs/revision_compatibilidad_streamlit_c9a3d45.md`; sigue siendo referencia
de la revisión anterior, no se modifica ni se afirma que sus defectos se hayan
corregido en esta tarea.

Puntos de conexión disponibles:

- `AgentService(documental_node=..., instalaciones_node=..., sintetizar_node=...,
  aplicar_node=..., route_provider=..., checkpointer=...)`.
- `crear_adaptador_documental(ejecutar_documental=...)` conserva el contrato
  documental actual; runtime ya pasa la puerta pública `.invoke`.
- El destino `instalaciones` ya existe; no necesita una nueva arista.
- `crear_servicio(modo="demo"|"real")` mantiene la API común. Un fallo real no
  activa el modo demo.

La validación final con entregas reales requiere colaboración de sus
responsables. No se contabiliza como funcionalidad externa terminada, pero no
requiere inventar más backend antes de recibirlas.

## Límites explícitos del cierre

- Supervisor por reglas con proveedor inyectable; conexión de un modelo de rutas
  no está implementada. Su reparto adicional con Héctor/equipo debe concretarse
  si se decide exigirla; no se presenta como un LLM en funcionamiento.
- Síntesis/aplicar son informativos: no reservan, pagan ni envían incidencias.
- Checkpoints, locks y registros de planes/decisiones viven en el proceso.
  Persistencia duradera, despliegue, historial semántico, imágenes por turno,
  asincronía y fan-out/fan-in no se incorporan al alcance solicitado.
- Presupuestos de herramientas y allowlist de especialistas no equivalen al
  `MAX_ITER` del supervisor; sus implementaciones quedan en sus bloques.
- Un plan estructuralmente válido no certifica fidelidad o vigencia de datos
  municipales; eso requiere evaluación con evidencia real.

## Archivos propuestos para un commit de cierre

Únicamente los nuevos archivos de esta tarea:

```text
tests/test_backend_cierre.py
docs/specs/cierre_backend_supervisor_grafo.md
```

El código de producto del alcance ya forma parte de HEAD; no necesita volver a
incluirse como cambio. No hay cambios en runtime, servicio, clientes,
especialistas ni proveedores para este cierre.

Fuera de la propuesta, conservados tal como estaban al comenzar:

```text
README.md
docs/specs/coordinacion_fase_integracion.md
docs/specs/golden_graph.md
docs/specs/revision_entorno_rag.md
output/debug_trace.diff
tests/data/
tests/test_golden_graph.py
tmp/
```

El cotejo de 280 archivos previos confirma 279 sin cambios. Hay una incidencia
de preservación fuera del código revisado: al terminar ya no está presente
`tmp/pdfs/reconstruccion/guia_reconstruida.pdf`, que sí existía al tomar las
huellas iniciales. No se ha editado ni borrado desde esta tarea y no se conoce
la causa de su ausencia. No se intenta regenerarlo ni sobrescribir otros
artefactos para ocultar esa diferencia. Los archivos de producto y cambios
previos de código/documentación permanecen sin modificaciones.

No se hace staging, commit, push, merge ni actualización de PR.
