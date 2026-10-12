"""Contratos compartidos del supervisor y del grafo.

Este módulo define estructuras simples para que el resto del proyecto
hable el mismo idioma aunque todavía falte conectar el RAG real.

Decisión temporal:
- Usamos dataclasses de Python estándar para aprender el flujo
  sin añadir complejidad de Pydantic al principio.
- Cuando el contrato esté estable, se puede migrar a Pydantic
  si el equipo quiere validación más estricta.
  
Pendiente de acordar con Héctor:
- Confirmar el formato final de la respuesta del RAG.
- Confirmar si `evidence` incluirá score, fuente, chunk y metadatos.
- Confirmar cómo indicará el RAG que no tiene evidencia suficiente.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

SpecialistName = Literal["documental", "instalaciones", "planificador", "desconocido"]

ToolStatus = Literal["ok", "abstained", "error"]

@dataclass
class Evidence: 
    """Fragmento de evidencia que justifica una respuesta.
    
    En RAG, esto debería venir de los chunks recuperados.
    En API externa, puede venir de una URL, dataset o fallback local.
    """

source: str
content: str
score: float | None = None
metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolResult:
    """Resultado normalizado de una tool o especialista.
    la clave para integrar bien es que todos devuelvaan algo parecido:
    respuesta, estado, evidencias y error opcional.
    """
    
status: ToolStatus
answer: str
evidence: list[Evidence] = field(default_factory=list)
error: str | None = None
data: dict[str, Any] = field(default_factory=dict)

@dataclass
class SupervisorDecision:
    """Decisión del supervisor sobre qué especialista debe actuar.
    
    Esta decisión puede salir de reglas simples mientras `llm.py` no esté listo.
    Más adelante puede salir de un LLM con salida estructurada.
    """
    
    specialist: SpecialistName
    reason: str
    needs_approval: bool = False

@dataclass
class PendingAction:
    """Acción que requiere aprobación humana antes de ejecutarse.
    
    Sirve para HITL: el sistemaa propone, la persona aprueba o rechaza.
    """
    
    action_type: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict) 