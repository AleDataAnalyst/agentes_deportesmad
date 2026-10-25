# rag/pdf_tabular.py
from pathlib import Path
import os
import sys

MANIFIESTO = "especiales.txt"
ETIQUETA_TABULAR = "TAB"
ETIQUETA_OCR = "OCR"

OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_PSM = os.getenv("OCR_PSM", "6")
TESSERACT_CMD = os.getenv("TESSERACT_CMD") or os.getenv("OCR_AGENT", "")
POPPLER_PATH = os.getenv("POPPLER_PATH") or None


def _extraer_texto_tabla_a_textos(pdf: Path) -> list[str]:
    """
    Extrae el texto de las tablas de un PDF y lo divide en bloques de texto
    comprensibles para el LLM.

    Retorna una lista de strings; cada uno contiene el contenido de una tabla
    o sección del PDF formateado para ser usado como contexto.
    """
    import pdfplumber

    textos: list[str] = []

    with pdfplumber.open(pdf) as documento:
        for numero_pagina, pagina in enumerate(documento.pages, start=1):
            tablas = pagina.extract_tables()

            if not tablas:
                texto = pagina.extract_text()
                if texto:
                    textos.append(f"# Página {numero_pagina}\n{texto}")
                continue

            for indice, tabla in enumerate(tablas, start=1):
                if not tabla or len(tabla) < 2:
                    continue

                headers = [h.strip() if h else "" for h in tabla[0]]
                rows_data = tabla[1:]

                bloques: list[str] = []
                bloques.append(f"# Página {numero_pagina} - Tabla {indice}")

                if headers:
                    bloques.append("| " + " | ".join(headers) + " |")
                    bloques.append("|" + "---|" * len(headers))

                for fila in rows_data:
                    celdas = [
                        ((c or "").strip().replace("|", "\\|")) if c else ""
                        for c in fila
                    ]

                    while len(celdas) < len(headers):
                        celdas.append("")

                    fila_str = " | ".join(celdas[: len(headers)])
                    bloques.append(f"| {fila_str} |")

                textos.append("\n".join(bloques))

    return textos


def _parsear_a_key_value_simple(texto: str) -> dict:
    """
    Intenta extraer pares clave:valor de un texto.

    Busca líneas con el patrón 'clave: valor' o 'clave -> valor'.
    """
    import re

    resultado: dict[str, str] = {}

    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue

        match = re.match(r"^(.+?):\s*(.+)$", linea)
        if match:
            clave = match.group(1).strip()
            valor = match.group(2).strip()
        else:
            match = re.match(r"^(.+?)\s*->\s*(.+)$", linea)
            if not match:
                continue
            clave = match.group(1).strip()
            valor = match.group(2).strip()

        if clave and valor and len(clave) < 50:
            resultado[clave] = valor

    return resultado


def _ocr_pdf(pdf: Path) -> str:
    """
    Convierte el PDF en imágenes y extrae texto mediante Tesseract.

    Usa 200 DPI por defecto y --psm 6, adecuado para bloques/tablas.
    """
    import pytesseract
    from pdf2image import convert_from_path

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    kwargs: dict[str, object] = {"dpi": OCR_DPI}

    if POPPLER_PATH:
        kwargs["poppler_path"] = POPPLER_PATH

    imagenes = convert_from_path(str(pdf), **kwargs)

    texto_ocr = ""
    for imagen in imagenes:
        texto_ocr += pytesseract.image_to_string(
            imagen,
            lang="spa",
            config=f"--psm {OCR_PSM}",
        ) + "\n"

    return texto_ocr.strip()


