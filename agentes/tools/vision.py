"""
agentes/tools/vision.py

Tool de visión: describe la imagen de demo (imagen → texto).

Contrato (sigue el mismo patrón que rag.py):
    imagen_preguntar(image_id, pregunta) -> dict
        {
            "ok": bool,            # True = éxito, False = fallo
            "resultado": str,      # descripción del texto visible
            "fuentes": list[str],  # ["imagen_demo.jpg"] cuando hay resultado
            "abstained": bool,     # no aplica aquí (es una demo)
            "error": str | None,   # SIEMPRE presente, nunca lanza
        }

Límites (según 02_multimodal.md):
    - Una sola llamada imagen → texto. No hay pipeline ni almacén de medios.
    - MIME correcto obligatorio (image/jpeg, image/png). Un tipo mal rompe la respuesta.
    - El modelo describe lo que ve, no consulta un catálogo.

La visión puede empezar con DATOS SIMULADOS (no necesita índice ni LLM real),
así no bloquea el proyecto si GEMINI_API_KEY no está configurada.
"""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool

import config
import os


@tool
def imagen_preguntar(image_id: str = "", pregunta: str = "") -> dict[str, str]:
    """Describe la imagen de demo en español (texto visible, lugar, contexto).

    Sin image_id (o cadena vacía) usa assets/imagen_demo.jpg del proyecto.
    Devuelve SIEMPRE un dict con ok/resultado/fuentes/abstained/error.
    Nunca lanza excepción: los fallos viajan en "error".
    """
    # 1) Normalizar el id de la imagen
    if not isinstance(image_id, str) or not image_id.strip():
        image_id = "imagen_demo"
    image_id = image_id.strip()

    # 2) Localizar la imagen
    path = Path(config.IMAGEN_DEFAULT_PATH) if image_id in ("", "imagen_demo") else Path(image_id)
    if not path.is_absolute():
        path = (config.ROOT / path)
    if not path.exists():
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error: no hay imagen en {path}",
        }

    # 3) Leer los bytes y detectar el MIME (obligatorio)
    try:
        data = path.read_bytes()
    except Exception as e:
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error al leer la imagen: {e}",
        }

    mime = "image/jpeg" if path.suffix.lower() == ".jpg" else "image/png"

    # 4) Llamada al modelo multimodal (Gemini)
    try:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # Sin API real: devolvemos un resultado SIMULADO para poder probar
            # la conexión sin bloquear el proyecto.
            return {
                "ok": True,
                "resultado": (
                    f"[SIMULADO] En la imagen de demo se observa el texto visible "
                    f"ubicado en el contexto del cartel. "
                    f"(GEMINI_API_KEY no configurada)"
                ),
                "fuentes": [str(path)],
                "abstained": False,
                "error": None,
            }

        client = genai.Client(api_key=api_key)
        out = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=data, mime_type=mime),
                        types.Part.from_text(
                            text=(
                                "Describe la imagen en 2-3 frases en español. "
                                "Si hay texto, fecha, hora o lugar visibles, menciónalos."
                            )
                        ),
                    ],
                )
            ],
        )
        return {
            "ok": True,
            "resultado": (out.text or "").strip() or "Error: respuesta vacía del modelo.",
            "fuentes": [str(path)],
            "abstained": False,
            "error": None,
        }
    except Exception as e:  # noqa: BLE001 — la tool nunca lanza
        return {
            "ok": False,
            "resultado": "",
            "fuentes": [],
            "abstained": False,
            "error": f"Error al leer la imagen: {e}",
        }