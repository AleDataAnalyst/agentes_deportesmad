"""
agentes/tools/vision.py

Tool de visión: imagen -> texto.

Contrato:
    imagen_preguntar(image_id, pregunta) -> dict
        {
            "ok": bool,
            "resultado": str,
            "fuentes": list[str],
            "abstained": bool,
            "error": str | None,
        }

Reglas:
- Nunca lanza excepciones: los errores viajan en "error".
- Acepta JPG/JPEG y PNG.
- Si no hay GOOGLE_API_KEY, devuelve una respuesta simulada para poder probar el grafo.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

try:
    import config
except ImportError:
    config = None


MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

DEFAULT_IMAGE = "assets/imagen_demo.jpg"


def _resolve_image_path(image_id: str) -> Path:
    """Resuelve una ruta absoluta a partir del image_id recibido."""
    raw = (image_id or "").strip()

    if not raw or raw == "imagen_demo":
        raw = DEFAULT_IMAGE

    path = Path(raw)

    if not path.is_absolute():
        root = getattr(config, "ROOT", Path.cwd())
        path = root / path

    return path


def _build_response(
    ok: bool,
    resultado: str = "",
    fuentes: list[str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Devuelve el contrato uniforme de la tool."""
    return {
        "ok": ok,
        "resultado": resultado,
        "fuentes": fuentes or [],
        "abstained": False,
        "error": error,
    }


@tool
def imagen_preguntar(image_id: str = "", pregunta: str = "") -> dict[str, Any]:
    """Describe una imagen en español y responde a la pregunta del usuario.

    Si no se indica image_id, usa assets/imagen_demo.jpg.
    Devuelve siempre un dict con ok, resultado, fuentes, abstained y error.
    """
    try:
        path = _resolve_image_path(image_id)

        if not path.exists() or not path.is_file():
            return _build_response(
                ok=False,
                error=f"Error: