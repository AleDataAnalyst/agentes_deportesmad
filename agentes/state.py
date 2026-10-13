"""Estado mínimo del grafo y conversión independiente para UI/CLI.

Mantiene user_message, final_answer y los otros nombres de la primera versión.
Cada nodo devuelve una actualización parcial; LangGraph fusiona esas claves.
No hay reducers: las listas y diccionarios se reemplazan, no se acumulan solos.
"""

from copy import deepcopy
from typing import Any, TypedDict

from agentes.contracts import PendingAction, SupervisorDecision, ToolResult

class AgentState(TypedDict, total=False):
    """Campos compartidos. TypedDict documenta tipos, no valida en ejecución.

    Entrada: user_message/thread_id. Supervisor: decisión, iterations y traza.
    Especialistas: specialist_results. Síntesis: final_answer/plan/pending_action.
    Humano: approved (None antes de decidir). Aplicar: done y cierre/reset.
    Cada nodo puede extender debug_trace devolviendo una lista nueva.
    """

    user_message: str
    thread_id: str
    supervisor_decision: SupervisorDecision | None
    specialist_results: dict[str, ToolResult]
    final_answer: str
    plan: list[str]
    pending_action: PendingAction | None
    approved: bool | None
    iterations: int
    done: bool
    debug_trace: list[str]

def initial_state(user_message: str, thread_id: str = "demo") -> AgentState:
    """Crea colecciones independientes y reinicia los datos de un pedido.

    No necesita deepcopy: cada llamada construye listas y dict nuevos. También
    reinicia la decisión y la aprobación para no reutilizar las del pedido anterior.
    thread_id aquí es informativo; el checkpoint se identifica en configurable.
    TODO clientes: conservar historial de conversación fuera de este estado mínimo
    o acordar el campo correspondiente antes de incorporarlo.
    """
    if not isinstance(user_message, str):
        raise TypeError("user_message debe ser un texto")
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id debe ser un texto no vacío")
    return {
        "user_message": user_message,
        "thread_id": thread_id,
        "supervisor_decision": None,
        "specialist_results": {},
        "final_answer": "",
        "plan": [],
        "pending_action": None,
        "approved": None,
        "iterations": 0,
        "done": False,
        "debug_trace": ["estado inicial creado"],
    }

def state_from_graph(
    resultado: dict[str, Any], base: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Convierte la salida en una copia independiente para un cliente.

    Necesita deepcopy para que el cliente no modifique la versión interna del grafo:
    la UI puede modificar listas, resultados o metadatos sin tocar la base ni
    las referencias que recibió el grafo. Copia también cada valor nuevo;
    copiar solo base no separaría los objetos que llegan en resultado.
    No escribe ni reanuda checkpoints. Conserva campos de presentación de base.
    """
    nuevo = deepcopy(base) if base is not None else initial_state("")
    for clave in AgentState.__annotations__:
        if clave in resultado:
            nuevo[clave] = deepcopy(resultado[clave])
    return nuevo

def plan_is_ready(state: AgentState) -> bool:
    """Guardia del router: requiere respuesta y al menos una viñeta real.

    No comprueba la fidelidad de la respuesta a las fuentes. Esa evaluación
    corresponde al contrato y a las pruebas de síntesis de la implementación real.
    """
    answer = state.get("final_answer")
    plan = state.get("plan")
    return (
        isinstance(answer, str) and bool(answer.strip())
        and isinstance(plan, list) and bool(plan)
        and all(isinstance(item, str) and bool(item.strip()) for item in plan)
    )
