"""Cierre informativo y guardia compatible con la inyección del grafo.

AgentService valida el plan_id y registra la decisión humana antes de reanudar.
Este módulo valida el estado y la salida, y añade una única marca HITL.
No reserva, paga ni envía incidencias. aplicar es la implementación concreta.
"""

from collections.abc import Callable

from agentes.state import AgentState, plan_is_ready


def aplicar(state: AgentState) -> dict:
    """Resuelve el plan informativo tras una decisión humana booleana real.

    Al rechazar limpia la propuesta y los resultados operativos; la decisión
    queda como evidencia hasta que initial_state reinicie el siguiente pedido.
    El servicio conserva plan_id e idempotencia. La guardia añade el evento HITL,
    por lo que esta implementación no devuelve ni repite la traza recibida.
    """
    if type(state.get("approved")) is not bool:
        raise ValueError("HITL_DECISION_REQUIRED: guardar approved=True/False antes de reanudar")
    if not plan_is_ready(state):
        raise ValueError("HITL_PLAN_REQUIRED: aplicar requiere respuesta y plan validos")
    if state["approved"]:
        return {"done": True, "pending_action": None,
                "final_answer": state["final_answer"] +
                "\nPlan informativo aprobado. No se ha ejecutado ninguna acción externa."}
    return {"done": False, "plan": [], "specialist_results": {}, "pending_action": None,
            "final_answer": "Propuesta rechazada. Puedes enviar un nuevo pedido."}


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
