"""Estado de conversación, pedido y ejecución del grafo.

Campos previstos: thread_id, request_id, message, image_id, messages, results,
visited, iterations, next_node, trace, answer, plan, plan_id, sources,
limitations, decision, phase, done, error y modo de ejecución.
Documentar quién actualiza cada campo y si reemplaza, fusiona o acumula.
Cada pedido reinicia resultados, plan, decisión y contadores; conserva solo
historial conversacional acotado. Evitar evidencias de pedidos anteriores.
En el diseño concurrente, las ramas trabajan sobre copias y el coordinador
combina sus resultados; no introducir reducers sin definir su semántica.

Decisión temporal:
- Usamos un dict tipado con TypedDict porque LangGraph suele trabajar bien con
  estados tipo diccionario.
- Los campos opcionales permiten avanzar con mocks mientras falta el RAG real.
"""

from typing import TypedDict
from agentes.contracts import PendingAction, SupervisorDecision, ToolResult

class AgentState(TypedDict, total=False):
    """Estado mínimo para la rama `feature/supervisor_grafo`."""
    
    user_message: str
    thread_id: str
    supervisor_decision: SupervisorDecision
    specialist_results: dict[str, ToolResult]
    final_answer: str
    pending_action: PendingAction | None
    approved: bool | None
    debug_trace: list[str]
    
def initial_state(user_message: str, thread_id: str = "demo") -> AgentState:
    """Crea el estado inicial de una conversación.
    
    Esta función ayuda a probar el grafo desde CLI sin depender todavía de
    Streamlit ni de MemorySaver.
    """
    
    return {
        "user_message": user_message,
        "thread_id": thread_id,
        "specialist_results": {},
        "pending_action": None,
        "approved": None,
        "debug_trace": ["estado inicial creado"],
    }