def cargar_pdfs_especiales(directorio: Path) -> dict[str, list[dict]]:
    """
    Lee el manifiesto y procesa los PDFs según su etiqueta.

    Retorna:
      - "tabular": resultados de PDFs marcados como TAB.
      - "ocr": resultados de PDFs marcados como OCR.
    """
    ruta_manifiesto = directorio / MANIFIESTO

    if not ruta_manifiesto.exists():
        raise FileNotFoundError(f"No existe el manifiesto: {ruta_manifiesto}")

    resultados: dict[str, list[dict]] = {"tabular": [], "ocr": []}

    for linea in ruta_manifiesto.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#") or ":" not in linea:
            continue

        nombre, etiqueta = linea.split(":", 1)
        nombre = nombre.strip()
        etiqueta = etiqueta.strip().upper()

        pdf = directorio / nombre

        if not pdf.exists():
            print(f"[AVISO] PDF declarado pero no encontrado: {pdf}")
            continue

        if etiqueta == ETIQUETA_TABULAR:
            try:
                textos = _extraer_texto_tabla_a_textos(pdf)

                for numero_bloque, texto in enumerate(textos):
                    kv = _parsear_a_key_value_simple(texto)
                    complemento = ""

                    if kv:
                        complemento = (
                            "\n---\nKey-value extraído:\n"
                            + "\n".join(
                                f"{clave}: {valor}"
                                for clave, valor in list(kv.items())[:10]
                            )
                        )

                    resultados["tabular"].append(
                        {
                            "texto": texto + complemento,
                            "fuente": pdf.name,
                            "formato": "tabla-formateada",
                            "numero_tabla": numero_bloque,
                        }
                    )

                print(
                    f"[OK] PDF TAB procesado: {pdf.name} "
                    f"({len(textos)} bloques)"
                )

            except Exception as exc:
                print(f"[ERROR] Error procesando {pdf.name} como TAB: {exc}")

        elif etiqueta == ETIQUETA_OCR:
            try:
                texto_ocr = _ocr_pdf(pdf)

                if not texto_ocr:
                    raise RuntimeError("OCR vacío")

                kv = _parsear_a_key_value_simple(texto_ocr)
                texto_final = texto_ocr

                if kv:
                    texto_final += (
                        "\n---\nKey-value OCR:\n"
                        + "\n".join(
                            f"{clave}: {valor}"
                            for clave, valor in list(kv.items())[:10]
                        )
                    )

                resultados["ocr"].append(
                    {
                        "texto": texto_final,
                        "fuente": pdf.name,
                        "formato": "key-value-ocr",
                    }
                )

                print(f"[OK] PDF OCR procesado: {pdf.name}")

            except Exception as exc:
                print(f"[AVISO] OCR fallido en {pdf.name}: {exc}")

                try:
                    textos = _extraer_texto_tabla_a_textos(pdf)

                    for numero_bloque, texto in enumerate(textos):
                        resultados["ocr"].append(
                            {
                                "texto": texto,
                                "fuente": pdf.name,
                                "formato": "tabla-formateada-fallback",
                                "numero_tabla": numero_bloque,
                            }
                        )

                    print(
                        f"[OK] PDF OCR fallback (texto directo): {pdf.name}"
                    )

                except Exception as exc_fallback:
                    print(
                        f"[ERROR] No se pudo procesar {pdf.name} con OCR "
                        f"ni fallback: {exc_fallback}"
                    )

    return resultados


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python -m rag.pdf_tabular /ruta/al/directorio/corpus"
        )

    directorio = Path(sys.argv[1]).resolve()
    resultados = cargar_pdfs_especiales(directorio)

    print("\n=== Resumen de procesamiento ===")
    print(f"PDFs TAB: {len(resultados['tabular'])} bloques")

    for resultado in resultados["tabular"][:3]:
        print(
            f"  - {resultado['fuente']}: "
            f"{len(resultado['texto'])} caracteres, "
            f"formato {resultado['formato']}"
        )

    print(f"PDFs OCR: {len(resultados['ocr'])} bloques")

    for resultado in resultados["ocr"][:3]:
        print(
            f"  - {resultado['fuente']}: "
            f"{len(resultado['texto'])} caracteres, "
            f"formato {resultado['formato']}"
        )


if __name__ == "__main__":
    main()
    