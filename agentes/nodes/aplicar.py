"""Infraestructura de aplicar; el cierre concreto se recibe por inyección.

AgentService valida el plan_id y registra la decisión humana antes de reanudar.
Este módulo valida el estado y la salida, y añade una única marca HITL.
No reserva, paga ni envía incidencias. La lógica de cierre sigue pendiente.
"""

from collections.abc import Callable

from agentes.state import AgentState, plan_is_ready


def aplicar_node(
    state: AgentState, *, node: Callable[[AgentState], dict],
) -> dict:
    """Exige decisión booleana y plan; valida done en el cierre inyectado.

    None significa pendiente y False es un rechazo explícito. La implementación
    devuelve done=True al aprobar o done=False al rechazar y solo sus eventos
    nuevos; esta envoltura añade la marca de decisión HITL.
    """
    if type(state.get("approved")) is not bool:
        raise ValueError("HITL_DECISION_REQUIRED: guardar approved=True/False antes de reanudar")
    if not plan_is_ready(state):
        raise ValueError("HITL_PLAN_REQUIRED: aplicar requiere respuesta y plan validos")
    update = node(state)
    if not isinstance(update, dict) or update.get("done") is not state["approved"]:
        raise ValueError("APPLY_CONTRACT: aplicar debe devolver done=True al aprobar y done=False al rechazar")
    return {
        **update,
        "debug_trace": [
            *update.get("debug_trace", []),
            "HITL -> " + ("plan aprobado" if state["approved"] else "plan rechazado"),
        ],
    }
