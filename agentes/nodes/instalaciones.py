
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

from agentes.especialista_llm import FalloPlanificacion, Herramienta, ejecutar_especialista, modo_especialistas
from agentes.tools.auxiliares import hora_actual

logger = logging.getLogger(__name__)

MAX_STEPS_INSTALACIONES = 3

PROMPT_INSTALACIONES = """Eres el especialista de instalaciones deportivas municipales de Madrid.
Decide qué herramientas necesitas para responder:
- consultar_instalaciones con modo "catalogo" para listar o buscar centros.
- consultar_instalaciones con modo "avisos" y el identificador del centro (centro_id)
  para incidencias, cierres u obras. Si no sabes el centro, no lo inventes.
- hora_actual si la pregunta depende de la fecha u hora de hoy.
Cuando tengas los datos, responde sin llamar a más herramientas."""

# Palabras que indican que la respuesta depende de la fecha u hora actual.
_PALABRAS_HORA = ("hora", "ahora", "hoy", "abierto", "abierta", "manana")

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


def _plan_llm(user_message: str) -> list[dict[str, Any]]:
    """El LLM propone consultar_instalaciones y hora_actual; Python las ejecuta."""
    herramientas = [
        Herramienta(
            TOOL_NAME, "Catálogo de centros deportivos municipales o avisos de un centro.",
            {"type": "object", "properties": {
                "modo": {"type": "string", "enum": ["catalogo", "avisos"]},
                "centro_id": {"type": "string"},
            }, "required": ["modo"]},
            consultar_instalaciones,
        ),
        Herramienta(
            "hora_actual", "Fecha y hora local actual en ISO 8601 con zona horaria.", 
            {"type": "object", "properties": {}}, hora_actual,
        ),
    ]
    return ejecutar_especialista(
        prompt_sistema=PROMPT_INSTALACIONES, mensaje=user_message,
        herramientas=herramientas, max_steps=MAX_STEPS_INSTALACIONES,
    )

def _hora_no_disponible() -> dict[str, Any]:
    return {
        "ok": False,
        "resultado": None,
        "fuentes": [],
        "abstained": False,
        "error": "Hora actual no disponible",
    }

def _hora_util(observacion: Any) -> bool:
    if not _hora_valida(observacion):
        return False

    return (
        observacion["ok"] is True
        and not observacion.get("error")
        and observacion["abstained"] is False
        and isinstance(observacion.get("resultado"), dict)
        and all(
            isinstance(observacion["resultado"].get(campo), str)
            and observacion["resultado"][campo]
            for campo in ("iso", "fecha", "hora", "dia_semana", "zona")
        )
    )

def _hora_valida(observacion: Any) -> bool:
    if not isinstance(observacion, dict):
        return False

    if (
        type(observacion.get("ok")) is not bool
        or type(observacion.get("abstained")) is not bool
        or not isinstance(observacion.get("fuentes"), list)
        or not all(isinstance(f, str) for f in observacion["fuentes"])
    ):
        return False

    error = observacion.get("error")
    if error is not None and not isinstance(error, str):
        return False

    if observacion["ok"] and not error and not observacion["abstained"]:
        resultado = observacion.get("resultado")
        if not isinstance(resultado, dict):
            return False

        return all(
            isinstance(resultado.get(campo), str) and resultado[campo]
            for campo in ("iso", "fecha", "hora", "dia_semana", "zona")
        )

    return True


def nodo_instalaciones(state: dict[str, Any]) -> dict[str, Any]:
    user_message = state.get("user_message") or ""
    texto_normalizado = _normalizar_texto(user_message)

    llamadas: list[dict[str, Any]] = []
    evento_hora: str | None = None

    if modo_especialistas() == "llm":
        try:
            llamadas = _plan_llm(user_message)
    
        except FalloPlanificacion as exc:
            # Conservar consultas y resultados anteriores al fallo.
            llamadas = exc.llamadas
            logger.warning(
                "Planificación LLM interrumpida; "
                "se conservan las llamadas realizadas"
            )
    
        except Exception:
            logger.exception(
                "Planificación LLM no disponible; se usan reglas"
            )
            llamadas = []    

    elif _PETICION_TEMPORAL.search(texto_normalizado):
        try:
            observacion = hora_actual(zona="Europe/Madrid")
        except Exception:
            observacion = _hora_no_disponible()

        llamadas = [{
            "paso": 1,
            "tool": "hora_actual",
            "args": {"zona": "Europe/Madrid"},
            "status": "ok" if _hora_util(observacion) else "error",
            "preview": "",
            "resultado": observacion,
        }]

    hora: dict[str, Any] | None = None
    consulta_llm: dict[str, Any] | None = None

    for llamada in llamadas:
        if llamada["tool"] == "hora_actual":
            observacion = llamada.get("resultado")
            if _hora_util(observacion):
                hora = observacion
                evento_hora = (
                    "instalaciones.tool: hora_actual "
                    "zona=Europe/Madrid status=ok"
                )
            else:
                hora = _hora_no_disponible()
                evento_hora = (
                    "instalaciones.tool: hora_actual "
                    "zona=Europe/Madrid status=error"
                )

        elif (
            llamada["tool"] == TOOL_NAME
            and llamada["status"] in {"ok", "error"}
        ):
            consulta_llm = llamada

    modo, centro_id, requiere_aclaracion = _decidir_consulta(user_message)

    if consulta_llm is not None:
        modo = consulta_llm["args"].get("modo", modo)
        centro_id = consulta_llm["args"].get("centro_id") or None
        requiere_aclaracion = False

    if requiere_aclaracion:
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
    elif consulta_llm is not None:
        resultado = consulta_llm["resultado"]
    else:
        try:
            resultado = consultar_instalaciones(
                modo=modo,
                centro_id=centro_id,
            )
        except Exception:
            logger.exception("Fallo inesperado en la herramienta de instalaciones")
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

    if hora is not None:
        tool_result.data["hora_actual"] = deepcopy(hora)

        if hora.get("ok") is False:
            advertencias = list(tool_result.data.get("advertencias") or [])
            advertencias.append("Hora actual no disponible")
            tool_result.data["advertencias"] = advertencias

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

    traza: list[str] = [evento]

    if evento_hora:
        traza.append(evento_hora)

    return {
        "specialist_results": nuevos,
        "debug_trace": traza,
    }
