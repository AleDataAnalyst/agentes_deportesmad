
"""
Nodo especialista de instalaciones y avisos.

Responsabilidad:
    - Leer `user_message` del AgentState para decidir modo y centro.
    - Llamar a `consultar_instalaciones` (modo catalogo o avisos).
    - Consultar `hora_actual` en Europe/Madrid ante petición explícita del presente;
      conservar su contrato en data sin inferir apertura de los centros.
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
from copy import deepcopy
from typing import Any

from agentes.contracts import Evidence, ToolResult
from agentes.tools.auxiliares import hora_actual
from agentes.tools.externa import (
    ToolResultInstalaciones,
    _fecha_actual_iso,
    consultar_instalaciones,
    resolver_centro_por_nombre,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "consultar_instalaciones"

# Solo referencias explícitas al presente; «horarios» o «abierto» no bastan.
_PETICION_TEMPORAL = re.compile(
    r"\b(?:hoy|ahora)\b|\b(?:hora|fecha|dia)\s+actual\b|"
    r"\bque\s+(?:hora|fecha|dia)\s+es\b"
)

# Un PK de centro es un número de 6 dígitos que NO empieza por 28 (CP Madrid)
# y NO es un año (19xx / 20xx). Aceptamos también "centro 114782" / "PK 114782"
# como identificador explícito.
_PATRON_PK_EXPLICITO = re.compile(
    r"(?:centro|pk|identificador|id)\s*[:#]?\s*(\d{5,12})\b",
    re.IGNORECASE,
)
_PATRON_NUMERO_SUELTO = re.compile(r"\b(\d{5,12})\b")

# Palabras que sugieren consultar avisos frente a listar el catálogo.
# Se normalizan las tildes antes de comprobarlas.
_PALABRAS_AVISO = (
    "aviso",
    "avisa",
    "incidencia",
    "cierre",
    "cerrado",
    "obra",
    "obras",
    "suspension",
    "suspendido",
    "piscina cerrada",
)


def _normalizar_texto(texto: str) -> str:
    """Normaliza texto para detectar palabras sin distinguir mayúsculas ni tildes."""
    import unicodedata

    texto = (texto or "").casefold()
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


def _es_ano_o_cp(numero: str) -> bool:
    """Descarta años (19xx/20xx) y códigos postales de Madrid (28xxx)."""
    if len(numero) == 4 and numero[:2] in {"19", "20"}:
        return True
    if len(numero) == 5 and numero.startswith("28"):
        return True
    return False


def _decidir_consulta(user_message: str) -> tuple[str, str | None, bool]:
    """
    Decide (modo, centro_id, requiere_aclaracion).

    Reglas:
        - Identificador explícito ("centro 114782", "PK 114782"): avisos con centro.
        - Número suelto que no sea año ni CP: avisos con centro (candidato).
        - Palabras de aviso sin centro: avisos sin centro → aclaración.
        - En cualquier otro caso: catálogo.
    """
    texto = (user_message or "").strip()
    if not texto:
        return ("catalogo", None, False)

    explicito = _PATRON_PK_EXPLICITO.search(texto)
    if explicito:
        candidato = explicito.group(1)
        if not _es_ano_o_cp(candidato):
            return ("avisos", candidato, False)

    texto_normalizado = _normalizar_texto(texto)      # ← al nivel de la función
    if any(
        re.search(rf"\b{re.escape(palabra)}\b", texto_normalizado)
        for palabra in _PALABRAS_AVISO
    ):
        
        # Hay intención de avisos pero no hay centro resoluble por número.
        suelto = _PATRON_NUMERO_SUELTO.search(texto)
        if suelto and not _es_ano_o_cp(suelto.group(1)):
            return ("avisos", suelto.group(1), False)

        # NUEVO: intentar resolver el centro por nombre contra el catálogo.
        coincidencias = resolver_centro_por_nombre(texto)
        if len(coincidencias) == 1:
            pk = str(coincidencias[0].get("pk") or "").strip()
            if pk:
                return ("avisos", pk, False)

        return ("avisos", None, True)

    return ("catalogo", None, False)

def _construir_answer(
    modo: str,
    datos: list[dict[str, Any]],
    advertencias: list[str],
) -> str:
    """Genera un texto legible para el nodo que sintetiza la respuesta."""
    if not datos:
        base = (
            "No se han encontrado resultados en la consulta del "
            f"{'catálogo' if modo == 'catalogo' else 'estado de los avisos'}."
        )
        if advertencias:
            base += " " + " ".join(advertencias)
        return base

    if modo == "catalogo":
        registros = [
            dato for dato in datos
            if isinstance(dato, dict)
        ]
        n = len(registros)

        primeros = ", ".join(
            f"{dato.get('nombre') or 'Nombre no disponible'} "
            f"({dato.get('distrito') or 'Distrito no disponible'})"
            for dato in registros[:5]
        )

        texto = (
            f"Catálogo: {n} centros registrados en el catálogo."
        )
        if primeros:
            texto += f" Primeros resultados: {primeros}."
        if n > 5:
            texto += f" Y {n - 5} centros más."
        if advertencias:
            texto += " Advertencias: " + " ".join(advertencias)
        return texto

    # Modo avisos.
    detectados = [
        dato for dato in datos
        if isinstance(dato, dict)
        and dato.get("aviso_detectado") is True
    ]
    sin_aviso = [
        dato for dato in datos
        if isinstance(dato, dict)
        and dato.get("aviso_detectado") is False
    ]
    no_verificables = [
        dato for dato in datos
        if isinstance(dato, dict)
        and dato.get("aviso_detectado") is None
    ]

    partes: list[str] = []

    if detectados:
        textos = [
            str(dato.get("texto_aviso") or "").strip()
            for dato in detectados
        ]
        textos = [texto for texto in textos if texto]
        if textos:
            partes.append(
                f"Avisos detectados ({len(detectados)}): "
                + " | ".join(textos)
            )
        else:
            partes.append(
                f"Se han detectado avisos en {len(detectados)} "
                "registro(s), pero no hay texto disponible."
            )

    if sin_aviso:
        partes.append(
            f"{len(sin_aviso)} centro(s) consultado(s) sin encabezado "
            "de aviso en la fuente revisada. Esto no garantiza la ausencia "
            "de incidencias."
        )

    if no_verificables:
        partes.append(
            f"No se pudo verificar el estado de los avisos de "
            f"{len(no_verificables)} centro(s)."
        )

    if advertencias:
        partes.append("Advertencias: " + " ".join(advertencias))

    return " ".join(partes) if partes else "Sin resultados."


def _construir_evidence(
    modo: str,
    datos: list[dict[str, Any]],
) -> list[Evidence]:
    """Convierte los datos de la herramienta en evidencias del contrato."""
    evidence: list[Evidence] = []

    # En catálogo limitamos la evidencia para no inflar el contexto de síntesis.
    items = datos[:10] if modo == "catalogo" else datos

    for item in items:
        if not isinstance(item, dict):
            continue

        if modo == "catalogo":
            pk = item.get("pk")
            nombre = item.get("nombre") or "Nombre no disponible"
            distrito = item.get("distrito") or "Distrito no disponible"
            url = item.get("content_url") or ""

            evidence.append(
                Evidence(
                    source=url,
                    content=f"{nombre} ({distrito})",
                    score=None,
                    metadata={
                        "pk": pk,
                        "distrito": distrito,
                    },
                )
            )
        else:
            centro_id = item.get("centro_id")
            texto = item.get("texto_aviso") or ""
            url = item.get("url_ficha") or ""

            evidence.append(
                Evidence(
                    source=url,
                    content=str(texto),
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
    ok = bool(resultado.get("ok"))
    modo = str(resultado.get("modo", "catalogo"))
    datos = resultado.get("datos") or []
    advertencias = list(resultado.get("advertencias") or [])
    error = resultado.get("error")
    requiere_aclaracion = bool(resultado.get("requiere_aclaracion"))

    if requiere_aclaracion:
        # Consulta incompleta pero no es un fallo: pedimos aclaración.
        status = "abstained"
        answer = (
            "Para consultar los avisos necesito el identificador del centro "
            "(por ejemplo, 114782). Indícamelo y repito la consulta."
        )
        return ToolResult(
            status=status,
            answer=answer,
            evidence=[],
            error=None,
            data={
                "modo": modo,
                "origen": resultado.get("origen"),
                "fuente": resultado.get("fuente"),
                "fecha_consulta": resultado.get("fecha_consulta"),
                "fecha_captura_fallback": resultado.get(
                    "fecha_captura_fallback"
                ),
                "advertencias": advertencias,
                "n_resultados": 0,
                "requiere_aclaracion": True,
            },
        )

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
    }
    # Solo adjuntamos los datos completos en avisos o en catálogos pequeños;
    # en catálogo grande la síntesis no los necesita.
    if modo == "avisos" or len(datos) <= 10:
        data["datos_raw"] = datos

    return ToolResult(
        status=status,
        answer=answer,
        evidence=evidence,
        error=error,
        data=data,
    )


def nodo_instalaciones(state: dict[str, Any]) -> dict[str, Any]:
    user_message = state.get("user_message") or ""
    modo, centro_id, requiere_aclaracion = _decidir_consulta(user_message)

    if requiere_aclaracion:
        # No llamamos a la tool: pedimos aclaración directamente.
        resultado: ToolResultInstalaciones = {
            "ok": False,
            "modo": "avisos",
            "datos": [],
            "fuente": "",
            "origen": "api",
            "fecha_consulta": _fecha_actual_iso(),
            "fecha_captura_fallback": None,
            "advertencias": [],
            "error": (
                "Necesito el identificador del centro para consultar avisos."
            ),
            "requiere_aclaracion": True,
        }
    else:
        try:
            resultado = consultar_instalaciones(
                modo=modo, centro_id=centro_id,
            )
        except Exception:
            logger.exception(
                "Fallo inesperado en la herramienta de instalaciones"
            )
            resultado = {
                "ok": False,
                "modo": modo,
                "datos": [],
                "fuente": "",
                "origen": "api",
                "fecha_consulta": _fecha_actual_iso(),
                "fecha_captura_fallback": None,
                "advertencias": [],
                "error": (
                    "No se pudo completar la consulta de instalaciones. "
                    "Inténtalo de nuevo más tarde."
                ),
                "requiere_aclaracion": False,
            }

    tool_result = _mapear_a_tool_result(resultado)

    previos = dict(state.get("specialist_results") or {})
    nuevos = dict(previos)
    nuevos["instalaciones"] = tool_result

    evento = (
        f"instalaciones: modo={modo} "
        f"centro_id={centro_id or '-'} "
        f"status={tool_result.status} "
        f"n={tool_result.data.get('n_resultados', 0)} "
        f"origen={tool_result.data.get('origen')}"
    )
    if tool_result.status == "error":
        evento += " error=consulta_no_completada"

    eventos = [evento]
    if _PETICION_TEMPORAL.search(_normalizar_texto(user_message)):
        try:
            reloj = hora_actual(zona="Europe/Madrid")
            if (
                not isinstance(reloj, dict)
                or type(reloj.get("ok")) is not bool
                or type(reloj.get("abstained")) is not bool
                or not isinstance(reloj.get("fuentes"), list)
                or not all(isinstance(f, str) for f in reloj["fuentes"])
                or (reloj.get("error") is not None
                    and not isinstance(reloj["error"], str))
            ):
                raise ValueError("Contrato del reloj inválido")
            if reloj["ok"] and not reloj["error"] and not reloj["abstained"]:
                if not isinstance(reloj.get("resultado"), dict) or not all(
                    isinstance(reloj["resultado"].get(campo), str)
                    and reloj["resultado"][campo]
                    for campo in ("iso", "fecha", "hora", "dia_semana", "zona")
                ):
                    raise ValueError("Resultado del reloj inválido")
        except Exception:  # El reloj no invalida el resultado municipal.
            reloj = {
                "ok": False, "resultado": None, "fuentes": [],
                "abstained": False, "error": "No se pudo consultar el reloj.",
            }
        tool_result.data["hora_actual"] = deepcopy(reloj)
        reloj_ok = (
            reloj.get("ok") is True and not reloj.get("error")
            and not reloj.get("abstained")
        )
        if not reloj_ok:
            tool_result.data["advertencias"].append(
                "Hora actual no disponible; no se ha podido verificar el reloj."
            )
        eventos.append(
            "instalaciones.tool: hora_actual zona=Europe/Madrid "
            f"status={'ok' if reloj_ok else 'error'}"
        )

    return {
        "specialist_results": nuevos,
        "debug_trace": eventos,
    }
