# Conexión real del grafo supervisor

Alcance confirmado: montaje e integración del grafo supervisor. Los nodos de
Héctor y Miguel y los clientes de David permanecen bajo su responsabilidad.

Actualización del montaje (25/10/2026): Miguel ya entregó `nodo_instalaciones`
y runtime lo inyecta directamente, sin modificar su implementación ni sus tools.
`tests/test_runtime.py` usa el nodo de instalaciones y el grafo documental reales,
con la dependencia externa de instalaciones y la entrada RAG de `REGISTRY`
sustituidas por dobles. Verifica construcción sin consultas, conservación
de resultados/fuentes/metadatos, fallback histórico, error/abstención y ciclo HITL.
La aceptación con catálogo/avisos reales y RAG operativo es una comprobación
distinta y sigue pendiente. Los resultados y el estado Git registrados más abajo
corresponden a la entrega histórica original y no se reinterpretan como validación
de esta conexión. No se presenta el MVP como terminado.

`tests/test_import_boundaries.py` verifica en procesos nuevos la construcción
por reglas y con Ollama, bloqueando red e importaciones RAG/Chroma, sin sustituir
la tool documental. La puerta documental se resuelve al ejecutar la consulta.
Las pruebas de ciclo de vida sustituyen las dependencias externas.

Comando exacto de la selección inicial de **444 pruebas** (antes de añadir la
prueba de frontera de esta revisión):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp="$env:TEMP/agentes-backend-conexion" tests/test_runtime.py tests/test_supervisor.py tests/test_agent_service.py tests/test_sync_integration.py tests/test_documental_adapter.py tests/test_node_guards.py tests/test_sintetizar_aplicar.py tests/test_infra_sintetizar_aplicar.py tests/test_backend_cierre.py tests/test_graph_hitl.py tests/test_import_boundaries.py tests/test_demo.py tests/test_cli.py tests/test_cli_security.py tests/test_clientes_seguridad.py tests/test_nodo_instalaciones.py
```

### Proveedor de rutas del supervisor (25/10/2026)

La #20 está integrada en `origin/develop` (`b3ea868`). La rama de #22 incorpora
ese destino mediante merge normal, incluidas las mejoras de clientes de #19.
No incorpora la rama de #21 (`a84e899` al revisar).

`agentes/supervisor_llm.py::crear_proveedor_rutas` recibe un adaptador con la
interfaz `generate` existente y una `message_factory` compatible con `LlmMessage`.
Los tipos de `agentes.llm` solo se importan bajo `TYPE_CHECKING`, sin duplicar su
cliente SDK/HTTP. Produce mensajes system/user con
pedido acotado a 2000 caracteres, rutas permitidas, estados de los resultados y
situación de respuesta/plan; excluye evidencias, datos internos y traza. Solicita
solo JSON `{"ruta": "instalaciones", "motivo": "Consultar catálogo."}` y devuelve
`SupervisorDecision`. No exige visitar todos los especialistas. Rechaza formatos
inválidos y llamadas a tools; el supervisor existente conserva allowlist,
protección de roles ya consultados, fallback, límite e HITL.

Configuración consumida: argumentos explícitos `temperature=0`,
`max_output_tokens=256`, `timeout=30` (segundos), validados al construir. No lee
`.env` ni cambia `GEN_*`, embeddings, TAG o generación del RAG. Ejecuta una sola
llamada a `generate` por propuesta con `tools=[]`, sin reintentos propios ni logs
de prompts/respuestas. Transmitir timeout no prueba que el transporte lo cumpla.

**Implementación y montaje configurado probados con dobles; aceptación con modelo
real pendiente.** El recorrido ahora es:

```python
servicio = crear_servicio(modo="real")
# runtime → crear_proveedor_configurado → crear_proveedor_supervisor_real
# → crear_proveedor_rutas → AgentService → build_graph → supervisor_node
```

CLI y Streamlit mantienen esa llamada. Runtime carga el `.env` de su repositorio
con `override=False` antes de importar adaptadores y sus constantes. No modifica
`GEN_*` ni recarga módulos previos: otros consumidores de constantes siguen
siendo responsables de cargar el entorno antes de importarlas.

| Variable consumida | Valores y comportamiento |
| --- | --- |
| SUPERVISOR_MODE | `reglas` por defecto, o `llm`; otro valor falla |
| SUPERVISOR_PROVIDER | En LLM, obligatorio: `google` u `ollama` |
| SUPERVISOR_MODEL | En LLM, obligatorio; sin nombre predeterminado ni disponibilidad verificada |
| SUPERVISOR_TEMPERATURE | 0–2, finito; defecto 0 |
| SUPERVISOR_MAX_OUTPUT_TOKENS | Entero 1–4096; defecto 256 |
| SUPERVISOR_TIMEOUT | Entero 1–240 segundos por petición; defecto 30 |
| GOOGLE_API_KEY | Obligatoria para Google; credencial del adaptador existente |
| OLLAMA_BASE_URL | Consumida por Ollama; defecto `http://127.0.0.1:11434` |

