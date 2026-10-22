"""Grafo LangGraph sincrono con nodos inyectados y pausa antes de aplicar.

No importa el LLM ni las implementaciones de especialistas. La API de clientes
y la validacion de plan vigente siguen siendo responsabilidades del servicio.
"""
from collections.abc import Callable
from functools import partial
from agentes import llm
from agentes.node_guards import especialista_protegido
from agentes.nodes.aplicar import aplicar_node as _aplicar_checked
from agentes.nodes.sintetizar import sintetizar_node as _sintetizar_checked
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

def especialista_documental(state: AgentState) -> dict:
    """TODO: especialista con acceso a rag_ask y/o consultar_api_dominio."""
    return {"mensajes": ["especialista_a: ejecutando análisis"]}

def build_graph(
    *, documental_node: Node, instalaciones_node: Node, sintetizar_node: Node,
    aplicar_node: Node, route_provider: RouteProvider | None = None,
    max_iter: int = 8, checkpointer=None,
):
    """Compila una vez por servicio y reutiliza la instancia entre turnos.

    Ejecutar con config={"configurable": {"thread_id": ...}}. Para resolver
    la pausa, guardar approved con update_state y reanudar con invoke(None,
    config). Cada pedido nuevo reinicia los datos operativos con initial_state
    y añade su marca de inicio a la traza del hilo mediante el acumulador.
    MemorySaver conserva checkpoints solo durante la vida del proceso.
    """
    if type(max_iter) is not int or max_iter < 1:
        raise ValueError("max_iter debe ser un entero positivo")
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    if checkpointer is None:
        # Tipos internos del estado: registro explícito, también en modo estricto.
        # No se altera el serializador de un checkpoint suministrado por el cliente.
        checkpointer = MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=[
            ("agentes.contracts", nombre)
            for nombre in ("SupervisorDecision", "Evidence", "ToolResult", "PendingAction")
        ]))



    builder = StateGraph(AgentState)
    builder.add_node("supervisor", partial(supervisor_node, route_provider=route_provider, max_iter=max_iter))
    builder.add_node("documental", partial(especialista_protegido, rol="documental", node=documental_node))
    builder.add_node("instalaciones", partial(especialista_protegido, rol="instalaciones", node=instalaciones_node))
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
        checkpointer=checkpointer,
        interrupt_before=["aplicar"],
    )


