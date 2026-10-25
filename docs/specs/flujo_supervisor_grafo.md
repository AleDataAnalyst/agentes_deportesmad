# Flujo síncrono de supervisor y grafo

Flujo explicativo de coordinación, síntesis y aprobación humana.
Actualizado el 25/10/2026: runtime conecta documental e instalaciones y selecciona
supervisor LLM Google/Ollama o reglas. CLI y Streamlit utilizan la misma factoría.
El montaje está probado con dobles; la aceptación conjunta real sigue pendiente.

Actualización del 17/10/2026: ya se pueden inyectar las implementaciones
deterministas `sintetizar` y `aplicar` en `AgentService`. El grafo aplica sus
guardias `sintetizar_node` y `aplicar_node`; el cliente no llama a los nodos.
La síntesis conserva fuentes y restricciones, y aplicar resuelve un plan
informativo sin acciones externas. Ver [montaje y pruebas](sintetizar_aplicar.md).

No cambia la topología. El [ASCII generado](grafo_actual.txt), regenerado con
`python -m scripts.ver_grafo`, conserva el mismo contenido y procede de la
demo simulada. El esquema explicativo siguiente detalla los retornos al
supervisor y la pausa humana. La traducción documental recibe un callable que
resuelve la puerta pública al consultar, evitando cargar RAG/Chroma durante la
construcción. Las mejoras de #21 se integrarán detrás de esa puerta; se conserva
la topología principal. El transporte de `image_id` desde Streamlit sigue
pendiente: guardar la imagen no implica enviarla al agente. Visión no es una
ruta del supervisor actual.

```text

CLIENTE: CLI / Streamlit / demo
              |
              +-- Runtime: real o demo explícita, sin fallback a demo
              +-- Real: LLM Google/Ollama o reglas; proveedor inyectable
              |
              v
    AgentService.procesar_turno()
              |
              +-- Comprueba que no haya un plan pendiente
              +-- Reinicia los datos operativos del pedido
              +-- Aporta solo la marca "inicio de pedido"
              |
              v
    grafo.invoke(estado, config)
    Acumulador: traza anterior + eventos nuevos
              |
              v
         SUPERVISOR <-----------------------------------+
              |                                         |
              | Propone ruta; fallback y límite Python  |
              v                                         |
        ROUTER DE PYTHON                                |
              |                                         |
              +-- documental ------> resultado ----------+
              |                                         |
              +-- instalaciones ---> resultado ----------+
              |                                         |
              +-- sintetizar ------> respuesta + plan ---+
              |
              `-- FINISH
                    |
                    v
            ¿Respuesta y plan válidos?
                    |
                    +-- NO --> sintetizar --> supervisor
                    |
                    `-- SÍ
                         |
                         v
                PAUSA ANTES DE APLICAR
                ----------------------
                Checkpoint guardado
                approved = None
                pendiente_hitl = True
                         |
                         v
                  DECISIÓN HUMANA
                         |
                         v
             AgentService.resolver_plan()
                         |
                         +-- Valida thread_id y plan_id
                         +-- Si ya está resuelto igual, devuelve el estado
                         +-- update_state(approved)
                         `-- invoke(None, mismo config)
                                      |
                                      v
                                   APLICAR
                         Eventos nuevos + una decisión HITL
                                      |
                    +-----------------+-----------------+
                    |                                   |
              approved=True                       approved=False
                    |                                   |
               done=True                      done=False / reset
                    |                                   |
                    v                                   v
                   END                                 END
```

## Cómo interpretarlo

- El LLM puede consultar solo los especialistas pertinentes; no obliga a visitar
  ambos. Por reglas/fallback se consulta documental, instalaciones y síntesis.
- Fuentes, errores, abstenciones y limitaciones se conservan hasta los clientes;
  Streamlit añade avisos por estado y fuentes bajo la respuesta.
- FINISH termina la preparación y conduce hacia la revisión humana.
- La pausa ocurre antes de ejecutar aplicar.
- Aprobar y rechazar pasan por aplicar.
- END termina la ejecución; tras rechazar, done permanece en False.
- La pausa y la reanudación utilizan el mismo thread_id.

## Estado del pedido y traza de la conversación

El servicio conserva una sola instancia del grafo. Cada llamada a
`procesar_turno()` utiliza `initial_state()` para reiniciar los datos operativos:
resultados de especialistas, respuesta, plan, acción pendiente, aprobación,
decisión del supervisor, contador de iteraciones y `done`. Si hay un plan
pendiente o una ejecución incompleta, el servicio rechaza otro pedido en ese
hilo hasta resolver la situación según las validaciones existentes.

`debug_trace` tiene una política distinta: conserva los eventos de la
conversación mientras se reutiliza el mismo `thread_id`. Cada pedido aporta
solo la marca `inicio de pedido`, que permite distinguir dónde empieza su
recorrido. Un `thread_id` nuevo tiene una traza independiente.

Esto cambia el comportamiento anterior: la traza se sustituía por pedido.
Ahora se acumula por conversación; los datos operativos siguen reiniciándose
por pedido. No se añade historial de mensajes.

## Cómo funciona el acumulador

En [state.py](../../agentes/state.py), el estado declara un acumulador
exclusivamente para `debug_trace`:

```python
from typing import Annotated