Las opciones LLM se validan en modo `llm`; reglas no exige modelo ni credenciales.
Configuración inválida: error al construir, sin demo silenciosa. No se escribe
el `.env` local. La inyección manual `crear_servicio_real(route_provider=proveedor)`
prevalece sobre la selección del entorno. Inferencia inválida o excepción:
fallback determinista y traza acotada, sin texto de la excepción. Se mantienen
allowlist, límites, ambos especialistas y HITL.

Construir no ejecuta inferencia/tools/HTTP ni importa RAG/Chroma. El único cambio
del montaje documental difiere su puerta pública hasta el uso, sin cambiar
contratos, estado, topología ni implementación del nodo. Google recibe `tools=[]`,
instrucciones de sistema y timeout HTTP en milisegundos. La prueba con SDK y
transporte HTTP doble verifica el timeout recibido por HTTPX para conexión,
lectura, escritura y pool; no mide latencia real. Ollama conserva tres intentos y
sus esperas: el timeout no es un plazo total del turno.

**Solapamientos con #21:** conservar la carga diferida y `TOOL_REGISTRY` de
`llm.py`; la importación directa de `agentes.tools.rag` en #21 reintroduciría la
carga del RAG al importar adaptadores. Conservar sus mejoras válidas del prompt
`INSTRUCCIONES_TOOLS` y `GEN_MAX_TOKENS`, junto con su configuración y consumidor.
#21 no modifica `llm_google.py` en el diff revisado; preservar allí `tools=[]`,
instrucciones de sistema y timeout HTTP de #22. Revisar de nuevo si cambia su HEAD.
No se copian cambios de nodo documental, OCR, visión, embeddings ni evaluación.

Validación de esta revisión: **514 pruebas offline superadas**, una advertencia
de deprecación del SDK Google, y `git diff --check`. Selección ejecutada:

```powershell
python -B -m pytest -q -p no:cacheprovider tests/test_llm_supervisor_real.py tests/test_runtime.py tests/test_supervisor_llm.py tests/test_supervisor.py tests/test_agent_service.py tests/test_sync_integration.py tests/test_documental_adapter.py tests/test_node_guards.py tests/test_sintetizar_aplicar.py tests/test_infra_sintetizar_aplicar.py tests/test_backend_cierre.py tests/test_graph_hitl.py tests/test_import_boundaries.py tests/test_demo.py tests/test_cli.py tests/test_cli_security.py tests/test_clientes_seguridad.py tests/test_nodo_instalaciones.py
```

Pendientes: aceptación de rutas con un modelo real disponible y aceptación
conjunta con índice RAG compatible e instalaciones reales. No se declara
terminado el MVP ni el RAG. No se ejecutó la suite completa ni se consultaron
APIs, modelos o índice durante esta tarea.


## Qué se conecta

`agentes/runtime.py::crear_servicio_real()` pasa al adaptador un callable que
resuelve la puerta pública `obtener_grafo_documental().invoke` al ejecutar la consulta.
El nodo adaptado se inyecta en `AgentService`, junto a las implementaciones
existentes `sintetizar` y `aplicar`. Pasar el método no ejecuta una consulta.

El adaptador conserva respuesta, fuentes, errores, abstención, limitaciones,
eventos y correlación en `specialist_results`. Su lógica ya existía: solo se
actualiza su explicación para indicar el montaje real.

`AgentService`, `graph.py` y el supervisor ya admitían la inyección. Se utiliza
su topología existente: supervisor → documental → supervisor → instalaciones
→ supervisor → sintetizar → supervisor → FINISH → pausa antes de aplicar.
La aprobación sigue en `resolver_plan`, con `update_state` e `invoke(None)`.
Las guardias y eventos HITL se aplican una sola vez en el grafo principal.

`agentes.nodes.instalaciones.nodo_instalaciones` recibe el estado compartido,
devuelve solo resultados por rol y eventos nuevos, y conserva el documental.
Sustituye la declaración de ausencia anterior en runtime. No se certifica aquí
la integración HTTP real ni se implementa la auxiliar determinista de Miguel.

`crear_servicio(modo='real'|'demo')` selecciona explícitamente el montaje.
Un fallo real no activa la demo. Construir el componente puede importar sus
dependencias actuales; no se promete carga diferida del pipeline del especialista.

