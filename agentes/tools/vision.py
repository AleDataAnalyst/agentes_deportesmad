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

        if not path.is_file():
            return _build_response(ok=False, error=f"No hay imagen en {path}")

        mime = MIME_TYPES.get(path.suffix.lower())
        if mime is None:
            return _build_response(
                ok=False,
                error=f"Formato no soportado: {path.suffix or 'sin extensión'} (solo JPG y PNG)",
            )

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return _build_response(
                ok=True,
                resultado="[SIMULADO] GOOGLE_API_KEY no configurada; no se ha analizado la imagen.",
                fuentes=[str(path)],
            )

        from google import genai
        from google.genai import types

        prompt = (pregunta or "").strip() or (
            "Describe la imagen en 2-3 frases en español. "
            "Si hay texto, fecha, hora o lugar visibles, menciónalos."
        )
        modelo = getattr(config, "VISION_MODEL", "gemini-3.8-flash")
        client = genai.Client(api_key=api_key)
        out = client.models.generate_content(
            model=modelo,
            contents=[
                types.Part.from_bytes(data=path.read_bytes(), mime_type=mime),
                prompt,
            ],
        )
        texto = (out.text or "").strip()
        if not texto:
            return _build_response(ok=False, error="El modelo devolvió una respuesta vacía")
        return _build_response(ok=True, resultado=texto, fuentes=[str(path)])
    except Exception as e:  # noqa: BLE001
        return _build_response(ok=False, error=f"Error al analizar la imagen: {e}")
