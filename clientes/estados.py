"""Traduce el resultado de un especialista a lo que muestra la interfaz.

Sin dependencias de Streamlit, para poder probarlo con datos de ejemplo. Un
resultado es una respuesta, una abstención o un error; las limitaciones y las
fuentes se muestran siempre que existan, sean cual sean los tres tipos.
"""
from __future__ import annotations

from typing import Any

CLAVES_LIMITACIONES = ("limitaciones", "advertencias", "warnings")


def _campo(obj: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(nombre, defecto)
    return getattr(obj, nombre, defecto)


def _textos(valor: Any) -> list[str]:
    if valor in (None, "", []):
        return []
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor if str(v)]
    return [str(valor)]


def vista_resultado(resultado: Any) -> dict[str, Any]:
    """Devuelve tipo (respuesta, abstencion o error), texto, fuentes, limitaciones y error."""
    estado = _campo(resultado, "status")
    data = _campo(resultado, "data") or {}

    fuentes: list[str] = []
    for ev in _campo(resultado, "evidence") or []:
        fuente = str(_campo(ev, "source") or "")
        if fuente and fuente not in fuentes:
            fuentes.append(fuente)

    limitaciones: list[str] = []
    for clave in CLAVES_LIMITACIONES:
        for texto in _textos(_campo(data, clave)):
            if texto not in limitaciones:
                limitaciones.append(texto)

    tipo = {"error": "error", "abstained": "abstencion"}.get(estado, "respuesta")
    return {
        "tipo": tipo,
        "texto": str(_campo(resultado, "answer") or ""),
        "fuentes": fuentes,
        "limitaciones": limitaciones,
        "error": _campo(resultado, "error"),
    }


def avisos_de_estado(estado: dict) -> list[tuple[str, str]]:
    """Avisos (nivel, texto) de cada especialista: abstención, error y limitaciones.

    El nivel es el nombre del componente de Streamlit: info, error o warning.
    En una abstención las limitaciones van dentro del mismo aviso.
    """
    avisos: list[tuple[str, str]] = []
    for rol, resultado in (estado.get("specialist_results") or {}).items():
        vista = vista_resultado(resultado)
        limitaciones = "; ".join(vista["limitaciones"])
        if vista["tipo"] == "abstencion":
            texto = vista["texto"] or "no hay evidencia suficiente para responder."
            if limitaciones:
                texto += f" {limitaciones}"
            avisos.append(("info", f"{rol}: {texto}"))
            continue
        if vista["tipo"] == "error":
            avisos.append(("error", f"{rol}: {vista['error'] or 'error sin detalle'}"))
        if limitaciones:
            avisos.append(("warning", f"{rol} · Limitaciones: {limitaciones}"))
    return avisos


def ayuda_arranque(exc: BaseException) -> str | None:
    """Pista para el usuario cuando el servicio no arranca por la configuración del supervisor."""
    if "SUPERVISOR_" in str(exc):
        return ("Revisa SUPERVISOR_MODE, SUPERVISOR_PROVIDER y SUPERVISOR_MODEL en el .env "
                "y reinicia Streamlit.")
    return None
