from agentes.contracts import Evidence, ToolResult
from agentes.state import AgentState


def vision_node(state: AgentState) -> dict:
    # Import diferido: construir el servicio no debe cargar rag.config.
    from agentes.tools.vision import imagen_preguntar

    pregunta = state.get("user_message", "")
    image_id = state.get("image_id") or "assets/imagen_demo.jpg"

    try:
        observacion = imagen_preguntar.invoke(
            {"image_id": image_id, "pregunta": pregunta}
        )
    except Exception as exc:
        observacion = {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error ejecutando visión: {exc}",
        }

    if not isinstance(observacion, dict):
        observacion = {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": "La tool de visión devolvió un formato inválido",
        }

    error = observacion.get("error")
    abstained = bool(observacion.get("abstained"))
    respuesta = str(observacion.get("resultado") or "")

    if error:
        status = "error"
    elif abstained or not respuesta.strip():
        status = "abstained"
    else:
        status = "ok"

    fuentes = observacion.get("fuentes") or []
    evidence = [
        Evidence(source=str(fuente), content="")
        for fuente in fuentes
        if isinstance(fuente, str)
    ]

    result = ToolResult(
        status=status,
        answer=respuesta,
        evidence=evidence,
        error=str(error) if error else None,
        data=observacion,
    )

    specialist_results = dict(state.get("specialist_results", {}))
    specialist_results["vision"] = result

    return {
        "specialist_results": specialist_results,
        "debug_trace": [f"vision: {status}"],
    }