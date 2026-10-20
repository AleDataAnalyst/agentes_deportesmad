"""Adaptación optativa del especialista documental al nodo del grafo principal.

La ejecución se recibe como callable explícito; importar este módulo no carga
el RAG. El montaje real de agentes.runtime pasa invoke desde la puerta pública
obtener_grafo_documental. El adaptador conserva separados ambos contratos.
"""

from copy import deepcopy
from collections.abc import Callable
from uuid import uuid4

from agentes.contracts import Evidence, ToolResult
from agentes.state import AgentState


def crear_adaptador_documental(
    *, ejecutar_documental: Callable[[dict], dict], contexto_permitido=None, image_id=None,
    presupuesto_tools=4, preparar_borrador=False,
):
    """Devuelve un Node síncrono para inyectar en build_graph o AgentService.

    Las opciones son explícitas del montaje, no campos nuevos de AgentState.
    El contrato común aún no transporta imágenes ni contexto por turno. La
    ejecución inyectada recibe el contrato documental y devuelve su patch; es
    obligatoria para no decidir aquí la puerta pública ni cargar especialistas.
    El identificador se genera por invocación: thread_id identifica conversación,
    no pedido. No se comparte el checkpoint/HITL del supervisor con el componente.
    """
    if not callable(ejecutar_documental):
        raise TypeError("ejecutar_documental debe ser callable")
    if type(presupuesto_tools) is not int or presupuesto_tools < 1:
        raise ValueError("presupuesto_tools debe ser un entero positivo")
    if type(preparar_borrador) is not bool:
        raise TypeError("preparar_borrador debe ser bool")
    if contexto_permitido is not None and (
        not isinstance(contexto_permitido, list)
        or not all(isinstance(item, str) for item in contexto_permitido)
    ):
        raise TypeError("contexto_permitido debe ser list[str] o None")
    if image_id is not None and not isinstance(image_id, str):
        raise TypeError("image_id debe ser str o None")
    options = deepcopy({
        "contexto_permitido": contexto_permitido, "image_id": image_id,
        "presupuesto_tools": presupuesto_tools,
        "preparar_borrador": preparar_borrador,
    })

    def documental_node(state: AgentState) -> dict:
        """Traduce el pedido y conserva el sobre sin mutar ninguna entrada.

        Errores declarados prevalecen sobre abstención y éxito; una respuesta
        parcial permanece en answer y en data aunque el estado sea error. Una
        fuente sin fragmento se representa con content vacío, sin datos inventados.
        Salidas mal formadas o de otro pedido fallan como errores de integración.
        """
        message = state.get("user_message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("DOCUMENTAL_INPUT: user_message debe ser texto no vacío")
        request_id = uuid4().hex
        output = ejecutar_documental({
            **deepcopy(options), "request_id": request_id, "pedido": message,
        })
        payload = output.get("documental") if isinstance(output, dict) else None
        if not isinstance(payload, dict) or payload.get("request_id") != request_id:
            raise ValueError("DOCUMENTAL_CONTRACT: falta documental o request_id no coincide")
        if (not isinstance(payload.get("resultado"), str)
                or type(payload.get("abstained")) is not bool
                or any(not isinstance(payload.get(key), list)
                       or not all(isinstance(item, str) for item in payload[key])
                       for key in ("fuentes", "errores", "limitaciones"))
                or not isinstance(payload.get("eventos"), list)
                or not all(isinstance(item, dict) for item in payload["eventos"])):
            raise ValueError("DOCUMENTAL_CONTRACT: sobre documental mal formado")
        data = deepcopy(payload)
        status = ("error" if data["errores"] else "abstained"
                  if data["abstained"] or not data["resultado"].strip() else "ok")
        result = ToolResult(
            status=status, answer=data["resultado"],
            evidence=[Evidence(source=source, content="") for source in data["fuentes"]],
            error="; ".join(data["errores"]) if data["errores"] else None,
            data=data,
        )
        return {
            "specialist_results": {
                **deepcopy(state.get("specialist_results", {})), "documental": result,
            },
            "debug_trace": [f"documental: {status}"],
        }

    return documental_node
