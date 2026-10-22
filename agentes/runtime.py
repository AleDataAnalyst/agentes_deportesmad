"""Conexión explícita de especialistas al grafo supervisor síncrono."""

from agentes.agent import AgentService
from agentes.contracts import ToolResult
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.nodes.vision import vision_node
from agentes.settings import AgentSettings


def _instalaciones_no_disponibles(state):
    """Límite del montaje mientras Miguel no publique su nodo ejecutable.

    No implementa el especialista: comunica su ausencia al supervisor con el
    contrato común, sin consultar herramientas ni fabricar datos de catálogo.
    """
    limitation = (
        "Instalaciones no disponibles: falta una operación pública ejecutable "
        "del especialista. Catálogo, avisos y comparación no están conectados."
    )
    return {
        "specialist_results": {
            **state.get("specialist_results", {}),
            "instalaciones": ToolResult(
                status="abstained", answer=limitation,
                data={"available": False, "limitaciones": [limitation]},
            ),
        },
        "debug_trace": ["instalaciones: no disponible"],
    }


def crear_servicio_real(*, settings: AgentSettings | None = None) -> AgentService:
    from agentes.grafo_documental import obtener_grafo_documental

    documental = obtener_grafo_documental()

    return AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=documental.invoke
        ),
        instalaciones_node=_instalaciones_no_disponibles,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar,
        vision_node=vision_node,
        settings=settings,
    )

def crear_servicio(*, modo: str = "real") -> AgentService:
    """Selecciona el modo pedido; un fallo real nunca activa la demo."""
    if modo == "real":
        return crear_servicio_real()
    if modo == "demo":
        from agentes.demo import crear_servicio_demo
        return crear_servicio_demo()
    raise ValueError("modo debe ser real o demo")
