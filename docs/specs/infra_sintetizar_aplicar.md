# Base de infraestructura de síntesis y aplicar

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
