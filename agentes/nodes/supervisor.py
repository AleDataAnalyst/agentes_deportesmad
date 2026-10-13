"""Supervisor sincrono con proveedor inyectable y limites en Python.

No ejecuta tools, no redacta el plan ni aprueba el pedido. El proveedor podrá
adaptar el LLM cuando se acuerde su interfaz. Las reglas permiten usar dobles.
"""
from collections.abc import Callable
from agentes.contracts import ROUTE_NAMES, SPECIALIST_NAMES, SupervisorDecision
from agentes.state import AgentState, plan_is_ready

ROLES = SPECIALIST_NAMES
RouteProvider = Callable[[AgentState], SupervisorDecision]


def fallback_decision(state: AgentState) -> SupervisorDecision:
    """La presencia de resultado cuenta como intento, incluso error/abstained."""
    results = state.get("specialist_results", {})
    for role in ROLES:
        if role not in results:
            return SupervisorDecision(role, f"Falta el resultado de {role}.")
    if not plan_is_ready(state):
        return SupervisorDecision("sintetizar", "Preparar respuesta y plan con los resultados disponibles.")
    return SupervisorDecision("FINISH", "Respuesta y plan listos para la decision humana.")


def supervisor_node(
    state: AgentState, *, route_provider: RouteProvider | None = None, max_iter: int = 8,
) -> AgentState:
    """Devuelve decision, contador y traza como actualizacion parcial.

    El tope fuerza FINISH. El router pasa por sintesis si falta el plan y luego
    por la pausa. Una sintesis invalida falla explicitamente en el grafo.
    """
    if type(max_iter) is not int or max_iter < 1:
        raise ValueError("max_iter debe ser un entero positivo")
    iteration = state.get("iterations", 0) + 1
    if iteration >= max_iter:
        decision = SupervisorDecision("FINISH", "Limite de iteraciones alcanzado.")
    else:
        decision = None
        if route_provider is not None:
            try:
                proposed = route_provider(state)
                if (isinstance(proposed, SupervisorDecision)
                        and proposed.specialist in ROUTE_NAMES
                        and isinstance(proposed.reason, str)
                        and (proposed.specialist not in ROLES
                             or proposed.specialist not in state.get("specialist_results", {}))):
                    decision = proposed
            except Exception:
                # La indisponibilidad del proveedor activa las reglas locales.
                pass
        if decision is None:
            decision = fallback_decision(state)
    return {
        "supervisor_decision": decision,
        "iterations": iteration,
        "debug_trace": [*state.get("debug_trace", []),
                        f"iter {iteration}: supervisor -> {decision.specialist}: {decision.reason}"],
    }
