"""Guardado de las imágenes que sube el usuario en Streamlit.

Imita guardar_imagen_subida del especialista documental, sin importarlo: solo
JPG y PNG, nunca se usa el nombre original del archivo y el contenido debe
coincidir con la extensión. Guarda siempre bajo la raíz del proyecto, arranque
Streamlit desde donde arranque, y devuelve como image_id una ruta relativa a
esa raíz (output/imagenes/<nombre>), que es la que valida el backend. Nunca se
muestra una ruta absoluta al usuario.
"""
from __future__ import annotations

import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PREFIJO_IMAGE_ID = "output/imagenes"
DIRECTORIO_IMAGENES = RAIZ / PREFIJO_IMAGE_ID
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
    nombre = f"{uuid.uuid4().hex}{extension}"
    (DIRECTORIO_IMAGENES / nombre).write_bytes(contenido)
    return f"{PREFIJO_IMAGE_ID}/{nombre}"


def ruta_imagen(image_id: str | None) -> Path | None:
    """Ruta real de un image_id guardado, solo para mostrarla; None si no existe o no es nuestra."""
    if not image_id or ".." in image_id or Path(image_id).is_absolute():
        return None
    ruta = (RAIZ / image_id).resolve()
    if not ruta.is_relative_to(RAIZ / PREFIJO_IMAGE_ID) or not ruta.is_file():
        return None
    return ruta
