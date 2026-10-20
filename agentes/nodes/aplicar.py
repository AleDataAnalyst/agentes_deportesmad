"""Cierre informativo y guardia compatible con la inyección del grafo.

AgentService valida el plan_id y registra la decisión humana antes de reanudar.
Este módulo valida el estado y la salida, y añade una única marca HITL.
No reserva, paga ni envía incidencias. aplicar es la implementación concreta.
"""

from collections.abc import Callable

from agentes.node_guards import ejecutar_aislado
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
    nuevos; esta envoltura añade la marca de decisión HITL. Al aprobar,
    final_answer solo puede conservarse o ampliarse al final.
    """
    if type(state.get("approved")) is not bool:
        raise ValueError("HITL_DECISION_REQUIRED: guardar approved=True/False antes de reanudar")
    if not plan_is_ready(state):
        raise ValueError("HITL_PLAN_REQUIRED: aplicar requiere respuesta y plan validos")
    update = ejecutar_aislado(state, node, campos=frozenset({
        "done", "plan", "specialist_results", "final_answer", "pending_action", "debug_trace",
    }), codigo="APPLY_CONTRACT")
    if not isinstance(update, dict) or update.get("done") is not state["approved"]:
        raise ValueError("APPLY_CONTRACT: aplicar debe devolver done=True al aprobar y done=False al rechazar")
    if "final_answer" in update and not isinstance(update["final_answer"], str):
        raise ValueError("APPLY_CONTRACT: final_answer debe ser texto")
    if (state["approved"] and "final_answer" in update
            and not update["final_answer"].startswith(state["final_answer"])):
        raise ValueError("APPLY_CONTRACT: al aprobar solo se permite añadir texto al final de final_answer")
    # Se puede conservar el plan/evidencia aprobados o limpiarlos al rechazar.
    # No se autoriza introducir otro plan, resultados o acciones en el cierre.
    for campo, vacio in (("plan", []), ("specialist_results", {})):
        if campo in update and update[campo] != state.get(campo, vacio):
            if state["approved"] or type(update[campo]) is not type(vacio) or update[campo] != vacio:
                raise ValueError("APPLY_CONTRACT: no se permite sustituir el plan ni sus resultados")
    if update.get("pending_action") is not None and update["pending_action"] != state.get("pending_action"):
        raise ValueError("APPLY_CONTRACT: no se permite introducir otra acción")
    return {
        **update,
        "debug_trace": [
            *update.get("debug_trace", []),
            "HITL -> " + ("plan aprobado" if state["approved"] else "plan rechazado"),
        ],
    }
