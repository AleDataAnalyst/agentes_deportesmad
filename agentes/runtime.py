"""Montaje explícito compartido por CLI y Streamlit, sin consultas al construir."""

from agentes.agent import AgentService
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar
from agentes.nodes.instalaciones import instalaciones_no_disponibles
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings

REAL_NOTICE = (
    "SERVICIO REAL: documental conectado al RAG configurado; "
    "instalaciones no disponibles. Cierre informativo con aprobación humana."
)


def crear_servicio_real(*, settings: AgentSettings | None = None) -> AgentService:
    """Respeta la puerta pública documental y conserva el supervisor principal.

    Se pasa el método invoke, sin llamarlo: compilar no consulta documentos ni
    modelos. El adaptador traduce los contratos; las guardias de síntesis y
    aplicar ya pertenecen a build_graph y no se envuelven aquí otra vez.
    """
    from agentes.grafo_documental import obtener_grafo_documental

    documental = obtener_grafo_documental()
    return AgentService(
        documental_node=crear_adaptador_documental(
            ejecutar_documental=documental.invoke),
        instalaciones_node=instalaciones_no_disponibles,
        sintetizar_node=sintetizar,
        aplicar_node=aplicar,
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


def aviso_modo(modo: str) -> str:
    if modo == "real":
        return REAL_NOTICE
    if modo == "demo":
        from agentes.demo import DEMO_NOTICE
        return DEMO_NOTICE
    raise ValueError("modo debe ser real o demo")
