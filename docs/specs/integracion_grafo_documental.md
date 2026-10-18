# Convivencia del componente documental y el grafo principal

> Actualización 18/10/2026: el montaje real ya está implementado en
> `agentes/runtime.py`, mediante `obtener_grafo_documental().invoke` y el
> adaptador existente. Ver [montaje y verificación actuales](integracion_real.md).
> El resto de este documento conserva la revisión histórica del 17/10;
> sus referencias a conexión pendiente describen aquel estado anterior.

Revisión local: 17/10/2026, rama `feature/supervisor-grafo`.

Estado: traducción provisional con callable inyectable obligatorio, sin montaje
automático. No se exige invocar el subgrafo documental. La llamada directa al
nodo real sigue pendiente de coordinación con Héctor.

## Interfaces y responsabilidades

`agentes/grafo_documental.py` es un componente del especialista de Héctor.
Su topología es entrada → documental → fin. No sustituye a
`agentes/graph.py`: este último conserva supervisor, router, especialistas,
síntesis, FINISH y pausa `interrupt_before=["aplicar"]`. Ambos pueden ser
grafos compilados porque sus estados y ciclos de vida son distintos.

| Aspecto | Componente documental | Grafo principal |
|---|---|---|
| Puerta pública | `obtener_grafo_documental().invoke(entrada)` | `build_graph(...)`; clientes mediante `AgentService` |
| Entrada | `EstadoDocumental`: `request_id`, `pedido` y opciones documentales | `AgentState`: `user_message`, resultados y estado de orquestación |
| Salida | Estado del componente con `documental`; no es necesariamente solo el patch del nodo | Estado del pedido; cada nodo inyectado devuelve un patch |
| Resultado | `resultado`, `fuentes`, `abstained`, `errores`, `limitaciones`, `eventos` | `specialist_results[rol]: ToolResult` |
| Memoria | Instancia compilada reutilizada; sin checkpointer explícito | Checkpointer y `configurable.thread_id` |
| Aprobación | No tiene | `AgentService.resolver_plan`, `update_state` e `invoke(None)` |

Con la firma actual, inyectar `nodo_documental` sin traducción no funciona:
recibe `pedido` y devuelve `documental`, mientras el principal usa `user_message`
y `specialist_results`. Esa incompatibilidad no obliga a utilizar un subgrafo.
El adaptador recibe `ejecutar_documental(entrada) -> patch` y extrae únicamente
su sobre `documental`, sin reenviar el estado completo ni el checkpoint padre.
No importa ni ejecuta automáticamente el nodo real o su grafo.

## Comparación con la adaptación directa del nodo

La implementación inspeccionada del grafo documental solo registra
`nodo_documental` y termina. Aporta ejecución de LangGraph, selección de campos
del esquema y reutilización de la instancia compilada; no añade lógica de
dominio, rutas, recuperación, checkpoint propio ni aprobación. El bucle acotado
de tools ya está dentro de `nodo_documental`. Invocar ese subgrafo desde el
principal no es necesario para conservar el comportamiento del especialista.
El esquema `TypedDict` tampoco equivale a validación semántica en ejecución.

| Opción | Efecto | Coste y compatibilidad |
|---|---|---|
| Principal → adaptador → grafo documental → nodo | Respeta la puerta actual; una sola implementación del especialista | Alternativa anterior; añade ejecución de LangGraph sin lógica de dominio adicional |
| Principal → traducción → callable documental | Ejecuta la misma lógica sin exigir el subgrafo intermedio | Opción implementada con callable obligatorio; conserva ambos contratos y deja pendiente coordinar el acceso directo real |
| Principal → nodo con contrato común nativo | El nodo recibe `AgentState` y devuelve `specialist_results` | Elimina la traducción del montaje común, pero cambia el contrato actual; el grafo documental y consumidores antiguos necesitan una fachada compatible |

Se adopta la segunda opción en el límite de integración: el adaptador exige
`ejecutar_documental`, lo valida como callable y lo llama directamente con el
contrato documental. Ya no contiene `graph_factory`, `.invoke`, importación del
subgrafo ni ejecutor real predeterminado. Sus pruebas inyectan funciones
simuladas. Reutiliza la traducción de fuentes, errores, abstención, limitaciones
y eventos, con correlación, copias y actualización parcial. No se ha añadido
otro adaptador ni otra implementación del especialista.

Esto conserva `nodo_documental`, sus exportaciones y `obtener_grafo_documental`
para quienes ya los usen. La indicación «El cliente usa esto, nunca
nodo_documental directamente» del grafo documental debe aclararse con Héctor
para distinguir cliente externo e integración interna. La puerta pública queda
intacta y la conexión real no se activa aquí. `contratos.md` también expone el
callable del nodo, de modo que la
documentación actual no expresa una única política de acceso coherente.

Si el equipo prefiere que el especialista adopte el contrato común nativamente,
el cambio mínimo compatible sería mantener una sola función de ejecución del
especialista y dos fachadas de contrato delgadas: la común y la documental
existente. La fachada antigua seguiría sirviendo al grafo documental. No copiar
el bucle de tools ni mantener dos implementaciones RAG. No se recomienda que
una misma función adivine el contrato por la presencia de claves ni devuelva
ambos sobres a la vez. Esa migración afecta más archivos y no se implementa
en esta revisión.

