""" Guadar imagen original sin modif. según la obtiene PyPDF

    Sin redimensiones ni compresión.
"""


from pathlib import Path

from pypdf import PdfReader

PDF_PATH = Path("data/corpus/PreciosPublicos2026.pdf")
OUTPUT_DIR = Path("diagnostico_pdf")


def guardar_imagen_original(
    pdf_path: Path,
    output_dir: Path,
    nombre_imagen: str = "X4.png",
    pagina: int = 1,
) -> Path:
    """Extrae una imagen incrustada sin redimensionarla."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"No existe el PDF: {pdf_path}")

    lector = PdfReader(str(pdf_path))

    if not 1 <= pagina <= len(lector.pages):
        raise ValueError(
            f"Página inválida: {pagina}. "
            f"El PDF tiene {len(lector.pages)} página(s)."
        )

    imagenes = list(lector.pages[pagina - 1].images)

    for imagen in imagenes:
        if imagen.name == nombre_imagen:
            output_dir.mkdir(parents=True, exist_ok=True)

            destino = output_dir / f"precios_original_{imagen.name}"
            destino.write_bytes(imagen.data)

            if destino.stat().st_size == 0:
                raise RuntimeError("La imagen extraída está vacía.")

            print(f"Imagen original guardada: {destino.resolve()}")
            return destino

    disponibles = ", ".join(imagen.name for imagen in imagenes)
    raise ValueError(
        f"No se encontró {nombre_imagen!r}. "
        f"Imágenes disponibles: {disponibles}"
    )


if __name__ == "__main__":
    guardar_imagen_original(
        pdf_path=PDF_PATH,
        output_dir=OUTPUT_DIR,
    )