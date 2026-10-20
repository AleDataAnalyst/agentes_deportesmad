"""
Nodo especialista de instalaciones y avisos.

Responsabilidad:
    - Leer `user_message` del AgentState para decidir modo y centro.
    - Llamar a `consultar_instalaciones` (modo catalogo o avisos).
    - Traducir el ToolResultInstalaciones al contrato compartido ToolResult
      (status, answer, evidence, error, data).
    - Añadir el resultado en `specialist_results["instalaciones"]`
      conservando los demás especialistas.
    - Añadir solo eventos nuevos (strings) a `debug_trace`.

No toca: plan, final_answer, pending_action, approved, done, iterations,
supervisor_decision. Esos campos los gestionan supervisor, sintetizar y aplicar.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agentes.contracts import Evidence, ToolResult
from agentes.tools.externa import (
    ToolResultInstalaciones,
    consultar_instalaciones,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "consultar_instalaciones"

# Patrón para detectar un PK de centro en el mensaje del usuario.
_PATRON_PK = re.compile(r"\b(\d{4,12})\b")

# Palabras que sugieren consultar avisos (frente a listar el catálogo).
_PALABRAS_AVISO = (
    "aviso", "avisa", "incidencia", "cierre", "cerrado", "obra",
    "obras", "suspensión", "suspendido", "piscina cerrada",
)


def _decidir_consulta(user_message: str) -> tuple[str, str | None]:
    """
    Decide (modo, centro_id) a partir del mensaje del usuario.

    Reglas:
        - Si hay un PK explícito en el mensaje → modo="avisos".
        - Si hay palabras de aviso/incidencia → modo="avisos" (sin centro).
        - En cualquier otro caso → modo="catalogo".
    """
    texto = (user_message or "").strip()
    if not texto:
        return ("catalogo", None)

    m = _PATRON_PK.search(texto)
    if m:
        return ("avisos", m.group(1))

    minusculas = texto.casefold()
    if any(p in minusculas for p in _PALABRAS_AVISO):
        return ("avisos", None)

    return ("catalogo", None)


def _construir_answer(
    modo: str,
    datos: list[dict[str, Any]],
    advertencias: list[str],
) -> str:
    """Genera un texto legible para sintetizar a partir de los datos."""
    if not datos:
        base = (
            "No se han encontrado resultados en la consulta de "
            f"{'catálogo' if modo == 'catalogo' else 'avisos'}."
        )
        if advertencias:
            base += " " + " ".join(advertencias)
        return base

    if modo == "catalogo":
        n = len(datos)
        primeros = ", ".join(
            f"{d.get('nombre', '?')} ({d.get('distrito', '?')})"
            for d in datos[:5]
            if isinstance(d, dict)
        )
        texto = f"Catálogo: {n} centros disponibles. Primeros: {primeros}."
        if n > 5:
            texto += f" (y {n - 5} más)."
        if advertencias:
            texto += " Advertencias: " + " ".join(advertencias)
        return texto

    # modo avisos
    detectados = [d for d in datos if isinstance(d, dict) and d.get("aviso_detectado")]
    sin_aviso = [d for d in datos if isinstance(d, dict) and d.get("aviso_detectado") is False]
    no_verif = [d for d in datos if isinstance(d, dict) and d.get("aviso_detectado") is None]

    partes: list[str] = []
    if detectados:
        partes.append(
            f"Avisos detectados ({len(detectados)}): " + " | ".join(
                d.get("texto_aviso", "") for d in detectados
            )
        )
    if sin_aviso:
        partes.append(
            f"{len(sin_aviso)} centro(s) consultado(s) sin encabezado de aviso "
            "(no garantiza ausencia de incidencia)."
        )
    if no_verif:
        partes.append(
            f"{len(no_verif)} centro(s) no verificable(s) por fallo de consulta."
        )
    if advertencias:
        partes.append("Advertencias: " + " ".join(advertencias))
    return " ".join(partes) if partes else "Sin resultados."


def _construir_evidence(
    modo: str,
    datos: list[dict[str, Any]],
) -> list[Evidence]:
    """Convierte los datos de la tool en una lista de Evidence del contrato."""
    evidence: list[Evidence] = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        if modo == "catalogo":
            pk = item.get("pk")
            nombre = item.get("nombre", "")
            distrito = item.get("distrito", "")
            url = item.get("content_url", "")
            evidence.append(
                Evidence(
                    source=url,
                    content=f"{nombre} ({distrito})",
                    score=None,
                    metadata={"pk": pk, "distrito": distrito},
                )
            )
        else:
            centro_id = item.get("centro_id")
            texto = item.get("texto_aviso") or ""
            url = item.get("url_ficha", "")
            evidence.append(
                Evidence(
                    source=url,
                    content=texto,
                    score=None,
                    metadata={
                        "centro_id": centro_id,
                        "aviso_detectado": item.get("aviso_detectado"),
                        "origen": item.get("origen"),
                    },
                )
            )
    return evidence


def _mapear_a_tool_result(
    resultado: ToolResultInstalaciones,
) -> ToolResult:
    """
    Traduce el ToolResultInstalaciones al ToolResult del contrato compartido.

    - status: "ok" si hay datos; "abstained" si ok pero sin datos;
      "error" si ok=False.
    - answer: texto legible para sintetizar.
    - evidence: lista de Evidence con fuentes.
    - error: mensaje de error si lo hay.
    - data: campos extra (modo, origen, fechas, advertencias, datos_raw).
    """
    ok = bool(resultado.get("ok"))
    modo = str(resultado.get("modo", "catalogo"))
    datos = resultado.get("datos") or []
    advertencias = list(resultado.get("advertencias") or [])
    error = resultado.get("error")

    if not ok:
        status = "error"
    elif not datos:
        status = "abstained"
    else:
        status = "ok"

    answer = _construir_answer(modo, datos, advertencias)
    evidence = _construir_evidence(modo, datos)

    data = {
        "modo": modo,
        "origen": resultado.get("origen"),
        "fuente": resultado.get("fuente"),
        "fecha_consulta": resultado.get("fecha_consulta"),
        "fecha_captura_fallback": resultado.get("fecha_captura_fallback"),
        "advertencias": advertencias,
        "n_resultados": len(datos),
        "datos_raw": datos,
    }

    return ToolResult(
        status=status,
        answer=answer,
        evidence=evidence,
        error=error,
        data=data,
    )


def nodo_instalaciones(state: dict[str, Any]) -> dict[str, Any]:
    """
    Nodo especialista de instalaciones y avisos.

    Args:
        state: AgentState compartido (TypedDict, total=False).

    Returns:
        Patch parcial con:
            - specialist_results: copia de los previos + "instalaciones".
            - debug_trace: solo eventos nuevos (strings).
    """
    user_message = state.get("user_message") or ""
    modo, centro_id = _decidir_consulta(user_message)

    try:
        resultado = consultar_instalaciones(modo=modo, centro_id=centro_id)
    except Exception as exc:  # nunca debe tumbar el grafo
        logger.exception("Fallo inesperado en consultar_instalaciones")
        resultado = {
            "ok": False,
            "modo": modo,
            "datos": [],
            "fuente": "",
            "origen": "api",
            "fecha_consulta": "",
            "fecha_captura_fallback": None,
            "advertencias": [],
            "error": f"Excepción inesperada: {exc}",
        }

    tool_result = _mapear_a_tool_result(resultado)

    # Copia de specialist_results para no mutar el estado original.
    previos = dict(state.get("specialist_results") or {})
    nuevos = dict(previos)
    nuevos["instalaciones"] = tool_result

    # Evento de traza (string, no dict).
    evento = (
        f"instalaciones: modo={modo} centro_id={centro_id or '-'} "
        f"status={tool_result.status} n={tool_result.data.get('n_resultados', 0)} "
        f"origen={tool_result.data.get('origen')}"
    )
    if tool_result.error:
        evento += f" error={tool_result.error[:80]}"

    return {
        "specialist_results": nuevos,
        "debug_trace": [evento],
    }
