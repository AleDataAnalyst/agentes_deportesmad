"""Guardado de las imágenes que sube el usuario en Streamlit.

Imita guardar_imagen_subida del especialista documental, sin importarlo: solo
JPG y PNG, nunca se usa el nombre original del archivo y el contenido debe
coincidir con la extensión. Devuelve la ruta relativa como image_id.
"""
from __future__ import annotations

import uuid
from pathlib import Path

DIRECTORIO_IMAGENES = Path("output") / "imagenes"
MAX_BYTES = 10 * 1024 * 1024
FIRMAS = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def guardar_imagen_subida(nombre_archivo: str, contenido: bytes) -> str:
    """Guarda la imagen y devuelve su image_id; ValueError con un código si no vale."""
    extension = Path(nombre_archivo or "").suffix.lower()
    if extension not in FIRMAS:
        raise ValueError("IMAGE_UNSUPPORTED: solo se aceptan imágenes JPG, JPEG o PNG")
    if not contenido:
        raise ValueError("IMAGE_EMPTY: el archivo de imagen está vacío")
    if len(contenido) > MAX_BYTES:
        raise ValueError(f"IMAGE_TOO_LARGE: la imagen supera {MAX_BYTES // (1024 * 1024)} MB")
    if not contenido.startswith(FIRMAS[extension]):
        raise ValueError("IMAGE_INVALID: el contenido no corresponde a una imagen de ese formato")

    DIRECTORIO_IMAGENES.mkdir(parents=True, exist_ok=True)
    ruta = DIRECTORIO_IMAGENES / f"{uuid.uuid4().hex}{extension}"
    ruta.write_bytes(contenido)
    return str(ruta)
