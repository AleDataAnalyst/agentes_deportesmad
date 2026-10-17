# Síntesis determinista y resolución del plan informativo

Fecha: 17/10/2026. Rama: `feature/supervisor-grafo`. Continuación de las
[guardias existentes](infra_sintetizar_aplicar.md), cuyas firmas se conservan.

## Implementaciones y contrato

`agentes.nodes.sintetizar.sintetizar(state)` recibe `user_message` y los
`ToolResult` del pedido vigente en `specialist_results`. Devuelve únicamente
`final_answer`, `plan`, `done=False`, `approved=None` y un evento nuevo de
`debug_trace`. No modifica el estado, sus resultados ni sus evidencias.

Presenta cada especialista por separado, sin resolver automáticamente posibles
contradicciones. Distingue dos resultados útiles, respuesta parcial, ningún
resultado útil y rol todavía sin resultado. Un `error`, una abstención o texto
vacío no cuentan como respuesta útil. Si el sobre declara errores o abstención
aunque su estado diga `ok`, conserva la restricción. El texto disponible de un
fallo o abstención se etiqueta como contenido declarado no confirmado.

Muestra las referencias y solo los fragmentos realmente aportados. Las fuentes
sin fragmento no reciben texto, score o fechas inventados. Conserva el sobre
estructurado en los resultados existentes y presenta las claves conocidas de
advertencias, errores, limitaciones, origen y fechas tanto en `data` como en
metadatos de evidencia. Una marca `fallback` o `origen="fallback"` se identifica
explícitamente como histórica y no acredita condiciones actuales. Una fecha de
captura parcial se reproduce tal cual. Sin fuentes, señala fundamento no
verificado. Las claves adicionales y eventos siguen disponibles en el resultado
original; no se exponen argumentos internos de tools en el texto del usuario.

La síntesis es determinista: no añade modelos, proveedores, HTTP ni ejecución
de especialistas. Produce un plan informativo de revisión y, si faltan datos,
propone aportar el documento o identificar centro/dato y reformular la consulta.
`plan_is_ready` exige respuesta y lista no vacía de textos no vacíos; no exige
un número fijo de pasos. No se encontró una regla numérica contradictoria en
los contratos/especificación revisados; no se cambia la guardia. La ampliación
posterior consiste en inyectar otra implementación con la misma firma, sujeta
a `sintetizar_node(state, node=...)`.

`agentes.nodes.aplicar.aplicar(state)` exige `approved` de tipo `bool` real y
respuesta/plan válidos, también al usarlo sin wrapper. Al aprobar devuelve
`done=True`, limpia `pending_action` y conserva la respuesta con un cierre
informativo. Al rechazar devuelve `done=False`, limpia `plan`,
`specialist_results` y `pending_action`, y sustituye la propuesta por un mensaje
de rechazo que permite un nuevo pedido. No muta la entrada. Conserva la decisión
humana hasta el reinicio del siguiente pedido; no devuelve `approved`.

No ejecuta reservas, pagos ni envíos. Tampoco genera `plan_id` ni implementa
idempotencia. Esas responsabilidades permanecen en `AgentService`. La función
concreta no añade eventos: la guardia `aplicar_node(state, node=...)` añade una
sola marca HITL al pasar por el grafo.

## Montaje sin modificar grafo, servicio ni clientes

```python
from agentes.agent import AgentService
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.sintetizar import sintetizar
from agentes.nodes.aplicar import aplicar

def montar_servicio(ejecutar_documental, instalaciones_node):
    return AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=ejecutar_documental),
        instalaciones_node=instalaciones_node,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar,
    )
```

Se inyectan las implementaciones `sintetizar` y `aplicar`, no las guardias
`sintetizar_node` y `aplicar_node`: `build_graph` ya las aplica. No se necesita
otro constructor de servicio ni otro supervisor, síntesis o HITL documental.
La demo anterior se mantiene explícitamente simulada y no se monta como fallback.

`ejecutar_documental` es un callable obligatorio del contrato documental; las
pruebas inyectan un doble. El adaptador conserva la traducción provisional, sin
`.invoke`, factorías de grafos ni importaciones automáticas del especialista.
`nodo_documental` y su interfaz pública permanecen intactos. La llamada directa
real queda pendiente de coordinación con Héctor: su módulo propone
`obtener_grafo_documental()` como puerta pública. Ver la
[comparación de composición y consumidores](integracion_grafo_documental.md).