### Consumidores y pruebas afectados

Inventario limitado al repositorio local; pueden existir clientes externos de
la puerta pública que esta búsqueda no permite conocer.

| Consumidor o prueba | Con llamada directa y traducción | Si se cambia el contrato de `nodo_documental` sin fachada |
|---|---|---|
| `agentes/grafo_documental.py` | Sin cambios; sigue llamando al mismo nodo | Hay que traducir entrada/salida o adaptar su esquema; de lo contrario deja de producir `documental` |
| `agentes/nodes/__init__.py` y comando de importación de `docs/specs/contratos.md` | Firma y exportación conservadas | El import puede seguir funcionando, pero el contrato documentado deja de ser válido |
| `agentes/documental_adapter.py` | Ahora recibe un callable obligatorio; conserva el mapeo | Su extracción de `documental` deja de servir; retirar o reconvertir, evitando doble traducción |
| `tests/test_node_documental.py` (cinco casos) | Sin cambios por esta decisión; sus fallos previos siguen pendientes | Cambian las entradas `pedido/request_id` y las aserciones del sobre y clave única; conservar esos tests para la fachada antigua si existe |
| `tests/test_documental_adapter.py` | Dobles convertidos en callables; conserva mapeo, errores, no mutación y HITL y comprueba ausencia de carga documental automática | Reubicar las garantías de traducción en las pruebas del nodo común; mantener prueba de compatibilidad de la fachada |
| Prueba `test_real_documental_graph_public_entry_with_explicit_specialist_double` | Prueba la puerta antigua con nodo doble y, por separado, su inyección directa; no acredita el RAG | Debe comprobar que la fachada mantiene el sobre documental |
| `tests/test_import_boundaries.py` | Mantener carga diferida y exportación del callable original; no requiere cambios si se conserva el nodo | Revisar si se mueve la función exportada: la prueba comprueba su identidad |
| `agentes/graph.py`, `agentes/agent.py`, demo y tests del supervisor/servicio | Sin cambios de API: reciben un `Node` inyectado | Tampoco necesitan cambios si el nuevo nodo cumple `Node` y devuelve solo su patch |
| Streamlit, CLI, `app.py`, `main.py` | No se han encontrado llamadas directas a las puertas documentales; el cliente del servicio no necesita cambios | Conservar el contrato de `AgentService`; verificar aparte cualquier cliente externo |

En ambas alternativas se debe comprobar el principal con un callable documental
doble y el mismo contrato de resultado: intento único, conservación del otro
especialista, fuentes y restricciones, retorno al supervisor, pausa humana y
reanudación. La prueba del subgrafo con nodo doble es estructural; los tests de
RAG reales siguen siendo una validación independiente. Cambiar el modo de
composición no corrige sus dependencias, monkeypatch, presupuesto o retrieval.

## Adaptador explícito

`agentes/documental_adapter.py::crear_adaptador_documental()` devuelve un
callable compatible con `Node`. No se activa automáticamente en la demo ni
modifica los grafos existentes. El ejecutor se recibe explícitamente como
callable; importar el backend o construir el adaptador no carga RAG. No hay
implementación real ni simulación predeterminada.

| Traducción | Decisión |
|---|---|
| `user_message` → `pedido` | Texto vigente, sin historial implícito |
| `request_id` | UUID nuevo por invocación; `thread_id` identifica conversación, no pedido. Se verifica coincidencia de la respuesta |
| Opciones | Contexto, imagen, presupuesto y borrador explícitos al construir el adaptador; copias independientes por ejecución |
| `resultado` → `answer` | Se conserva incluso si es parcial o el especialista se abstiene |
| `fuentes` → `evidence` | Una `Evidence(source=referencia, content="")` por referencia; sin fragmentos, scores ni fechas inventados |
| Sobre completo → `data` | Copia de `request_id`, resultado, fuentes, abstención, errores, limitaciones y eventos; conserva también campos adicionales |
| `errores` → `error` | Mensaje agregado; lista original completa en `data["errores"]` |
| Estado común | Errores presentes → `error`; en su ausencia abstención explícita o resultado vacío → `abstained`; resto → `ok` |
| Actualización | Solo `specialist_results` y un evento nuevo en `debug_trace`; copia los resultados de otros roles porque ese campo no tiene acumulador |

La precedencia de error es conservadora: un texto útil con errores mantiene su
contenido y procedencia, pero no pasa a ser un éxito pleno. La abstención original
permanece en `data["abstained"]` incluso si prevalece `error`. Un intento fallido
o abstención queda registrado y el supervisor no lo repite indefinidamente.

