# Base de infraestructura de síntesis y aplicar

Actualización del 17/10/2026: las guardias descritas aquí conservan sus firmas.
Ya existen las implementaciones deterministas `sintetizar(state)` y
`aplicar(state)`, documentadas con su montaje y verificación vigente en
[síntesis y resolución del plan](sintetizar_aplicar.md). Los apartados siguientes
recogen el alcance de la extracción original y sus comprobaciones históricas.

Alcance autorizado el 15/10/2026: extraer las guardias existentes del grafo
a módulos reutilizables. La lógica completa y la integración de los nodos
reales quedan pendientes de confirmación. No cambia el contrato del estado,
de los especialistas ni de los clientes.

## Interfaces disponibles

- `agentes.nodes.sintetizar.sintetizar_node(state, *, node)` valida que el
  pedido siga pendiente, llama a la implementación inyectada y exige una
  actualización con `final_answer` y `plan` no vacíos. No permite aprobar
  ni cerrar el pedido.
- `agentes.nodes.aplicar.aplicar_node(state, *, node)` exige `approved` booleano
  y un plan válido antes de llamar a la implementación. Exige `done` idéntico
  a la decisión humana y añade la marca HITL a los eventos nuevos.

Ambas interfaces requieren una implementación explícita. No proporcionan
una lógica predeterminada, modelo ni fallback simulado. Las excepciones
se propagan al cliente. La comprobación estructural no evalúa la fidelidad
de una respuesta a sus fuentes.

## Montaje y responsabilidades

`build_graph(...)` utiliza estas envolturas automáticamente sobre los nodos
recibidos en `sintetizar_node=` y `aplicar_node=`. `AgentService` conserva
la validación del `plan_id`, la decisión vigente, la reanudación e idempotencia.
El punto de pausa sigue siendo `interrupt_before=["aplicar"]`.

Quien implemente la continuación entrega un callable síncrono
`implementacion(state) -> dict` con una actualización parcial, sin mutar el
estado recibido. Se pasa directamente a `AgentService` o `build_graph`;
no debe envolverse de nuevo con estas guardias ni duplicar la marca HITL.
Los eventos devueltos son solo los nuevos, porque el estado acumula la traza.

Quedan por acordar la combinación de evidencias, fuentes, limitaciones,
contradicciones, prompt, fallback y presentación final del cierre/rechazo.
No se incorporan reservas, pagos ni envíos externos. La demo continúa usando
dobles explícitos y no acredita ninguno de esos bloques reales.

## Verificación

```powershell
python -m pytest -q
```

`tests/test_infra_sintetizar_aplicar.py` comprueba las guardias con dobles,
incluido el rechazo previo a ejecutar una implementación y la propagación
de sus errores. Las pruebas del servicio y la demo comprueban el recorrido
integrado, la pausa y la resolución con las envolturas extraídas.

### Importaciones tras integrar develop (17/10/2026)

Los paquetes `agentes.nodes` y `agentes.tools` resuelven sus exportaciones
documentales cuando se solicitan, mediante `__getattr__`. Conservan los
callables públicos `nodo_documental` y `rag_preguntar`. Importar el supervisor,
síntesis, aplicar o la demo ya no importa automáticamente el especialista
documental y sus dependencias de modelos. Solicitar o importar directamente
el especialista sigue requiriendo sus dependencias reales.

Verificación con Python 3.14 del sistema (la `.venv` local no tenía pytest):

```powershell
python -m pytest -q tests/test_import_boundaries.py tests/test_infra_sintetizar_aplicar.py tests/test_sync_integration.py tests/test_agent_service.py tests/test_state.py tests/test_supervisor.py tests/test_demo.py tests/test_contracts.py tests/test_async.py tests/test_graph_hitl.py tests/test_clients.py
```

Resultado: 198 pruebas superadas. La regresión de importaciones se ejecuta en
procesos nuevos y bloquea explícitamente la carga documental/RAG mientras
comprueba la demo hasta la pausa HITL. Las exportaciones se comprueban con
dobles explícitos; no se acredita la ejecución del RAG.

`python -m pytest -q` sigue bloqueado durante la colección de
`test_node_documental.py`, `test_tool_rag.py` y `test_tools.py` por falta de
`sentence_transformers`. No se ejecutó la suite completa ni se omitieron o
modificaron esas pruebas. La validación del entorno y del RAG queda pendiente.