def _acumular(actual: list, nuevo: list) -> list:
    return (actual or []) + (nuevo or [])

# Dentro de AgentState:
debug_trace: Annotated[list[str], _acumular]
```

Cuando un nodo devuelve eventos, LangGraph llama al acumulador para combinar
la traza existente con esos eventos nuevos, en orden. Los demás campos se
reemplazan con sus actualizaciones; no tienen acumulador.

Cada nodo devuelve únicamente los eventos que acaba de producir:

```python
return {"debug_trace": [event]}
# Si produce varios eventos:
return {"debug_trace": [evento_uno, evento_dos]}
```

El nodo no incorpora `state["debug_trace"]` al retorno ni hace `append` sobre
la lista recibida. Devolver la traza completa haría que el acumulador añadiera
otra vez los eventos anteriores. Tampoco debe modificar el estado de entrada.

Los puntos corregidos son:

- [supervisor.py](../../agentes/nodes/supervisor.py): devuelve solo el evento
  de la decisión actual, junto con la decisión y el contador.
- [demo.py](../../agentes/demo.py): los dobles de especialistas y síntesis
  devuelven solo sus eventos nuevos. Los resultados de especialistas siguen
  conservando los de otros roles mediante su actualización explícita.
- [aplicar.py](../../agentes/nodes/aplicar.py): el envoltorio `aplicar_node`,
  montado desde [graph.py](../../agentes/graph.py), conserva los
  eventos nuevos del nodo inyectado y añade su propio evento
  `HITL -> plan aprobado` o `HITL -> plan rechazado`. Si el nodo no devuelve
  traza, parte de una lista vacía. El evento HITL corresponde al envoltorio;
  el nodo inyectado no debe volver a generarlo.

## Dos pedidos y dos hilos

Por ejemplo, tras resolver el primer pedido y enviar otro en el mismo hilo,
la traza tendrá esta estructura. Los puntos suspensivos representan los
eventos del recorrido, no un evento literal:

```text
Hilo A
  inicio de pedido
  iter 1: supervisor -> documental; origen=reglas
  ... eventos del primer pedido ...
  HITL -> plan aprobado
  inicio de pedido
  iter 1: supervisor -> documental; origen=reglas
  ... eventos del segundo pedido ...

Hilo B (nuevo)
  inicio de pedido
  iter 1: supervisor -> documental; origen=reglas
  ... eventos propios del hilo B ...
```

El segundo pedido del hilo A conserva la traza anterior, pero comienza con
resultados vacíos, sin plan ni aprobación y con el contador a cero. El hilo B
no recibe los eventos del hilo A. Durante la resolución se reutilizan el
mismo grafo, `thread_id` y checkpoint del pedido pendiente.

`consultar_estado()` lee una copia sin ejecutar nodos ni añadir eventos.
Repetir una aprobación o rechazo ya resuelto con el mismo `plan_id` y la misma
decisión devuelve el estado sin volver a ejecutar aplicar ni duplicar HITL.
Una decisión contradictoria o un `plan_id` antiguo sigue siendo rechazada;
el acumulador no cambia la política de aprobación ni de plan vigente.

## Acumular y copiar cumplen funciones diferentes

`state_from_graph()` conserva `deepcopy`: devuelve al cliente una copia
independiente de la salida ya acumulada. Así, modificar listas, resultados,
metadatos o acciones anidadas en el cliente no cambia el checkpoint ni las
estructuras originales. Esta conversión copia la traza recibida; no vuelve
a aplicar el acumulador.

Un `state.update({"debug_trace": [event]})` de Python puro reemplaza la lista.
`Annotated` no hace que los diccionarios ejecuten el acumulador por sí solos.
Por eso las pruebas aisladas comprueban los eventos nuevos y la inmutabilidad,
y las integraciones con LangGraph comprueban la acumulación efectiva:

- [Estado](../../tests/test_state.py): acumulador, diferencia con `dict.update`
  y aislamiento de estructuras anidadas mediante `deepcopy`.
- [Supervisor](../../tests/test_supervisor.py) y [demo](../../tests/test_demo.py):
  retornos con eventos nuevos y estado de entrada intacto.
- [Grafo real](../../tests/test_sync_integration.py): eventos acumulados una
  sola vez y en orden, incluidos los del nodo aplicar y del envoltorio HITL.
- [Servicio](../../tests/test_agent_service.py): conservación entre pedidos,
  reinicio operativo, independencia entre hilos y decisiones idempotentes.

El grafo sigue siendo síncrono. Los checkpoints y la traza de `MemorySaver`
se conservan durante la vida del proceso del servicio.
