"""Infraestructura de síntesis; la lógica se recibe por inyección.

No combina evidencias ni llama al modelo. El contrato de especialistas,
el prompt, las fuentes, las limitaciones y el fallback siguen pendientes.
plan_id y la fase HITL pertenecen a AgentService, no a este nodo.
"""

from collections.abc import Callable

from agentes.state import AgentState, plan_is_ready


def sintetizar_node(
    state: AgentState, *, node: Callable[[AgentState], dict],
) -> dict:
    """Valida la implementación inyectada sin aprobar ni cerrar el pedido.

    La implementación recibe el estado y devuelve una actualización parcial
    con final_answer y plan no vacíos. Debe conservar la procedencia y las
    limitaciones al redactar; esta guardia solo comprueba la estructura mínima.
    Las excepciones se propagan: no se sustituye un fallo por datos simulados.
    """
    if state.get("approved") is not None or state.get("done", False) is not False:
        raise ValueError("SYNTHESIS_CONTRACT: el pedido debe estar pendiente y sin cerrar")
    update = node(state)
    if (not isinstance(update, dict)
            or "final_answer" not in update or "plan" not in update
            or not plan_is_ready({**state, **update})):
        raise ValueError("SYNTHESIS_CONTRACT: sintetizar debe devolver final_answer y plan no vacios")
    if update.get("approved") is not None or update.get("done", False) is not False:
        raise ValueError("SYNTHESIS_CONTRACT: la sintesis no puede aprobar ni cerrar el pedido")
    return update
