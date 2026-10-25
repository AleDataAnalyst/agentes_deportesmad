"""
agentes/nodes/documental.py

Entradas (state):
    request_id: str                      — identificador del pedido vigente (obligatorio)
    pedido: str                          — texto del pedido actual
    contexto_permitido: list[str] | None — fuentes autorizadas (None = todas)
    image_id: str | None                 — ruta o identificador de la imagen adjunta
    presupuesto_tools: int               — máximo de llamadas a tools (default 4)
    preparar_borrador: bool              — si se pide un borrador (default False)

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
    imagen           → implementada: describe o responde sobre una imagen JPG/JPEG/PNG
    preparar_reporte → prevista (no disponible aún → limitación)
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable

from agentes.tools.rag import rag_preguntar
from agentes.tools.vision import imagen_preguntar

PRESUPUESTO_DEFECTO = 4

FORMATOS_IMAGEN = {".jpg", ".jpeg", ".png"}
DIRECTORIO_IMAGENES = Path("output") / "imagenes"


# ---------------------------------------------------------------------------
# Utilidades de imagen
# ---------------------------------------------------------------------------

def guardar_imagen_subida(nombre_archivo: str, contenido: bytes) -> str:
    """Guarda una imagen subida y devuelve el image_id utilizable por la tool."""
    extension = Path(nombre_archivo or "").suffix.lower()

    if extension not in FORMATOS_IMAGEN:
        raise ValueError(
            "IMAGE_UNSUPPORTED: solo se aceptan imágenes JPG, JPEG o PNG"
        )

    if not contenido:
        raise ValueError("IMAGE_EMPTY: el archivo de imagen está vacío")

    DIRECTORIO_IMAGENES.mkdir(parents=True, exist_ok=True)

    image_id = f"{uuid.uuid4().hex}{extension}"
    ruta = DIRECTORIO_IMAGENES / image_id
    ruta.write_bytes(contenido)

    return str(ruta)


# ---------------------------------------------------------------------------
# Registry de tools
# ---------------------------------------------------------------------------

def _tool_rag(consulta: str) -> dict[str, Any]:
    """Normaliza la salida de rag_preguntar al contrato de observación."""
    r = rag_preguntar(consulta)

    return {
        "ok": r["error"] is None,
        "resultado": r["respuesta"],
        "fuentes": list(r["fuentes"]),
        "abstained": bool(r["abstained"]),
        "error": r["error"],
    }


def _tool_imagen(image_id: str, pregunta: str) -> dict[str, Any]:
    """Normaliza la salida de imagen_preguntar al contrato de observación."""
    r = imagen_preguntar(image_id=image_id, pregunta=pregunta)

    return {
        "ok": bool(r.get("ok")),
        "resultado": str(r.get("resultado", "")),
        "fuentes": list(r.get("fuentes", [])),
        "abstained": bool(r.get("abstained")),
        "error": r.get("error"),
    }


REGISTRY: dict[str, Callable[..., dict[str, Any]] | None] = {
    "rag": _tool_rag,
    "imagen": _tool_imagen,
    "preparar_reporte": None,
}


# ---------------------------------------------------------------------------
# Nodo del especialista documental
# ---------------------------------------------------------------------------

def _imagen_disponible(image_id: str | None) -> bool:
    """Comprueba que la imagen indicada existe y tiene un formato admitido."""
    if not image_id:
        return False

    ruta = Path(image_id)
    return ruta.is_file() and ruta.suffix.lower() in FORMATOS_IMAGEN


def _ejecutar_tool(
    nombre: str,
    funcion: Callable[..., dict[str, Any]],
    argumentos: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Ejecuta una tool sin propagar excepciones."""
    try:
        return funcion(**argumentos), None
    except Exception as exc:  # noqa: BLE001 - el nodo no debe lanzar
        return None, f"{nombre}: {type(exc).__name__}: {exc}"


def nodo_documental(state: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el bucle acotado del especialista documental.

    Devuelve SOLO la clave autorizada "documental" (update de state).
    Nunca lanza excepción: los fallos se reflejan en errores/limitaciones.
    """
    request_id = str(state.get("request_id") or "")
    pedido = str(state.get("pedido") or "").strip()
    contexto_permitido = state.get("contexto_permitido")
    image_id = state.get("image_id")
    presupuesto = state.get("presupuesto_tools", PRESUPUESTO_DEFECTO)
    preparar_borrador = bool(state.get("preparar_borrador", False))

    resultado = ""
    fuentes: list[str] = []
    errores: list[str] = []
    limitaciones: list[str] = []
    eventos: list[dict[str, Any]] = []
    abstained = True

    if not request_id:
        errores.append("REQUEST_ID_MISSING: falta request_id")

    if not pedido:
        errores.append("PEDIDO_MISSING: falta el texto del pedido")

    try:
        presupuesto = int(presupuesto)
    except (TypeError, ValueError):
        presupuesto = PRESUPUESTO_DEFECTO
        limitaciones.append("presupuesto_tools inválido; se usa el valor por defecto")

    if presupuesto <= 0:
        limitaciones.append("presupuesto agotado: no se puede consultar ninguna tool")

    if preparar_borrador:
        limitaciones.append("preparar_reporte no está disponible todavía")

    if image_id and not _imagen_disponible(str(image_id)):
        limitaciones.append("imagen no disponible o formato no admitido")
        image_id = None

    puede_consultar = bool(request_id and pedido and presupuesto > 0)

    if puede_consultar:
        observacion, error = _ejecutar_tool(
            "rag",
            REGISTRY["rag"],
            {"consulta": pedido},
        )

        if error is not None:
            errores.append(error)
        elif observacion is not None:
            eventos.append(
                {
                    "tool": "rag",
                    "ok": bool(observacion.get("ok")),
                    "error": observacion.get("error"),
                }
            )

            fuentes_raw = list(observacion.get("fuentes", []))

            if contexto_permitido is not None:
                permitidas = set(contexto_permitido)
                fuentes = [f for f in fuentes_raw if f in permitidas]

                if not fuentes:
                    limitaciones.append(
                        "ninguna fuente obtenida está dentro del contexto permitido"
                    )
            else:
                fuentes = fuentes_raw

            if observacion.get("error"):
                errores.append(str(observacion["error"]))

            if fuentes and not observacion.get("abstained"):
                resultado = str(observacion.get("resultado", ""))
                abstained = False
            else:
                limitaciones.append("sin evidencia útil en las fuentes disponibles")

        presupuesto -= 1

    # La imagen solo se consulta si ya hay una respuesta documental válida
    # y queda presupuesto.
    if image_id and not abstained and presupuesto > 0:
        observacion, error = _ejecutar_tool(
            "imagen",
            REGISTRY["imagen"],
            {"image_id": str(image_id), "pregunta": pedido},
        )

        if error is not None:
            errores.append(error)
        elif observacion is not None:
            eventos.append(
                {
                    "tool": "imagen",
                    "ok": bool(observacion.get("ok")),
                    "error": observacion.get("error"),
                }
            )

            if observacion.get("error"):
                errores.append(str(observacion["error"]))

            texto_imagen = str(observacion.get("resultado", "")).strip()
            if texto_imagen:
                resultado = f"{resultado}\n\nEvidencia visual:\n{texto_imagen}".strip()
                fuentes.extend(
                    f for f in observacion.get("fuentes", []) if f not in fuentes
                )

        presupuesto -= 1

    if contexto_permitido is not None and not fuentes:
        abstained = True

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