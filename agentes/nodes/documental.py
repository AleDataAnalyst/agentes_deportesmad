"""
agentes/nodes/documental.py

Especialista documental: RAG, evidencias, imagen y borradores.

Bucle acotado: propuesta → validación → llamada → observación.

Entradas (state):
    request_id: str               — identificador del pedido vigente (obligatorio)
    pedido: str                   — texto del pedido actual
    contexto_permitido: list[str] | None — fuentes autorizadas (None = todas)
    image_id: str | None          — imagen asociada al pedido
    presupuesto_tools: int        — máximo de llamadas a tools (default 4)
    preparar_borrador: bool       — si se pide un borrador (default False)

Salidas (solo la clave autorizada "documental"):
    documental: dict
        {
            "request_id":   str,
            "resultado":    str,         # síntesis de la evidencia (texto plano)
            "fuentes":      list[str],   # fuentes citadas, orden de aparición
            "abstained":    bool,
            "errores":      list[str],
            "limitaciones": list[str],   # tools no disponibles, presupuesto, contexto
            "eventos":      list[dict],  # uno por cada llamada a tool
        }

Reglas del especialista:
    - No inventar condiciones: si no hay evidencia útil, se abstiene.
    - Un cartel/imagen es evidencia visual, no normativa vigente.
    - Actualizar solo campos autorizados: la única clave devuelta es "documental".
    - El bucle está acotado por presupuesto_tools.

Tools (registry):
    rag              → implementada (agentes.tools.rag.rag_preguntar)
    imagen           → prevista (no disponible aún → limitación)
    preparar_reporte → prevista (no disponible aún → limitación)
"""

from __future__ import annotations

import time
from typing import Any, Callable

from agentes.tools.rag import rag_preguntar

PRESUPUESTO_DEFECTO = 4

# ---------------------------------------------------------------------------
# Registry de tools.
# Cada tool registrada devuelve la observación normalizada:
#   {"ok": bool, "resultado": str, "fuentes": list[str],
#    "abstained": bool, "error": str | None}
# None en el registro = "prevista pero no disponible aún".
# ---------------------------------------------------------------------------

def _tool_rag(consulta: str) -> dict[str, Any]:
    """Wrapper: normaliza el dict de rag_preguntar a observación."""
    r = rag_preguntar(consulta)
    return {
        "ok": r["error"] is None,
        "resultado": r["respuesta"],
        "fuentes": list(r["fuentes"]),
        "abstained": bool(r["abstained"]),
        "error": r["error"],
    }

REGISTRY: dict[str, Callable[..., dict[str, Any]] | None] = {
    "rag": _tool_rag,
    "imagen": None,            # prevista: tool de visión (bytes + MIME + pregunta)
    "preparar_reporte": None,  # prevista: borrador de informe
}


def nodo_documental(state: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el bucle acotado del especialista documental.

    Devuelve SOLO la clave autorizada "documental" (update de state).
    Nunca lanza excepción: los fallos se reflejan en errores/limitaciones.
    """
    request_id = str(state.get("request_id") or "")
    pedido = str(state.get("pedido") or "").strip()
    contexto_permitido: list[str] | None = state.get("contexto_permitido")
    image_id = state.get("image_id")
    presupuesto = int(state.get("presupuesto_tools") or PRESUPUESTO_DEFECTO)
    preparar_borrador = bool(state.get("preparar_borrador", False))

    errores: list[str] = []
    limitaciones: list[str] = []
    eventos: list[dict[str, Any]] = []
    fuentes: list[str] = []
    fragmentos: list[str] = []

    # 1) Propuesta: plan determinista según las entradas del pedido.
    plan: list[tuple[str, dict[str, Any]]] = []
    if image_id:
        plan.append(("imagen", {"image_id": str(image_id), "pregunta": pedido}))
    plan.append(("rag", {"consulta": pedido}))
    if preparar_borrador:
        plan.append(("preparar_reporte", {"titulo": pedido}))

    # 2-4) Validación → llamada → observación, acotado por presupuesto.
    for nombre, args in plan:
        if len(eventos) >= presupuesto:
            limitaciones.append("presupuesto_tools agotado: se omiten las llamadas restantes")
            break

        fn = REGISTRY.get(nombre)
        if fn is None:
            limitaciones.append(f"tool '{nombre}' prevista pero no disponible aún")
            continue

        t0 = time.perf_counter()
        try:
            obs = fn(**args)
        except Exception as e:  # noqa: BLE001 — el especialista no rompe al agente
            obs = {
                "ok": False, "resultado": "", "fuentes": [],
                "abstained": False, "error": f"Error en tool '{nombre}': {e}",
            }
        ms = int((time.perf_counter() - t0) * 1000)

        if obs.get("error"):
            errores.append(str(obs["error"]))

        eventos.append({
            "tool": nombre,
            "args": args,
            "ok": bool(obs.get("ok")),
            "abstained": bool(obs.get("abstained")),
            "fuentes": list(obs.get("fuentes", [])),
            "error": obs.get("error"),
            "ms": ms,
        })

        # Observación útil: suma evidencia y fuentes (sin duplicar).
        if obs.get("ok") and not obs.get("abstained") and str(obs.get("resultado", "")).strip():
            fragmentos.append(str(obs["resultado"]).strip())
            for f in obs.get("fuentes", []):
                if f not in fuentes:
                    fuentes.append(f)

    # Contexto permitido: solo se citan fuentes autorizadas.
    if contexto_permitido is not None:
        permitidos = set(contexto_permitido)
        filtradas = [f for f in fuentes if f in permitidos]
        if fuentes and not filtradas:
            limitaciones.append("ninguna fuente del resultado está en el contexto permitido")
            fragmentos = []  # evidencia no autorizada → se abstuve
        fuentes = filtradas

    abstained = not fragmentos
    if fragmentos:
        resultado = " ".join(fragmentos)
    elif errores:
        resultado = ""  # el fallo viaja en "errores"; no se inventa texto
    else:
        resultado = "No dispongo de esa información en los documentos proporcionados."

    return {
        "documental": {
            "request_id": request_id,
            "resultado": resultado,
            "fuentes": fuentes,
            "abstained": abstained,
            "errores": errores,
            "limitaciones": limitaciones,
            "eventos": eventos,
        }
    }