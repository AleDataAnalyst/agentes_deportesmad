"""Supervisor de enrutado y finalización de la fase de consultas.

Responsabilidad:
- Leer la petición del usuario.
- Decidir qué especialista debe intervenir.
- No ejecutar tools directamente.

Mientras `llm.py` no esté cerrado con Héctor, este supervisor usa reglas simples
por palabras clave. Eso permite probar el grafo sin bloquearse.

TODO cuando esté listo `llm.py`:
- Sustituir `decide_with_rules` por una llamada al LLM con salida estructurada.
- Mantener el mismo contrato `SupervisorDecision` para no romper el grafo.

Entradas: pedido, roles pendientes, resultados actuales y contadores.
Salidas: siguiente rol o síntesis, razón de ruta, contador y evento de traza.
Validar propuesta del modelo y aplicar fallback determinista en Python.
No repetir indefinidamente especialistas ni permitir nombres desconocidos.
Puede autorizar consultas independientes en paralelo; no establece done por sí solo.
Dependencias: modelo, estado, contratos y límites de configuración.
"""

from agentes.contracts import SupervisorDecision
from agentes.state import AgentState

def decide_with_rules(message: str) -> SupervisorDecision:
    """Decide especialista con reglas simples y explicables.
    
    Esto no pretende ser inteligente todavía; pretende desbloquear la integración.
    """
    
    text = message.lower()
    
    if any(word in text for word in ["rag", "documento", "normativa", "requisito","fuente"]):
        return SupervisorDecision(
            specialist="documental",
            reason="La consulta parece necesitar evidencia documental o RAG.",
        )
        
    if any(word in text for word in ["instalación", "polideportivo", "piscina", "actividad", "horario"]):
        return SupervisorDecision(
            specialist="documental",
            reason="La consulta parece necesitar datos de instalaciones o actividades.",
        )
        
    if any(word in text for word in ["plan", "agenda", "fisioterapia", "rutina"]):
        return SupervisorDecision(
            specialist="planificador",
            reason="La consulta parece pedir organización o planificación deportiva.",
            needs_approval=True,
        )
        
    return SupervisorDecision(
        specialist="desconocido",
        reason="No se detectó todavía un especialista claro.",
)
        
def supervisor_node(state: AgentState) -> AgentStaate:
    """Añade al estado la decisión del supervisor."""
    
    decision = decide_with_rules(state["user_message"])
    state["supervisor_decision"] = decision
    state.setdefault("debug_trace", []).append(f"supervisor -> {decision.specialist}: {decision.reason}")
    return state