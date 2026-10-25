"""
agentes/nodes/documental.py

Especialista documental: RAG, evidencias, imagen y borradores.

Bucle acotado: propuesta → validación → llamada → observación.

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
    """Guarda una imagen subida y devuelve el image_id utilizable por la tool.

    Args:
        nombre_archivo: nombre original del archivo, usado solo para la extensión.
        contenido: bytes de la imagen.

    Returns:
        Ruta relativa al archivo guardado, utilizable como `image_id`.

    Raises:
        ValueError: si el formato no está permitido o el contenido está vacío.
    """
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

def nodo_documental(state: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el bucle acotado del especialista documental.

    Devuelve SOLO la clave autorizada "documental" (update de state).
    Nunca lanza excepción: los fallos se reflejan en errores/limitaciones.
    """
    request_id = str(state.get("request_id") or