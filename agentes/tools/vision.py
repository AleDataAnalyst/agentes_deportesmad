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
from pathlib import Path

import requests
from langchain_core.tools import tool

from rag.config import (
    GOOGLE_API_KEY,
    IMAGE_VISION_MODEL,
)

FORMATOS_PERMITIDOS = {".jpg", ".jpeg", ".png", ".webp"}


def _abstencion(error: str) -> dict:
    return {
        "ok": False,
        "resultado": "",
        "fuentes": [],
        "abstained": True,
        "error": error,
    }


def _error(error: str) -> dict:
    return {
        "ok": False,
        "resultado": "",
        "fuentes": [],
        "abstained": False,
        "error": error,
    }


@tool
def imagen_preguntar(image_id: str, pregunta: str = "Describe objetivamente la imagen.") -> dict:
    """Responde una pregunta sobre una imagen usando visión multimodal.

    Args:
        image_id: Ruta o identificador de la imagen.
        pregunta: Pregunta que debe responderse usando solo información visible.
    """
    if not GOOGLE_API_KEY:
        return _abstencion(
            "Visión no disponible: GOOGLE_API_KEY no está definida."
        )

    ruta = Path(image_id)

    if not ruta.exists():
        return _error(f"No hay imagen en la ruta indicada: {image_id}")

    if ruta.suffix.lower() not in FORMATOS_PERMITIDOS:
        return _error(
            f"Formato no soportado: {ruta.suffix}. "
            f"Formatos permitidos: {', '.join(sorted(FORMATOS_PERMITIDOS))}."
        )

    try:
        imagen_base64 = base64.b64encode(ruta.read_bytes()).decode("utf-8")
    except OSError as exc:
        return _error(f"No se pudo leer la imagen: {exc}")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_VISION_MODEL}:generateContent"
    )

    try:
        respuesta = requests.post(
            url,
            headers={"x-goog-api-key": GOOGLE_API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": pregunta},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": imagen_base64,
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 512,
                },
            },
            timeout=120,
        )
        respuesta.raise_for_status()

        partes = respuesta.json()["candidates"][0]["content"]["parts"]
        texto = "".join(parte.get("text", "") for parte in partes).strip()

    except (requests.RequestException, KeyError, IndexError, TypeError) as exc:
        return _abstencion(f"Error al consultar el modelo de visión: {exc}")

    if not texto:
        return _abstencion(
            "El modelo de visión no devolvió información verificable."
        )

    return {
        "ok": True,
        "resultado": texto,
        "fuentes": [
            {
                "tipo": "imagen",
                "ruta": str(ruta),
                "modelo": IMAGE_VISION_MODEL,
            }
        ],
        "abstained": False,
        "error": None,
    }