"""Conexión explícita de especialistas al grafo supervisor síncrono."""

from pathlib import Path

from dotenv import load_dotenv

from agentes.agent import AgentService
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar
from agentes.nodes.supervisor import RouteProvider
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings


def crear_servicio_real(
    *, settings: AgentSettings | None = None, route_provider: RouteProvider | None = None,
) -> AgentService:
    """Carga configuración y monta el proveedor y especialistas sin consultarlos."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    from agentes.nodes.vision import vision_node
    from agentes.nodes.instalaciones import nodo_instalaciones
    from agentes.supervisor_llm_real import crear_proveedor_configurado

    if route_provider is None:
        route_provider = crear_proveedor_configurado()

    def ejecutar_documental(state):
        # La puerta pública importa el RAG: diferir hasta la consulta evita
        # abrir Chroma o cargar embeddings durante la construcción del servicio.
        from agentes.grafo_documental import obtener_grafo_documental
        return obtener_grafo_documental().invoke(state)

    return AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=ejecutar_documental
        ),
        instalaciones_node=nodo_instalaciones,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar,
        vision_node=vision_node,
        route_provider=route_provider,
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
