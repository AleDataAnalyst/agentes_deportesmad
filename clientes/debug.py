"""Panel de diagnóstico del agente.

Muestra identificadores, fase HITL, estado de finalización, iteraciones,
trazas y resultados de especialistas. Los valores pasan por el filtro
de secretos en los puntos indicados y se recortan para limitar la salida.

Este módulo solo presenta el estado recibido; no ejecuta herramientas.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import streamlit as st

from agentes.secret_filter import sin_secretos

# Límites de presentación.
MAX_TEXTO = 400
MAX_TRAZA = 50
MAX_FUENTES = 5

ICONOS = {"ok": "✅", "abstained": "⚪", "error": "❌"}


def _campo(obj: Any, nombre: str, defecto: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(nombre, defecto)
    return getattr(obj, nombre, defecto)


def _seguro(valor: Any, limite: int = MAX_TEXTO) -> str:
    texto = sin_secretos(valor)
    if len(texto) > limite:
        texto = texto[:limite] + " …[recortado]"
    return texto


def _a_dict(valor: Any) -> Any:
    """Expone los campos de dataclasses y modelos al filtro de secretos."""
    try:
        if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
            return dataclasses.asdict(valor)
        if hasattr(valor, "model_dump"):
            return valor.model_dump()
    except Exception:
        pass
    return valor


def _origen(resultado: Any) -> str:
    data = _campo(resultado, "data") or {}
    if _campo(data, "available") is False:
        return "no disponible"
    if _campo(data, "simulated"):
        return "simulado"
    if _campo(data, "fallback") or _campo(data, "origen") == "fallback":
        return "fallback"
    return "real"


def fuentes_de_estado(estado: dict) -> list[str]:
    """Fuentes citadas por los especialistas, sin repetir y ya filtradas."""
    vistas: list[str] = []
    for resultado in (estado.get("specialist_results") or {}).values():
        for ev in _campo(resultado, "evidence") or []:
            fuente = _seguro(_campo(ev, "source"), 200)
            if fuente and fuente not in vistas:
                vistas.append(fuente)
    return vistas[:MAX_FUENTES]


def _fase_hitl(estado: dict) -> str:
    if estado.get("pendiente_hitl"):
        return "pendiente de decisión"

    aprobado = estado.get("approved")
    if aprobado is True:
        return "aprobado"
    if aprobado is False:
        return "rechazado"
    return "sin decisión"


def _render_resultado(nombre: str, resultado: Any) -> None:
    status = str(_campo(resultado, "status", "desconocido"))
    icono = ICONOS.get(status, "❔")
    st.markdown(
        f"**{icono} {nombre}** · estado `{status}` · "
        f"origen `{_origen(resultado)}`"
    )

    data = _campo(resultado, "data") or {}
    request_id = _campo(data, "request_id")
    if request_id:
        st.text(f"request_id: {_seguro(request_id, 64)}")

    answer = _campo(resultado, "answer")
    if answer:
        st.text(f"Respuesta: {_seguro(answer)}")

    error = _campo(resultado, "error")
    if error:
        st.error(_seguro(error))

    evidencias = _campo(resultado, "evidence") or []
    if evidencias:
        st.text(f"Fuentes ({len(evidencias)}):")
        for ev in evidencias[:MAX_FUENTES]:
            st.text(f"  • {_seguro(_campo(ev, 'source'), 200)}")

        if len(evidencias) > MAX_FUENTES:
            st.text(f"  … y {len(evidencias) - MAX_FUENTES} más")
    else:
        st.text("Fuentes: ninguna")

    for ev in (_campo(data, "eventos") or [])[:MAX_TRAZA]:
        st.text(
            f"  tool={_seguro(_campo(ev, 'tool'), 40)} · "
            f"ok={_campo(ev, 'ok')} · "
            f"abstained={_campo(ev, 'abstained')} · "
            f"{_seguro(_campo(ev, 'ms'), 20)} ms"
        )


def render_debug(estado: dict, thread_id: str) -> None:
    with st.expander("Debug — estado del agente"):
        st.markdown(f"**thread_id:** `{_seguro(thread_id, 80)}`")

        c1, c2, c3 = st.columns(3)
        c1.metric("Fase HITL", _fase_hitl(estado))
        c2.metric("done", str(estado.get("done")))
        c3.metric("iteraciones", str(estado.get("iterations")))

        if estado.get("ejecucion_incompleta"):
            st.warning("Ejecución incompleta: usa una nueva conversación.")

        traza = estado.get("debug_trace") or []
        if traza:
            st.markdown("**Traza:**")
            for evento in traza[:MAX_TRAZA]:
                st.text(f"• {_seguro(evento, 200)}")

            if len(traza) > MAX_TRAZA:
                st.text(f"… {len(traza) - MAX_TRAZA} eventos más")

        resultados = estado.get("specialist_results") or {}
        if resultados:
            st.markdown("**Resultados de especialistas:**")
            for nombre, resultado in resultados.items():
                _render_resultado(str(nombre), resultado)

            if st.checkbox(
                "Mostrar datos técnicos (filtrados)",
                key=f"debug_raw_{thread_id}",
            ):
                st.code(
                    _seguro(
                        {k: _a_dict(v) for k, v in resultados.items()},
                        3000,
                    )
                )