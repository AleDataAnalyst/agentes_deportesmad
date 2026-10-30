import io
from pathlib import Path

import pytesseract
from PIL import Image
from pypdf import PdfReader

PDF_PATH = Path("data/corpus/PreciosPublicos2026.pdf")
OUTPUT_DIR = Path("diagnostico_pdf")
IMAGE_NAME = "X4.png"

# En Windows, descomenta y ajusta si Tesseract no está en PATH:
# pytesseract.pytesseract.tesseract_cmd = (
#     r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Comprueba el ejecutable y el idioma antes de procesar.
    print("Tesseract:", pytesseract.get_tesseract_version())

    if "spa" not in pytesseract.get_languages(config=""):
        raise RuntimeError(
            "Falta el idioma español 'spa' en Tesseract."
        )

    lector = PdfReader(str(PDF_PATH))
    imagen_pdf = next(
        (
            imagen
            for imagen in lector.pages[0].images
            if imagen.name == IMAGE_NAME
        ),
        None,
    )

    if imagen_pdf is None:
        raise ValueError(f"No se encontró la imagen {IMAGE_NAME!r}.")

    ruta_original = OUTPUT_DIR / f"precios_original_{IMAGE_NAME}"
    ruta_original.write_bytes(imagen_pdf.data)

    with Image.open(io.BytesIO(imagen_pdf.data)) as original:
        imagen = original.convert("RGB")

    config = "--psm 6"

    texto = pytesseract.image_to_string(
        imagen,
        lang="spa",
        config=config,
    )

    tsv = pytesseract.image_to_data(
        imagen,
        lang="spa",
        config=config,
        output_type=pytesseract.Output.STRING,
    )

    ruta_texto = OUTPUT_DIR / "precios_X4_ocr.txt"
    ruta_tsv = OUTPUT_DIR / "precios_X4_ocr.tsv"

    ruta_texto.write_text(texto, encoding="utf-8")
    ruta_tsv.write_text(tsv, encoding="utf-8")

    print(f"Imagen original: {imagen.width} × {imagen.height} píxeles")
    print(f"Texto guardado: {ruta_texto.resolve()}")
    print(f"Posiciones guardadas: {ruta_tsv.resolve()}")
    print("\n--- TEXTO RECONOCIDO ---\n")
    print(texto)


if __name__ == "__main__":
    main()