David conserva servicio e hilo entre reruns, presenta `final_answer` y `plan`,
y utiliza `resolver_plan(thread_id, aprobado, plan_id=...)`. El grafo mantiene
la pausa antes de aplicar, el checkpointer y la reanudación en el mismo hilo.

## Verificación y límites

```powershell
python -m pytest -q tests/test_sintetizar_aplicar.py tests/test_documental_adapter.py tests/test_infra_sintetizar_aplicar.py tests/test_import_boundaries.py tests/test_sync_integration.py tests/test_agent_service.py tests/test_state.py tests/test_supervisor.py tests/test_demo.py tests/test_contracts.py tests/test_async.py tests/test_graph_hitl.py tests/test_clients.py
```

Resultado: **266 pruebas superadas** con Python del sistema. Se cubren nodos
reales y recorrido por LangGraph/AgentService con especialistas dobles: fuentes,
advertencias, errores, abstenciones, históricos, ausencia de datos, no mutación,
pausa/reanudación, aprobación y rechazo, nuevo pedido, idempotencia, plan antiguo,
traza sin duplicación y aislamiento de conversaciones. La puerta documental
antigua también se compila con un nodo doble como prueba independiente.

No se ejecutaron la suite completa ni las pruebas reales de RAG/HTTP. No se
instalaron dependencias ni prepararon índices. Se conserva sin cambios el
[diagnóstico previo del RAG](revision_entorno_rag.md); no se han reparado sus
fallos internos ni debilitado sus pruebas. La compatibilidad del adaptador no
acredita retrieval, calidad, contexto permitido, vigencia ni disponibilidad.

Pendiente con Héctor: puerta de integración real, dependencias y pruebas RAG,
presupuesto/contexto y ejemplos reales. Con Miguel: resultados reales y
procedencia/fallback del especialista de instalaciones. Con David: montaje y
verificación conjunta de la UI. La síntesis actual combina texto y restricciones
de forma explícita; no verifica la verdad de respuestas marcadas `ok` ni detecta
contradicciones semánticas entre especialistas.

## Entrega local

Cambios propios de esta continuación: implementaciones en los dos módulos de
nodos, adaptación del ejecutor documental y sus pruebas, nuevas pruebas de nodos
y recorrido, y documentación. No se tocan `graph.py`, `agent.py`, clientes,
`nodo_documental`, el grafo documental ni los archivos del diagnóstico previo.
Se actualiza el [flujo ASCII explicativo](flujo_supervisor_grafo.md) para señalar
las implementaciones disponibles. El dibujo generado `grafo_actual.txt` se
regeneró y no presenta cambios: la topología sigue siendo la misma.

Título propuesto de PR de borrador hacia `develop`:
`Implementar síntesis determinista y cierre informativo con especialistas inyectados`.

Descripción preparada para una PR existente o futura:

> Implementa síntesis informativa que conserva procedencia y restricciones y
> aplicar que resuelve la aprobación/rechazo sin acciones externas. La traducción
> documental provisional recibe un callable explícito, manteniendo intactos ambos
> grafos y la API de clientes. Verificación: 266 pruebas sin RAG/HTTP reales.
> Pendiente: coordinar con Héctor la puerta del nodo y validar los especialistas
> reales. No se acredita la integración de RAG ni la UI.

No se ha consultado ni creado una PR remota. Comandos de entrega selectiva,
sin incluir `coordinacion_fase_integracion.md`, `revision_entorno_rag.md` ni
`output/debug_trace.diff`, que eran trabajo previo:

```powershell
git add -- agentes/nodes/sintetizar.py agentes/nodes/aplicar.py agentes/documental_adapter.py
git add -- tests/test_sintetizar_aplicar.py tests/test_documental_adapter.py
git add -- docs/specs/sintetizar_aplicar.md docs/specs/integracion_grafo_documental.md docs/specs/infra_sintetizar_aplicar.md
git add -- docs/specs/flujo_supervisor_grafo.md
git diff --cached --check
git diff --cached --stat
git commit -m "Implementar síntesis y cierre informativos con ejecutor documental inyectable"
git push -u origin feature/supervisor-grafo
```

Estos comandos no se han ejecutado. Revisar el stage antes de confirmar; no se
publican cambios automáticamente. El texto de coordinación para Slack queda
en el documento de integración para envío manual.