El adaptador valida la estructura del sobre y la correlación del pedido. Un
formato incompatible produce `DOCUMENTAL_CONTRACT`. Una excepción del callable
inyectado se propaga, siguiendo la política actual de
`AgentService`; no se transforma en abstención ni en respuesta simulada. El
cliente debe presentar el fallo; una ejecución incompleta conserva las reglas
de recuperación del servicio. Los errores que el especialista sí devuelve en
su sobre se normalizan como resultados y permiten continuar hacia síntesis.

El adaptador no escribe decisiones, iteraciones, respuesta final, plan,
`approved` ni `done`. Tampoco incorpora supervisor, síntesis, HITL o ejecución
de acciones dentro del componente documental. Sus eventos de tools permanecen
estructurados en `data["eventos"]`; la traza común recibe solo un evento nuevo.

## Montaje por inyección y consumo

```python
from agentes.agent import AgentService
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.sintetizar import sintetizar
from agentes.nodes.aplicar import aplicar

# ejecutar_documental usa el contrato documental; en pruebas es un doble.
# Conectar el nodo real queda pendiente de coordinación con Héctor.
def montar_servicio(ejecutar_documental, instalaciones_node):
    return AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=ejecutar_documental),
        instalaciones_node=instalaciones_node,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar,
    )
```

David conserva esa instancia y el `thread_id` en Streamlit y utiliza
`procesar_turno`, `consultar_estado` y `resolver_plan`; no necesita invocar el
componente documental desde la UI. La síntesis inyectada debe consumir las
evidencias y `data["limitaciones"]`, `data["errores"]` y `data["abstained"]`
para mantener esas restricciones en el texto presentado. Conservarlos en el
adaptador no acredita todavía que una síntesis real los presente correctamente.
La síntesis y aplicar deterministas ya están implementados: ver
[síntesis y cierre informativo](sintetizar_aplicar.md). No se modifica
`graph.py`, `agent.py` ni clientes para conectarlos.

El contrato público actual de `AgentService` solo admite mensaje e hilo. Las
opciones documentales del adaptador son configuración del montaje, no soporte
de imagen/contexto por turno. No se toman campos extra de un `AgentState` que
LangGraph podría descartar. Para entradas variables por pedido hace falta acordar
su transporte con Héctor y David. El adaptador exige presupuesto positivo:
no promete resolver el comportamiento incorrecto del presupuesto cero del nodo.

## Compatibilidad comprobada y validación pendiente

Las pruebas de `tests/test_documental_adapter.py` usan respuestas explícitamente
simuladas. Comprueban mapeo, precedencia de errores, abstención, salida parcial,
fuentes sin fragmentos, conservación de eventos y limitaciones, no mutación,
identificadores, ausencia de carga documental implícita y rechazo de sobres incompatibles.
También compilan el `grafo_documental` real sustituyendo exclusivamente el nodo
especialista por un doble; eso comprueba la puerta y topología, no sus tools.
El recorrido de `tests/test_sintetizar_aplicar.py` usa el grafo supervisor real,
síntesis/aplicar reales y especialistas dobles; verifica que solo el principal
pausa y reanuda la aprobación/rechazo, además de idempotencia, plan antiguo,
pedidos consecutivos, trazas y aislamiento. No constituye una integración con RAG real.

Se conserva el [diagnóstico previo del RAG](revision_entorno_rag.md), que es
trabajo local anterior y no se sustituye aquí. Sigue registrando dependencias
ausentes, el monkeypatch incorrecto de `REGISTRY`, presupuesto cero, variables
sin definir en HuggingFace y acceso a Chroma durante colección de tests.
No se han reparado estos problemas ni ejecutado pruebas que consulten índices
o modelos. Poder conectar el componente no valida retrieval, calidad, vigencia
ni restricciones de evidencia. Por ejemplo, el filtrado actual de contexto no
garantiza retirar del texto fragmentos no autorizados cuando también quedan
fuentes autorizadas; el adaptador conserva el sobre, no puede reconstruir la
relación fragmento/fuente que no recibe. Revisar esa garantía con Héctor.

Héctor mantiene la responsabilidad del RAG, sus pruebas y semántica documental;
Miguel, del especialista de instalaciones; Alejandra, del montaje y consumo del
contrato común; David, de la presentación y decisión humana mediante el servicio.

La comprobación vigente y su comando están en
[síntesis y cierre informativo](sintetizar_aplicar.md). El resultado anterior de
191 pruebas correspondía a la composición previa con subgrafo, no al estado
actual del adaptador. Los bloqueos previos del RAG no se presentan como fallos
nuevos ni como problemas resueltos por este cambio.

## Texto de coordinación para enviar manualmente

> Continúo con sintetizar y aplicar deterministas, probados con resultados
> simulados conforme al contrato común. La traducción documental es provisional
> y ahora recibe un callable; no exige invocar el subgrafo ni conecta el RAG real.
> Con Héctor queda pendiente acordar la llamada directa porque su módulo propone
> el grafo como puerta pública, además de revisar sus fallos internos. Necesitamos
> ejemplos reales con fuentes, abstención, errores y limitaciones; Miguel aporta
> el equivalente de instalaciones y David consume el servicio conservando hilo,
> plan_id y decisión humana. Las pruebas con dobles no validan el RAG.
