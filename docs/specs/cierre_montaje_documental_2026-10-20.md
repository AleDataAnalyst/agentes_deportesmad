# Cierre del montaje documental con supervisor y grafo — 20/10/2026

**La conexión de backend ya está implementada y supera las pruebas de montaje. La validación documental real sigue pendiente de un índice compatible preparado y de una consulta con evidencia verificable.** No se necesita añadir código al montaje para suplir esa entrega.

Revisión de la copia de trabajo sobre HEAD `7465c023f31497b90ec41e16b3b07508df685c8f`. Se conserva todo el trabajo local previo, incluidos el cierre anterior, cambios de CLI/grafo y las plantillas/sonda de benchmark. No se modifica código de producto, pruebas, modelos, `.env`, dependencias ni código interno del RAG. No se ejecuta indexación, benchmark, recuperación real ni `smoke_real`. No se hace staging, commit, push, merge ni actualización de PR.

## 1. Conexión implementada

Ruta de ejecución existente:

```text
crear_servicio(modo="real") / crear_servicio_real()
  AgentService y supervisor principal
    crear_adaptador_documental(ejecutar_documental=obtener_grafo_documental().invoke)
      subgrafo documental -> nodo_documental
        REGISTRY["rag"] original -> _tool_rag -> rag_preguntar -> responder
      sobre documental -> ToolResult
    vuelta al supervisor -> instalaciones no disponibles -> síntesis -> FINISH
    pausa antes de aplicar -> resolver_plan(mismo hilo, decisión, plan_id vigente)
```

`runtime.py` pasa el método público `invoke` sin consultar durante la construcción. El documental no sustituye al supervisor ni comparte su checkpoint/HITL. Las guardias de síntesis/aplicar ya pertenecen a `build_graph`; no necesitan nuevas envolturas. `crear_servicio` mantiene modos explícitos y no sustituye por demo un fallo de construcción real.

Contratos revisados:

| Frontera | Contrato y conservación |
| --- | --- |
| RAG -> tool | `respuesta`, `fuentes`, `abstained`, `error`. Excepciones de `responder`, incluido timeout, se normalizan en error; no se convierten en respuesta válida |
| Tool -> documental | Observación `ok`, `resultado`, `fuentes`, `abstained`, `error`; evento por llamada con argumentos, fuentes, error y duración |
| Documental -> adaptador | Sobre `request_id`, `resultado`, `fuentes`, `abstained`, `errores`, `limitaciones`, `eventos`; identificador nuevo por pedido |
| Adaptador -> principal | Valida forma y coincidencia de `request_id`; `ToolResult.data` conserva el sobre; `Evidence.source` conserva fuentes confirmadas sin inventar fragmentos, scores ni fechas |
| Estado común | Errores prevalecen sobre abstención; respuesta vacía sin error se trata como abstención. Error/abstención cuentan como intento completado; no causan bucle infinito |
| HITL | Pausa `interrupt_before=["aplicar"]`; decisión booleana y plan vigente obligatorios; reanuda el mismo hilo |

La conservación tiene límites concretos, no equivale a guardar toda la salida interna del RAG:

- En éxito, las fuentes se deduplican en orden y aparecen en `data`, `Evidence` y síntesis. El evento conserva la lista recibida, incluso sus duplicados.
- En error o falta de evidencia, el documental no promueve texto parcial ni fuentes a evidencia confirmada. Las fuentes que acompañen al fallo permanecen en `data.eventos[].fuentes`; los errores permanecen en el evento, en `data.errores`, en `ToolResult.error` y en la síntesis.
- El contrato público de la tool tiene cuatro campos. No se afirma conservación de `chunks`, contexto o métricas adicionales de `rag.logic.responder` que esa tool no expone.
- Una aprobación conserva resultados y sobre. El rechazo limpia deliberadamente plan/resultados operativos; mantiene la traza. El nuevo pedido reinicia datos operativos y genera nuevos identificadores.
- Aprobar el plan cierra un flujo informativo; no certifica la evidencia ni ejecuta reservas, pagos o envíos. Checkpoints/decisiones viven en memoria del proceso.

## 2. Pruebas del montaje superadas

