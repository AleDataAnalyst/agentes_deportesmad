# Compatibilidad Streamlit y backend en c9a3d45

Revisión local del 19/10/2026, rama `integration/pruebas-streamlit`, HEAD
`c9a3d45`. El historial local contiene el merge de la PR #6 de Streamlit.
No se consulta ni actualiza la PR remota.

No se encontraron archivos `AGENTS.md` en el árbol del repositorio ni en sus directorios ascendientes. Se respetan los límites expresados por Alejandra:
montaje y adaptación de contratos; David mantiene clientes, Héctor documental/RAG y Miguel instalaciones. No se han editado sus módulos, dependencias ni pruebas originales. Tampoco se modifica el backend para compensar defectos del cliente.

## Resultado

El contrato consumido por el cliente coincide con `AgentService`. No se encontró un defecto en `agentes/runtime.py`, `agentes/agent.py` o en la adaptación documental que justifique una corrección para este cliente.

La pantalla sigue construyendo `crear_servicio_demo()` directamente. El cambio a la factoría de runtime corresponde a David y no requiere un nuevo adaptador de salida ni cambiar firmas del servicio. El modo real continúa bloqueado para una
consulta documental verificable por ausencia del índice configurado.

Hay dos defectos reproducidos en la UI: no refresca la vista tras resolver un plan y no captura los errores de inicialización/resolución. Se detallan abajo.

## Operaciones y campos

| Uso del cliente | Contrato del backend | Resultado |
|---|---|---|
| `_init_session`: crear servicio una vez | Cada instancia de `AgentService` conserva grafo, checkpoints y registros de planes | Compatible; falta usar runtime en vez de importar la demo |
| `nueva_conversacion()` | Devuelve `thread_id: str` nuevo | Compatible; no borra los checkpoints anteriores |
| `procesar_turno(prompt, thread_id)` | Devuelve estado hasta pausa; valida mensaje y trabajo pendiente | Compatible |
| `resolver_plan(thread_id, aprobado=True/False, plan_id=...)` | Bool real y plan vigente; reanuda el mismo hilo | Compatible en ambas decisiones |
| `consultar_estado(thread_id)` | Copia del checkpoint sin ejecutar nodos | Disponible; el cliente actual no la llama |
| `final_answer` | `str` en estado principal | Compatible con `st.markdown` e historial |
| `plan` | `list[str]` | Compatible con `render_hitl` |
| `pendiente_hitl` | `bool` derivado de `snapshot.next` | Compatible; es el campo correcto para bloquear chat y mostrar botones |
| `plan_id` | `str` cuando hay plan vigente; `None` antes del primer plan | Compatible: se usa dentro de la condición de pausa |
| `approved` | `None` pendiente, `True` o `False` tras resolver | Backend correcto; la UI no lo presenta de forma específica |
| `done` | `False` pendiente o tras rechazar; `True` tras aprobar | Debug puede leerlo; no sustituye a `pendiente_hitl` |
| `iterations`, `debug_trace` | `int`, `list[str]` | Compatible; traza acumulada por conversación |
| `specialist_results` | `dict[str, ToolResult]`; valores dataclass, no dict JSON | Se imprime sin fallo, pero mediante repr completa, sin presentación estructurada |

No existe un `ClientResult` importado ni exigido por `render_hitl`; su docstring no representa un tipo implementado. No hay campo raíz `fuentes`, `respuesta`,
`request_id` ni `modo` en `AgentState`, y la UI actual tampoco los exige.

Para ampliar presentación, usar los datos existentes:

```python
for rol, resultado in estado.get("specialist_results", {}).items():
    status = resultado.status
    fuentes = [e.source for e in resultado.evidence]
    limitaciones = resultado.data.get("limitaciones", [])
    # Solo el resultado documental actual conserva estas claves:
    request_id = resultado.data.get("request_id")
    eventos = resultado.data.get("eventos", [])
```

Esto es una pauta de consumo, no código añadido al cliente. `Evidence.content`puede estar vacío: el adaptador conserva fuentes sin inventar fragmentos. Las fuentes y limitaciones también aparecen en el texto de la síntesis real actual.
No se necesita aplanar dataclasses en el backend para poder mostrarlas.

## Servicio, sesión y ciclo HITL

Comprobado con AppTest headless sobre `app.py`, ejecutando los módulos reales de clientes, más verificaciones del servicio:

- `service` se crea solo si no existe en `st.session_state`; se conserva entre reruns. No usa caché global de servicios personales.
- `thread_id` se conserva durante el pedido y su resolución. Sesiones AppTest diferentes reciben servicios distintos.
- Tras enviar: plan no vacío, `plan_id` de texto, `pendiente_hitl=True`, `approved=None`, `done=False`. No aparece `chat_input`; sí ambos botones.
- Aprobar y rechazar llaman al servicio con el mismo hilo y plan, y booleanos reales. El backend queda sin pausa. Aprobar da `done=True`; rechazar da `done=False` y limpia propuesta/resultados. Ambos recorridos terminan.
- Repetir la misma decisión sobre el mismo plan devuelve el estado sin ejecutar otra vez aplicar. Un pedido siguiente tiene otro `plan_id`; el anterior se rechaza con `PLAN_NOT_CURRENT`.
- Nueva conversación conserva el servicio, cambia el hilo, vacía mensajes y pone `estado=None`. El nuevo hilo no recibe resultados del anterior.
  Si se abandona un plan pendiente con este botón, el checkpoint anterior permanece: no es una cancelación ni eliminación. No es un defecto del montaje.
