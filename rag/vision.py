"""
rag/vision.py
Carga imágenes como Documents de LangChain.

Genera como máximo dos documentos por imagen:
  - OCR con Tesseract: texto literal extraído.
  - Descripción multimodal con Gemini: descripción generada, opcional.

No fusiona OCR y descripción: cada representación conserva su método
de extracción y puede auditarse por separado.
"""

import base64
from pathlib import Path

import requests
from langchain_core.documents import Document

from .config import (
    GOOGLE_API_KEY,
    IMAGE_MAX_DESCRIPTION_CHARS,
    IMAGE_OCR_ENABLED,
    IMAGE_OCR_LANG,
    IMAGE_VISION_ENABLED,
    IMAGE_VISION_MODEL,
)


def _ocr_imagen(ruta: Path) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(ruta) as imagen:
        texto = pytesseract.image_to_string(
            imagen,
            lang=IMAGE_OCR_LANG,
        )

    return texto.strip()


def _descripcion_gemini(ruta: Path) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "IMAGE_VISION_ENABLED=true pero GOOGLE_API_KEY no está definida."
        )

    imagen_base64 = base64.b64encode(ruta.read_bytes()).decode("utf-8")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{IMAGE_VISION_MODEL}:generateContent"
    )

    respuesta = requests.post(
        url,
        headers={"x-goog-api-key": GOOGLE_API_KEY},
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Describe objetivamente la imagen para un sistema "
                                "de recuperación documental. Incluye solo información "
                                "visible: texto, lugares, instalaciones, personas, "
                                "actividades y datos relevantes. No inventes datos."
                            )
                        },
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

    contenido = respuesta.json()["candidates"][0]["content"]["parts"]
    descripcion = "".join(
        parte.get("text", "") for parte in contenido
    ).strip()

    return descripcion[:IMAGE_MAX_DESCRIPTION_CHARS]


def cargar_imagen(ruta: str) -> list[Document]:
    """
    Convierte una imagen en Documents indexables.

    Returns:
        Lista con OCR y, si está activado, descripción visual.
    """
    path = Path(ruta)
    documentos: list[Document] = []

    metadatos_base = {
        "source": path.name,
        "image_path": str(path),
        "format": "image",
        "element_type": "ocr",
    }

    if IMAGE_OCR_ENABLED:
        try:
            texto_ocr = _ocr_imagen(path)

            if texto_ocr:
                documentos.append(
                    Document(
                        page_content=texto_ocr,
                        metadata={
                            **metadatos_base,
                            "extraction_method": "tesseract",
                            "ocr_language": IMAGE_OCR_LANG,
                        },
                    )
                )
            else:
                print(f"[VISION] OCR vacío: {path.name}")

        except Exception as exc:
            print(f"[VISION] Error OCR en {path.name}: {exc}")

    if IMAGE_VISION_ENABLED:
        try:
            descripcion = _descripcion_gemini(path)

            if descripcion:
                documentos.append(
                    Document(
                        page_content=descripcion,
                        metadata={
                            **metadatos_base,
                            "element_type": "image_description",
                            "extraction_method": f"gemini:{IMAGE_VISION_MODEL}",
                        },
                    )
                )

        except Exception as exc:
            print(f"[VISION] Error de descripción en {path.name}: {exc}")

    if not documentos:
        # No se inventa contenido: se registra la limitación.
        documentos.append(
            Document(
                page_content=(
                    "No se pudo extraer información verificable de esta imagen."
                ),
                metadata={
                    **metadatos_base,
                    "element_type": "image_unreadable",
                    "extraction_method": "none",
                    "abstention": True,
                },
            )
        )

    return documentos