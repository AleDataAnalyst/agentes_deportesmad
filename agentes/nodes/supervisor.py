"""Supervisor síncrono con proveedor inyectable y límites en Python.

No ejecuta tools, no redacta el plan ni aprueba el pedido. Runtime puede inyectar
el proveedor LLM configurado; sin proveedor utiliza reglas deterministas.
La traza identifica el origen y una causa breve de fallback, sin reproducir
prompts, motivos del proveedor ni textos completos de excepciones.
"""
from collections.abc import Callable
from copy import deepcopy
from agentes.contracts import ROUTE_NAMES, SPECIALIST_NAMES, SupervisorDecision
from agentes.state import AgentState, plan_is_ready

ROLES = SPECIALIST_NAMES
RouteProvider = Callable[[AgentState], SupervisorDecision]


def fallback_decision(state: AgentState) -> SupervisorDecision:
    """Política provisional de integración, pendiente de revisión con el equipo.

    Consulta documental, después instalaciones, luego sintetiza y finalmente
    propone FINISH cuando la respuesta y el plan están listos. La presencia de
    resultado cuenta como intento completado, incluso con error o abstained.
    Un plan listo no salta los roles que aún no tienen resultado.
    """
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
    """Devuelve solo decisión, contador y traza como actualización parcial.

    No modifica el estado recibido ni sus colecciones; el proveedor recibe
    una copia independiente, incluso si después falla. Los orígenes son reglas (sin
    proveedor), proveedor (propuesta válida), fallback (fallo o propuesta
    inválida) y limite (tope alcanzado).

    El tope fuerza FINISH. El router pasa por síntesis si falta el plan y luego
    por la pausa. Una síntesis inválida falla explícitamente en el grafo.
    """
    if type(max_iter) is not int or max_iter < 1:
        raise ValueError("max_iter debe ser un entero positivo")
    iteration = state.get("iterations", 0) + 1
    cause = None
    if iteration >= max_iter:
        decision = SupervisorDecision("FINISH", "Limite de iteraciones alcanzado.")
        origin = "limite"
    else:
        decision = None
        origin = "reglas"
        if route_provider is not None:
            origin = "fallback"
            try:
                proposed = route_provider(deepcopy(state))
                if not isinstance(proposed, SupervisorDecision):
                    cause = "tipo_respuesta_incorrecto"
                elif proposed.specialist not in ROUTE_NAMES:
                    cause = "ruta_desconocida"
                elif not isinstance(proposed.reason, str):
                    cause = "tipo_motivo_incorrecto"
                elif (proposed.specialist in ROLES
                      and proposed.specialist in state.get("specialist_results", {})):
                    cause = "especialista_ya_consultado"
                else:
                    decision = proposed
                    origin = "proveedor"
            except Exception:
                # Registrar solo la categoría, nunca el texto de la excepción.
                cause = "excepcion_proveedor"
        if decision is None:
            decision = fallback_decision(state)
    event = f"iter {iteration}: supervisor -> {decision.specialist}; origen={origin}"
    if cause is not None:
        event += f"; causa={cause}"
    return {
        "supervisor_decision": decision,
        "iterations": iteration,
        "debug_trace": [event],
    }