- Historial visible de Streamlit no se incorpora automáticamente como memoria de contenido al backend. Checkpoint/traza y registros viven en el proceso.

### Hallazgo 1: vista obsoleta después de aprobar o rechazar

Prioridad: bloquea la continuación normal del chat. Responsable: **David**.

Ubicación: `clientes/streamlit_app.py:32`, callbacks en líneas 50 y 61, condición del chat en línea 82 y debug en línea 112; ejecución de los botones en `clientes/hitl.py:24` y `:27`.

`estado` se lee antes de dibujar el sidebar. Los callbacks actualizan `st.session_state.estado`, pero no la variable local ni solicitan rerun.
`render_hitl` los ejecuta dentro del `if st.button(...)`, no como callbacks `on_click` previos a la ejecución del script.

Observación inmediatamente después de cada clic:

```text
session_state.estado.pendiente_hitl = False
servicio.consultar_estado(hilo).pendiente_hitl = False
UI: siguen visibles Aprobar/Rechazar
UI: chat_input ausente
UI debug: pendiente_hitl=True
```

Después de un rerun adicional aparecen el chat y el debug correcto. Se reproduce tanto con la demo creada por runtime como con el montaje real usando una puerta documental doble explícita. No indica que el backend siga pausado.

Cambio solicitado a David: tras una resolución exitosa, actualizar estado e historial y forzar un rerun antes de continuar el render, o reorganizar los callbacks para que se ejecuten antes de leer el estado. Verificar ambas decisiones sin necesitar un segundo evento del usuario.

### Hallazgo 2: excepciones sin tratamiento en inicialización y HITL

Responsable: **David**. Ubicación: `clientes/streamlit_app.py:29`, `:51` y `:62`.

El `try/except` de líneas 89-106 solo cubre el envío. La inicialización del servicio y los callbacks de resolución quedan fuera. Se indujeron dos errores:

- `ValueError("PLAN_NOT_CURRENT: inducido en sonda")` al resolver: AppTest   registra excepción no capturada, sin elemento `st.error`.
- `RuntimeError("INIT_REAL: error inducido")` al crear: excepción no capturada antes de mostrar la interfaz.

Son fallos inducidos para comprobar tratamiento de errores, no afirmaciones de que esas excepciones ocurran en toda consulta real. `AgentService` propaga los errores de validación/integración intencionadamente.

Cambio solicitado a David: capturar inicialización y resolución, presentar el error y una acción coherente (reintentar inicialización, consultar estado o nueva
conversación según el caso), y no anunciar aprobación/rechazo si falló. No convertir el error en datos ficticios ni seleccionar demo automáticamente.

### Presentación pendiente, sin incompatibilidad de tipos

Responsable: **David**, con datos de cada componente conservados por sus responsables.

- `debug.py:29` representa la dataclass completa. No extrae de forma controlada fuentes, `request_id` documental, eventos de tools, fechas o advertencias.
  Recorre toda la traza acumulada sin acotarla.
- `plan_id` y `approved` no tienen presentación específica en debug.
- No hay selector/etiqueta propia del modo en la UI. La demo se identifica en su contenido, pero al usar runtime conviene mostrar el modo elegido sin dar por validados RAG o instalaciones porque se llame `real`.
- No hay carga de imagen en el cliente inspeccionado y `procesar_turno` no transporta adjuntos. No corresponde añadir un argumento de imagen solo desde la UI; requiere acuerdo transversal fuera de esta revisión.

## Handoff a David: consumir la factoría de runtime

Cambio mínimo en su módulo, pendiente de que David lo implemente:

```python
from agentes.runtime import crear_servicio

# Dentro de _init_session y conservando el guard actual:
if "service" not in st.session_state:
    st.session_state.service = crear_servicio(modo=modo_elegido)
```

`modo_elegido` debe proceder de una selección/configuración explícita y ser `"demo"` o `"real"`. `crear_servicio()` sin argumentos selecciona real. La firma actual acepta solo el keyword `modo`; no exige un tipo nuevo ni callbacks.
Conservar `nueva_conversacion`, `procesar_turno`, `resolver_plan` y sus argumentos tal como ya se llaman. El backend no necesita cambios para este consumo.

Para hacerlo verificable:

