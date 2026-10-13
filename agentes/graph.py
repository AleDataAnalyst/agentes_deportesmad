"""Grafo LangGraph sincrono con nodos inyectados y pausa antes de aplicar.

No importa el LLM ni las implementaciones de especialistas. La API de clientes
y la validacion de plan vigente siguen siendo responsabilidades del servicio.
"""
from collections.abc import Callable
from functools import partial
from agentes.state import AgentState, plan_is_ready
from agentes.nodes.supervisor import ROLES, RouteProvider, fallback_decision, supervisor_node

Node = Callable[[AgentState], dict]


def router_supervisor(state: AgentState) -> str:
    """FINISH pasa por sintesis si falta el plan, o por la pausa HITL."""
    decision = state.get("supervisor_decision")
    requested = getattr(decision, "specialist", None)
    if requested == "FINISH":
        return "aplicar" if plan_is_ready(state) else "sintetizar"
    if requested == "sintetizar":
        return "sintetizar"
    if requested in ROLES and requested not in state.get("specialist_results", {}):
        return requested
    fallback = fallback_decision(state).specialist
    if fallback == "FINISH":
        return "aplicar" if plan_is_ready(state) else "sintetizar"
    return fallback


def _sintetizar_checked(state: AgentState, *, node: Node) -> dict:
    """Exige respuesta y plan validos sin aprobacion ni cierre automaticos."""
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


def _aplicar_checked(state: AgentState, *, node: Node) -> dict:
    """None es pendiente; False es una decision humana de rechazo."""
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
            *update.get("debug_trace", state.get("debug_trace", [])),
            "HITL -> " + ("plan aprobado" if state["approved"] else "plan rechazado"),
        ],
    }


def build_graph(
    *, documental_node: Node, instalaciones_node: Node, sintetizar_node: Node,
    aplicar_node: Node, route_provider: RouteProvider | None = None,
    max_iter: int = 8, checkpointer=None,
):
    """Compila una vez por servicio y reutiliza la instancia entre turnos.

    Ejecutar con config={"configurable": {"thread_id": ...}}. Para resolver
    la pausa, guardar approved con update_state y reanudar con invoke(None,
    config). Cada pedido nuevo debe limpiar el estado con initial_state.
    MemorySaver conserva checkpoints solo durante la vida del proceso.
    """
    if type(max_iter) is not int or max_iter < 1:
        raise ValueError("max_iter debe ser un entero positivo")
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver

    builder = StateGraph(AgentState)
    builder.add_node("supervisor", partial(supervisor_node, route_provider=route_provider, max_iter=max_iter))
    builder.add_node("documental", documental_node)
    builder.add_node("instalaciones", instalaciones_node)
    builder.add_node("sintetizar", partial(_sintetizar_checked, node=sintetizar_node))
    builder.add_node("aplicar", partial(_aplicar_checked, node=aplicar_node))
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges("supervisor", router_supervisor, {
        "documental": "documental", "instalaciones": "instalaciones",
        "sintetizar": "sintetizar", "aplicar": "aplicar",
    })
    for name in (*ROLES, "sintetizar"):
        builder.add_edge(name, "supervisor")
    builder.add_edge("aplicar", END)
    return builder.compile(
        checkpointer=MemorySaver() if checkpointer is None else checkpointer,
        interrupt_before=["aplicar"],
    )