## Archivos que pertenecen a esta integración

- `agentes/runtime.py`: montaje documental e inyección del nodo público de instalaciones.
- `agentes/documental_adapter.py`: actualización de su docstring, sin cambios lógicos.
- `tests/test_runtime.py`: pruebas del montaje con tool RAG y dependencia externa de instalaciones dobles explícitas.
- `scripts/smoke_real.py`: diagnóstico manual acotado, con preflight de índice.
- Documentación de integración, handoff, evidencia y borrador de PR.

Los archivos internos `agentes/nodes/`, `agentes/tools/rag.py`, `rag/`,
`requirements.txt` y las pruebas originales de los especialistas coinciden con
`e36b563`. También se mantienen intactos `app.py`, `main.py` y `clientes/`.
Se retiraron del diff las correcciones internas y sus regresiones añadidas.

Los problemas de presupuesto cero, constructor HuggingFace, monkeypatch sobre
REGISTRY y acceso a Chroma durante colección siguen pendientes de sus responsables.
No se corrigen ni se eliminan sus pruebas para presentar una suite completa verde.

## Uso y verificación

Se conserva el entorno local preparado con Python 3.14.2. No se modifican las
dependencias declaradas para esta conexión ni el Python global.

```python
from agentes.runtime import crear_servicio_real

servicio = crear_servicio_real()
hilo = servicio.nueva_conversacion()
estado = servicio.procesar_turno("Consulta sintética sobre un abono municipal", hilo)
# Cuando exista una decisión humana, resolver_plan(hilo, decision_bool,
# plan_id=estado['plan_id']) conserva el ciclo HITL del supervisor.
```

Pruebas del backend y montaje, excluyendo expresamente las tres suites de
especialistas que abren almacenamiento o mantienen fallos ajenos a esta PR:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-supervisor tests --ignore=tests/test_node_documental.py --ignore=tests/test_tool_rag.py --ignore=tests/test_tools.py
.\.venv\Scripts\python.exe -m scripts.smoke_real
```

Las pruebas del montaje utilizan el grafo documental, supervisor, adaptador,
síntesis y aplicar reales, sustituyendo exclusivamente la tool RAG con un doble.
Comprueban rutas, conservación del sobre, fuentes y errores, pausa, aprobación,
rechazo, nuevo pedido, plan antiguo, idempotencia, traza e hilos aislados.
No acreditan recuperación ni generación reales.

El diagnóstico manual comprueba la presencia de `chroma.sqlite3` antes de
invocar el especialista: la implementación original puede crear almacenamiento
al consultar. Si falta el índice, informa `rag_executed=False` y no llama al RAG.
Ese preflight es del diagnóstico de integración y no cambia el especialista.
Si hay índice, usa su configuración vigente y un máximo de cuatro consultas
sintéticas, sin ingestas, cambios de proveedor ni sustituciones por dobles.

Falta el índice configurado `output/chroma_db/chroma.sqlite3`. La recuperación
y generación reales siguen bloqueadas. La evidencia anterior obtenida con
correcciones internas se retira de la PR; no valida esta versión final.
Resultado de esta versión: **299 pruebas del backend y montaje superadas**, con
tres avisos de deprecación de dependencias. Las tres suites de especialistas
se excluyen explícitamente del comando anterior; no se afirma que pase la suite
completa. Sus archivos y aserciones se han restaurado sin cambios.
El [diagnóstico actual](evidencia_conexion_supervisor.json) confirma índice
ausente, `rag_executed=False` y ninguna llamada al pipeline. Esa ejecución es
un preflight bloqueado y no una prueba de recuperación real.

## Git y entrega

El fetch solicitado confirmó `origin/develop=6e60890`, ya incluido en la rama
inicial `feature/supervisor-grafo=e36b563`, con siete commits propios. Develop
local ya coincidía con su remoto. La PR #5 seguía abierta y sin integrar.
La rama documental ya estaba integrada; las ramas de instalaciones y Streamlit
seguían separadas. No se repiten merges ni se modifican ramas de compañeros.

La rama local `integration/especialistas-reales` conserva el historial y añade
commits que retiran del diff los cambios fuera de alcance, sin reescribirlo.
Para revisión, comparar el resultado final con `e36b563`; los commits iniciales
contenían trabajo posteriormente retirado. No hay push ni actualización de PR.

Los cambios previos de README, dataset golden, documentos locales y
`output/debug_trace.diff` permanecen fuera de nuestros commits. Las pruebas
incluyen el golden local existente, sin atribuir su creación a esta entrega.

El [borrador de PR](pr_integracion_real.md) describe solo el resultado final.
