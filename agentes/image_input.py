"""Autoriza referencias locales de imagen sin abrir ni interpretar su contenido."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSIONES = frozenset({".jpg", ".jpeg", ".png"})
DEMO = Path("assets/imagen_demo.jpg")


def validar_image_id(image_id: str | None) -> str | None:
    """Devuelve ruta absoluta canónica o None; errores sin rutas personales.

    Solo autoriza ubicación, formato declarado y existencia. La validación del
    contenido corresponde al guardado/visión; aquí no se leen bytes. Revalidar
    al transportar reduce cambios entre entrada y ejecución, sin garantizar
    atomicidad frente a modificaciones concurrentes del sistema de archivos.
    """
    if image_id is None:
        return None
    if not isinstance(image_id, str) or not image_id.strip():
        raise ValueError("IMAGE_ID_INVALID: image_id debe ser texto no vacío o None")
    raw = image_id.strip().replace("\\", "/")
    if ".." in raw.split("/") or any(ord(c) < 32 for c in raw):
        raise ValueError("IMAGE_PATH_FORBIDDEN: ubicación de imagen no autorizada")
    path = DEMO if raw == "imagen_demo" else Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path = path.resolve()
        # Comparar con las ubicaciones autorizadas sin resolver sus enlaces:
        # también rechaza enlaces/junctions que salen de output/imagenes.
        if not (path.is_relative_to(ROOT / "output" / "imagenes") or path == ROOT / DEMO):
            raise ValueError("IMAGE_PATH_FORBIDDEN: ubicación de imagen no autorizada")
        if path.suffix.lower() not in EXTENSIONES:
            raise ValueError("IMAGE_UNSUPPORTED: solo se aceptan imágenes JPG, JPEG o PNG")
        if not path.is_file():
            raise ValueError("IMAGE_NOT_FOUND: no se encuentra el archivo de imagen")
    except (OSError, RuntimeError):
        raise ValueError("IMAGE_UNAVAILABLE: no se puede acceder a la imagen") from None
    return str(path)
