"""
Recorte cartesiano en PDF.

Este códgido guarda el recorte con coordenadas cartesianas definido
para la primera región sin marcas ni bordes añadidos

"""


from pathlib import Path

import pdfplumber

PDF_PATH = Path("data/corpus/PreciosPublicos2026.pdf")
OUTPUT_PATH = Path("diagnostico_pdf/precios_tabla_01.png")

# Región en puntos PDF: izquierda, arriba, derecha, abajo.
BBOX = (60, 574, 1812, 1241)

# Resolución de la imagen resultante.
DPI = 100


def guardar_recorte(
    pdf_path: Path,
    output_path: Path,
    bbox: tuple[float, float, float, float],
    pagina: int = 1,
    dpi: int = 100,
) -> Path:
    """Guarda una región del PDF como PNG. Página numerada desde 1."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"No existe el PDF: {pdf_path}")

    if dpi <= 0:
        raise ValueError("La resolución debe ser mayor que cero.")

    with pdfplumber.open(pdf_path) as documento:
        if not 1 <= pagina <= len(documento.pages):
            raise ValueError(
                f"Página {pagina} inválida. "
                f"El PDF tiene {len(documento.pages)} página(s)."
            )

        page = documento.pages[pagina - 1]
        izquierda, arriba, derecha, abajo = bbox
        px0, py0, px1, py1 = page.bbox

        if not (
            px0 <= izquierda < derecha <= px1
            and py0 <= arriba < abajo <= py1
        ):
            raise ValueError(
                f"El recorte {bbox} está fuera de la página "
                f"o tiene límites incorrectos. Límites: {page.bbox}"
            )

        region = page.crop(bbox)
        imagen = region.to_image(resolution=dpi).original.convert("RGB")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        imagen.save(
            output_path,
            format="PNG",
            dpi=(dpi, dpi),
        )

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(f"No se pudo guardar el recorte: {output_path}")

    print(f"Recorte guardado: {output_path.resolve()}")
    print(f"Tamaño: {imagen.width} × {imagen.height} píxeles")

    return output_path


if __name__ == "__main__":
    guardar_recorte(
        pdf_path=PDF_PATH,
        output_path=OUTPUT_PATH,
        bbox=BBOX,
        pagina=1,
        dpi=DPI,
    )