1. Empezar con `crear_servicio(modo="demo")`, mantener el servicio una vez por sesión y corregir refresco/errores de UI.
2. Mostrar el modo explícito. Si se permite cambiarlo durante una sesión, sustituir servicio y crear hilo nuevo, limpiar estado/historial y no reutilizar un `plan_id` de otra instancia. Acordar qué hacer con un plan pendiente antes de cambiar. No recrear el servicio por cada rerun.
3. Al sustituir la llamada en código, la sesión ya abierta puede seguir teniendo el servicio demo guardado: reiniciar esa sesión o hacer migración explícita. «Nueva conversación» por sí sola conserva el servicio y no cambia su modo.
4. Capturar fallos de construcción. No afirmar que el servicio está listo ni avanzar a chat sin haberlo creado; no activar la demo por fallo real.
5. Tras cada decisión exitosa, un único clic debe actualizar controles, chat, respuesta y debug. Los errores deben poder verse sin traceback no tratado.
6. Añadir pruebas de cliente bajo su responsabilidad: reruns, sesiones aisladas, ambas decisiones, error de resolución, error de creación, plan obsoleto y nuevo hilo. `tests/test_clients.py` sigue siendo solo un docstring; esta revisión no lo modifica.
7. Usar `real` para la validación externa solo después de cerrar el requisito del índice con Héctor; mantener visible la limitación de instalaciones.

## Bloqueos del modo real y responsables

Revisión de solo lectura: import de `rag.config` y comprobación de existencia, sin abrir colección Chroma, ejecutar pipeline, consultar modelos, crear índice,
modificar `.env` ni cambiar proveedores.

```text
CHROMA_DIR = ./output/chroma_db
COLLECTION_NAME = deporte_municipal
chroma.sqlite3 presente = False
EMBED_PROVIDER = ollama
GEN_PROVIDER = ollama
RAG ejecutado = False
```

- **Héctor:** aportar/señalar procedimiento reproducible, corpus/índice, colección, embeddings/modelo/dimensión y configuración coherentes. La existencia del archivo por sí sola tampoco probaría contenido, dimensiones o generación.
- **Alejandra:** verificar la puerta pública y el mapeo con esa entrega; no alterar proveedores para esconder el bloqueo.
- **Miguel:** entregar callable público de instalaciones y contrato. Runtime sigue declarando `abstained`, `available=False` y limitación explícita; no hay consulta de catálogo/avisos en este montaje.
- **David:** usar modo explícito y presentar errores/limitaciones reales.

El constructor real puede importar dependencias RAG, pero no envía una consulta.
La comprobación del índice de `scripts/smoke_real.py` es de ese diagnóstico, no una guardia automática de `crear_servicio_real`. Cambiar la UI a runtime no
resuelve el índice ni convierte el modo real en un preflight de disponibilidad.
No se ejecutó `smoke_real` porque, si hubiera un índice, podría consultar el RAG.

## Pruebas y alcance de la evidencia

Selección existente repetida:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  --basetemp=tmp/pytest-revision-streamlit-c9a3d45 `
  tests/test_agent_service.py tests/test_runtime.py `
  tests/test_documental_adapter.py tests/test_sync_integration.py `
  tests/test_graph_hitl.py tests/test_sintetizar_aplicar.py `
  tests/test_import_boundaries.py
```

Resultado: **116 passed, 3 warnings, 10.57 s**. Los tres avisos son de deprecación de dependencias. No se ejecuta la colección completa de tests RAG.
Los tests de runtime usan grafo documental real con tool RAG doble.

Sonda nueva local, sin editar código de producto:

```powershell
.\.venv\Scripts\python.exe tmp/revision_streamlit_c9a3d45/sonda_compatibilidad.py
```

Resultado: salida 0, aserciones completadas. Usa Streamlit AppTest 1.66.0 sobre
`app.py`; es ejecución headless, no inspección manual en un navegador. Hace:

- Aprobación/rechazo con demo de runtime inyectada solo en el proceso de sonda.
- Aprobación/rechazo con montaje real y puerta documental doble, que evita importar/ejecutar el documental y el RAG originales; cuatro llamadas a ese doble.
- Segundo pedido, idempotencia, plan antiguo, reruns y nueva conversación.
- Dos errores inducidos para reproducir la falta de tratamiento en la UI.

Las sustituciones de factoría no son un cambio entregado a Streamlit. El cliente versionado sigue importando la demo directamente. Los tracebacks de los dos casos de error son resultados esperados de la sonda, no fallos de sus aserciones. Resultado detallado en `tmp/revision_streamlit_c9a3d45/resultado.json`.

AppTest también emite advertencias sobre tipos internos no registrados para deserialización msgpack de checkpoints. Con la configuración actual no impiden estos recorridos; no se modifica el serializador ni dependencias. No se usa esta
observación como prueba de recuperación duradera o de compatibilidad futura.

**No se ha realizado ninguna consulta real al RAG ni HTTP de instalaciones.**

## Cambios de esta revisión

- Nuevo documento de revisión/handoff (este archivo).
- Nueva sonda y resultado solo en un subdirectorio nuevo de `tmp/`.
- Sin correcciones de backend: no se ha identificado un defecto suyo en este contrato. Sin nuevos tests de regresión de producto para congelar el fallo de UI; David debe probar el comportamiento corregido al cambiar su cliente.
- Cambios previos y archivos protegidos conservados; se comparan sus huellas antes/después. No se hace staging, commit, push, merge ni actualización de PR.
