"""Síntesis determinista y guardia compatible con la inyección del grafo.

No ejecuta especialistas ni modelos. sintetizar es la implementación concreta;
sintetizar_node conserva la guardia existente para cualquier implementación.
"""

from collections.abc import Callable
import json

from agentes.contracts import SPECIALIST_NAMES, ToolResult
from agentes.state import AgentState, plan_is_ready


def _texto(value) -> str:
    """Presenta solo datos recibidos, sin completar fechas ni procedencias."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(_texto(item) for item in value)
    return json.dumps(value, ensure_ascii=False, default=str)


def _notas(data: dict) -> list[str]:
    """Extrae restricciones y procedencia conocidas del contrato provisional.

    El sobre completo permanece en specialist_results; no se vuelcan argumentos
    internos de tools en el texto del usuario. Admite los nombres documentales
    actuales y las advertencias/procedencia propuestas para instalaciones.
    """
    lines = []
    if data.get("fallback") or data.get("origen") == "fallback":
        lines.append("Fallback histórico: no acredita condiciones actuales.")
    labels = {
        "warnings": "Advertencias", "advertencias": "Advertencias",
        "errores": "Errores", "errors": "Errores",
        "limitaciones": "Limitaciones", "limitations": "Limitaciones",
        "origen": "Origen", "fecha_consulta": "Fecha de consulta",
        "fecha_captura_fallback": "Fecha de captura histórica",
        "fecha_captura": "Fecha de captura", "captured_at": "Fecha de captura",
    }
    for key, label in labels.items():
        value = data.get(key)
        if value is not None and value != [] and value != "":
            lines.append(f"{label}: {_texto(value)}")
    return lines


def sintetizar(state: AgentState) -> dict:
    """Redacta un borrador informativo con resultados del pedido vigente.

    Los resultados operativos se reinician por pedido en AgentService. Un rol
    ausente se distingue de abstención/error; solo un ok con texto y sin señales
    de fallo se presenta como útil. El texto parcial de un fallo se etiqueta y
    nunca justifica una conclusión afirmativa. No modifica resultados ni evidencia.
    """
    if state.get("approved") is not None or state.get("done", False) is not False:
        raise ValueError("SYNTHESIS_CONTRACT: el pedido debe estar pendiente y sin cerrar")
    lines = [f"Consulta: {state.get('user_message', '')}"]
    results = state.get("specialist_results", {})
    useful = 0
    for role in SPECIALIST_NAMES:
        result = results.get(role)
        if result is None:
            lines.append(f"{role}: sin resultado; especialista todavía no consultado.")
            continue
        if not isinstance(result, ToolResult) or result.status not in ("ok", "abstained", "error"):
            raise ValueError("SYNTHESIS_CONTRACT: resultado de especialista incompatible")
        failed = (result.status == "error" or bool(result.error)
                  or bool(result.data.get("errores")) or bool(result.data.get("errors")))
        abstained = result.status == "abstained" or bool(result.data.get("abstained"))
        if failed:
            lines.append(f"{role}: error; no permite una conclusión confirmada.")
        elif abstained:
            lines.append(f"{role}: abstención; sin respuesta fundada.")
        elif not result.answer.strip():
            lines.append(f"{role}: sin contenido útil disponible.")
        else:
            useful += 1
            lines.append(f"{role}: resultado disponible.")
        if result.answer.strip():
            label = "Contenido declarado, no confirmado" if failed or abstained else "Respuesta"
            lines.append(f"{label}: {result.answer}")
        if result.error:
            lines.append(f"Error: {result.error}")
        if result.data.get("abstained"):
            lines.append("Abstención declarada por el especialista.")
        lines.extend(_notas(result.data))
        if not result.evidence:
            lines.append("Limitación: sin fuentes aportadas; fundamento no verificado.")
        for evidence in result.evidence:
            lines.append(f"Fuente: {evidence.source}")
            if evidence.content:
                lines.append(f"Fragmento aportado: {evidence.content}")
            lines.extend(_notas(evidence.metadata))
    if useful == len(SPECIALIST_NAMES):
        lines.append("Resultados disponibles de ambos especialistas; revisar fuentes y limitaciones antes de aceptar.")
    elif useful:
        lines.append("Respuesta parcial: quedan datos sin confirmar; no se completan con suposiciones.")
    else:
        lines.append("No hay resultados útiles para responder con fundamento a esta consulta.")
    plan = ["Revisar qué fuentes y limitaciones se han aportado para esta consulta."]
    if useful < len(SPECIALIST_NAMES):
        plan.extend([
            "Aportar el documento o identificar el centro y el dato que falta por confirmar.",
            "Reformular la consulta con esa información para obtener una respuesta verificable.",
        ])
    else:
        plan.append("Revisar por separado las respuestas; confirmar su vigencia y cualquier discrepancia.")
    return {"final_answer": "\n".join(lines), "plan": plan,
            "done": False, "approved": None,
            "debug_trace": [f"síntesis: {useful} de {len(SPECIALIST_NAMES)} resultados útiles"]}


def sintetizar_node(
    state: AgentState, *, node: Callable[[AgentState], dict],
) -> dict:
    """Valida la implementación inyectada sin aprobar ni cerrar el pedido.

    La implementación recibe el estado y devuelve una actualización parcial
    con final_answer y plan no vacíos. Debe conservar la procedencia y las
    limitaciones al redactar; esta guardia solo comprueba la estructura mínima.
    Las excepciones se propagan: no se sustituye un fallo por datos simulados.
    """
    if state.get("approved") is not None or state.get("done", False) is not False:
        raise ValueError("SYNTHESIS_CONTRACT: el pedido debe estar pendiente y sin cerrar")
    update = node(state)
    if (not isinstance(update, dict)
            or "final_answer" not in update or "plan" not in update
            or not plan_is_ready({**state, **update})):
        raise ValueError("SYNTHESIS_CONTRACT: sintetizar debe devolver final_answer y plan no vacios")
    if update.get("approved") is not None or update.get("done", False) is not False:
        raise ValueError("SYNTHESIS_CONTRACT: la sintesis no puede aprobar ni cerrar el pedido")
    return update