### Selección existente de backend

**276 passed, 15 warnings en 11.63 s** (13.968 s incluyendo preparación/importación del ejecutor). Evidencias:

- `tmp/cierre_montaje_documental_20261020/pytest_backend.txt`.
- `tmp/cierre_montaje_documental_20261020/pytest_backend.json`.

Selección ejecutada mediante `pytest.main`, sin autoload de plugins externos ni caché pytest. Se bloquearon conexiones de socket y `chromadb.PersistentClient` durante el proceso. Comando equivalente para reproducir la selección de pruebas existentes, sin lanzar la suite de herramientas/RAG:

```powershell
& .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  --basetemp=tmp/pytest-cierre-documental-revision `
  tests/test_runtime.py tests/test_documental_adapter.py `
  tests/test_agent_service.py tests/test_sync_integration.py `
  tests/test_backend_cierre.py tests/test_supervisor.py `
  tests/test_sintetizar_aplicar.py tests/test_infra_sintetizar_aplicar.py `
  tests/test_contracts.py tests/test_state.py `
  tests/test_import_boundaries.py tests/test_golden_graph.py
```

Ese comando reproduce la selección; los bloqueos adicionales de red/Chroma del ejecutor inline no son modificaciones de las pruebas. El golden usa especialistas simulados. Los tests de runtime existentes sustituyen la tool en `REGISTRY`; los del adaptador usan sobres documentales explícitos. No se confunden esos alcances con la consulta real.

No se recogió `tests/test_tools.py`: su código de colección intenta abrir la colección Chroma. Tampoco se ejecutaron suites de RAG ni de clientes. No se afirma que todas las pruebas del repositorio estén aprobadas.

### Frontera exacta del RAG, con el resto del montaje real

**10 recorridos aprobados en 9.663 s**, ejecutados mediante una sonda inline; no se añade un archivo de código ni una prueba al repositorio. Evidencia completa: `tmp/cierre_montaje_documental_20261020/montaje_frontera_rag.json`.

El único comportamiento externo sustituido fue el símbolo `agentes.tools.rag.responder`, que es el que usa la tool. `REGISTRY["rag"]` permaneció apuntando a su wrapper original. Se usaron tool, nodo, puerta pública del subgrafo, adaptador, runtime, supervisor, síntesis, servicio y aplicar originales. Solo se observó `runtime.aplicar` con una envoltura que delega en la implementación original para contar invocaciones. Red y cliente Chroma bloqueados.

| Caso doble en responder | Resultado comprobado | Decisiones |
| --- | --- | --- |
| Respuesta con fuentes y duplicados | `ok`; fuentes conservadas/deduplicadas y visibles; evento original conservado | Aprobar y rechazar |
| Falta de evidencia declarada | `abstained`; síntesis explícita, sin fuentes o contenido inventados | Aprobar y rechazar |
| Respuesta vacía sin flag de abstención | `abstained` derivado; no se presenta como éxito | Aprobar y rechazar |
| Error declarado con texto/fuente parcial | `error`; conserva el fallo y las fuentes en el evento, sin confirmar el parcial | Aprobar y rechazar |
| `requests.ReadTimeout` lanzado por responder | `error`; mensaje de timeout visible, evento conservado y sin repetición automática del RAG | Aprobar y rechazar |

En cada recorrido se verificaron: construcción sin consulta; una llamada al RAG por pedido; orden documental -> instalaciones -> síntesis -> FINISH; pausa antes de aplicar; bloqueo de otro turno mientras hay HITL; mismo hilo al reanudar; una sola aplicación; ausencia de consultas RAG al resolver; repetición idempotente; decisión contradictoria rechazada; plan antiguo rechazado; nuevo pedido/identificadores tras aprobar o rechazar; aislamiento de otro hilo y traza sin duplicados. Los timeouts son excepciones simuladas inmediatas, no una medición de espera ni de cancelación de Ollama.

Una primera sonda auxiliar se interrumpió por una aserción y no se contabiliza como aceptación. La sonda final empleó comprobaciones identificadas y completó los diez recorridos sin cambios en el producto. Los totales de arriba corresponden a las ejecuciones finales separadas; no se suman ensayos repetidos.

