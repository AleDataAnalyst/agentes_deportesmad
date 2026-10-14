"""Contratos internos del supervisor y propuesta de resultados del grafo.

SpecialistName y RouteName corresponden al montaje síncrono actual. Evidence,
ToolResult y PendingAction son formatos internos provisionales: no fijan la
entrada ni la salida pública de los especialistas, del RAG o de la API.
Cuando lleguen esas interfaces, adaptar sus salidas en el límite de integración
y revisar sus consumidores. No exigir a los especialistas rehacer sus módulos.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, get_args

SpecialistName = Literal["documental", "instalaciones"]
# Un especialista es un rol; sintetizar y FINISH son decisiones de flujo.
RouteName = Literal["documental", "instalaciones", "sintetizar", "FINISH"]
ToolStatus = Literal["ok", "abstained", "error"]

# Derivados de los tipos: supervisor y grafo comparten los mismos nombres.
# aplicar es un destino del router, no una propuesta del supervisor:
# FINISH conduce a aplicar únicamente cuando existe un plan válido.
SPECIALIST_NAMES: tuple[SpecialistName, ...] = get_args(SpecialistName)
ROUTE_NAMES: tuple[RouteName, ...] = get_args(RouteName)


@dataclass
class Evidence:
    """Evidencia interna propuesta; sus campos deben revisarse con el RAG.

    score es opcional y no presupone rango, escala ni comparabilidad entre
    fuentes. metadata permite conservar la procedencia disponible sin exigir
    claves que los especialistas todavía no han confirmado.

    default_factory crea un diccionario nuevo para cada instancia. Evita que
    dos evidencias compartan metadatos por accidente.
    """

    source: str
    content: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Resultado interno provisional de un intento de tool o especialista.

    ok indica respuesta disponible; abstained, falta de respuesta fundada;
    error, fallo técnico. answer puede estar vacío en abstención o error.
    evidence conserva fuentes y data los datos adicionales disponibles. La
    ausencia de evidence no demuestra que una respuesta esté fundamentada.
    No se impone todavía la forma de consulta ni de actualización de un nodo.

    Un resultado error/abstained también cuenta como intento completado: el
    supervisor no debe repetir la consulta indefinidamente por falta de datos.
    Las dataclasses y Literal no validan valores en ejecución por sí solos.
    La validación del adaptador se acordará con las interfaces reales.
    """

    status: ToolStatus
    answer: str
    evidence: list[Evidence] = field(default_factory=list)
    error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class SupervisorDecision:
    """Propuesta interna; el supervisor valida la ruta o usa su fallback.

    Se conserva specialist para no renombrar todos los consumidores de golpe,
    aunque también admite sintetizar y FINISH. FINISH solicita avanzar al
    cierre; no equivale a END ni a done=True. needs_approval se conserva
    por compatibilidad; el grafo actual lo ignora. No es una decisión humana
    y no controla el breakpoint: approved pertenece a la decisión del cliente.
    TODO equipo: acordar si se renombra specialist a next_node y se retira
    needs_approval cuando se revisen todos los consumidores.
    """

    specialist: RouteName
    reason: str
    needs_approval: bool = False


@dataclass
class PendingAction:
    """Propuesta interna opcional; no sustituye al plan ni a approved.

    Los tipos de acción y el payload siguen pendientes de acuerdo. Su presencia
    no ejecuta reservas, pagos ni envíos y no activa por sí sola la pausa HITL.
    """

    action_type: str
    description: str
    payload: dict[str, Any] = field(default_factory=dict)
