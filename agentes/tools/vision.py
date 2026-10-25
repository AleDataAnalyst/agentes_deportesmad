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

import base64
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


def _llamar_google_vision(
    ruta: Path,
    mime_type: str,
    pregunta: str,
) -> str:
    """Llama al modelo multimodal de Google y devuelve el texto generado."""
    from google import genai
    from google.genai import types

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY no está configurada")

    client = genai.Client(api_key=api_key)

    with ruta.open("rb") as f:
        image_bytes = f.read()

    modelo = os.getenv("VISION_MODEL", "gemini-2.0-flash")

    respuesta = client.models.generate_content(
        model=modelo,
        contents=[
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            ),
            pregunta,
        ],
    )

    texto = (respuesta.text or "").strip()

    if not texto:
        raise ValueError("El modelo de visión no devolvió texto")

    return texto


@tool
def imagen_preguntar(image_id: str = "", pregunta: str = "") -> dict[str, Any]:
    """Describe una imagen en español y responde a la pregunta del usuario.

    Si no se indica image_id, usa assets/imagen_demo.jpg.
    Devuelve siempre un dict con ok, resultado, fuentes, abstained y error.
    """
    try:
        pregunta = (pregunta or "").strip()

        if not pregunta:
            pregunta = "Describe esta imagen con detalle."

        ruta = _resolve_image_path(image_id)

        if not ruta.is_file():
            return _build_response(
                ok=False,
                error=f"IMAGE_NOT_FOUND: no existe la imagen '{ruta}'",
            )

        extension = ruta.suffix.lower()

        if extension not in MIME_TYPES:
            return _build_response(
                ok=False,
                error=(
                    "IMAGE_UNSUPPORTED_FORMAT: formato no soportado. "
                    "Usa JPG, JPEG o PNG."
                ),
            )

        mime_type = MIME_TYPES[extension]

        if not os.getenv("GOOGLE_API_KEY"):
            return _build_response(
                ok=True,
                resultado=(
                    "[SIMULACIÓN] Imagen analizada: "
                    f"{ruta.name}. No hay GOOGLE_API_KEY configurada, "
                    "por lo que no se ha realizado una descripción real."
                ),
                fuentes=[str(ruta)],
            )

        descripcion = _llamar_google_vision(
            ruta=ruta,
            mime_type=mime_type,
            pregunta=pregunta,
        )

        return _build_response(
            ok=True,
            resultado=descripcion,
            fuentes=[str(ruta)],
        )

    except Exception as exc:  # noqa: BLE001 — la tool nunca rompe el grafo
        return _build_response(
            ok=False,
            error=f"VISION_ERROR: {exc}",
        )