Los avisos de pytest son de deprecación de dependencias. LangGraph también emitió avisos sobre futura restricción de deserialización de las dataclasses del checkpoint; no son fallos actuales. Su mantenimiento se coordinará aparte, sin actualizar dependencias ni añadir configuración en este cierre.

## 3. Validación real pendiente y recurso concreto

La inspección de solo lectura de la configuración efectiva observó:

```text
CHROMA_DIR: ./output/chromadb
COLLECTION_NAME: deporte_municipal
EMBED_MODEL: qwen3-embedding:0.6b
EMBED_DIM: 1024
GEN_MODEL: smtek/Qwen3.8-27B:Q2_K_XL-16gb
TAG_MODEL: qwen2.5:3b
chroma.sqlite3 presente en la ruta efectiva: False
```

**Recurso que falta:** un índice Chroma ya preparado, poblado y verificable en esa ruta/colección, construido con el modelo y configuración de embeddings anteriores, más una consulta de aceptación cuya fuente esperada haya confirmado Héctor. La presencia de SQLite por sí sola no prueba población, compatibilidad o calidad.

Después de su entrega deben estar disponibles Ollama, el embedding y el generador configurados para una consulta documental real. Su disponibilidad/latencia no se ha vuelto a medir en esta revisión. TAG interviene en la preparación del índice; no es necesario repetir sus benchmarks para confirmar que el cableado del supervisor existe.

La aceptación real pendiente debe observar: una consulta con respuesta y fuente esperadas, una pregunta sin evidencia con abstención honesta y el ciclo aprobar/rechazar mediante el montaje real sin sustituciones. El comando ya existente `python -m scripts.smoke_real` puede efectuar hasta cuatro llamadas documentales y no se ha ejecutado aquí. Requiere primero la entrega y revisión del índice; no debe usarse para crearlo ni para ocultar un bloqueo con demo.

## Pendientes por responsable

| Responsable | Pendiente concreto | Qué permite cerrar |
| --- | --- | --- |
| Alejandra | Backend de supervisor/grafo y montaje documental: implementado y verificado con dobles. Conservar estas evidencias y coordinar la aceptación real tras recibir el índice | Cierre del cableado y sus contratos, sin más código preventivo |
| Héctor | Entregar índice reproducible compatible, procedencia/corpus y consulta/fuente de aceptación; confirmar configuración y respuesta real, abstención y errores de su componente | Validación real de recuperación/generación/documental |
| Héctor | Resolver, si se necesitan para preparar ese índice, los parámetros/tiempos de TAG y sus incidencias internas ya documentadas | Preparación fiable del recurso; no es una nueva conexión pendiente en runtime |
| David | Usar runtime con modo explícito en Streamlit, conservar servicio/hilo y refrescar/capturar errores de HITL | Integración de UI con el montaje. La inspección actual aún muestra `crear_servicio_demo()` directo; no se ha probado ni modificado la UI |
| Miguel | Entregar operación pública ejecutable del especialista de instalaciones y contrato de fuentes/errores/abstención | Sustituir la ausencia explícita actual mediante inyección/adaptación acordada; no rehacer el grafo |

Instalaciones continúa declarada como no disponible y nunca se sustituye por datos ficticios. El supervisor actual usa reglas/proveedor inyectable; no se presenta un router LLM como validado. Persistencia duradera, interfaz Streamlit completa, herramientas externas e imágenes permanecen fuera de esta aceptación.

## Preservación y propuesta de cierre

La comparación por hash de **152 archivos preexistentes** —incluidos `.env`, todos los módulos y cambios locales previos— no encontró modificaciones. Evidencia: `tmp/cierre_montaje_documental_20261020/integridad_inicial.json` e `integridad_final.json`.

Único documento nuevo propuesto por esta revisión para un cierre independiente:

```text
docs/specs/cierre_montaje_documental_2026-10-20.md
```

Los archivos de evidencia bajo `tmp/` quedan locales. No se cambia la propuesta del cierre anterior ni se incorporan plantillas/benchmark, cambios de compañeros, CLI o visualizaciones a este documento como si fueran parte de esta revisión. No se realiza commit ni push.
