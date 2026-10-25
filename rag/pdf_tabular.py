# rag/pdf_tabular.py
from pathlib import Path
import sys
import os

MANIFIESTO = "especiales.txt"
ETIQUETA_TABULAR = "TAB"
ETIQUETA_OCR = "OCR"


def _extraer_texto_tabla_a_textos(pdf: Path) -> list[str]:
    """
    Extrae el texto de las tablas de un PDF y lo divide en bloques de texto
    comprensibles para el LLM.

    Retorna una lista de strings, cada uno containing el contenido de una tabla
    o sección del PDF formateado para ser usado como contexto.
    """
    import pdfplumber

    textos: list[str] = []
    with pdfplumber.open(pdf) as documento:
        for numero_pagina, pagina in enumerate(documento.pages, start=1):
            tablas = pagina.extract_tables()

            if not tablas:
                # Si no hay tablas, extraer texto plano
                texto = pagina.extract_text()
                if texto:
                    textos.append(f"# Página {numero_pagina}\n{texto}")
                continue

            for indice, tabla in enumerate(tablas, start=1):
                if not tabla or len(tabla) < 2:
                    continue

                # Primera fila = encabezados
                headers = [h.strip() if h else "" for h in tabla[0]]
                rows_data = tabla[1:]

                # Formatear como texto con encabezados
                bloques: list[str] = []
                bloques.append(f"# Página {numero_pagina} - Tabla {indice}")

                if headers:
                    bloques.append("| " + " | ".join(headers) + " |")
                    bloques.append("|-" + "-|-" * len(headers) + "|")

                for fila in rows_data:
                    # Limpiar celdas vacías
                    celdas = [((c or "").strip().replace("|", "\\|")) if c else "" for c in fila]
                    # Asegurar que tenga la misma cantidad de columnas que encabezados
                    while len(celdas) < len(headers):
                        celdas.append("")
                    fila_str = " | ".join(celdas[:len(headers)])
                    bloques.append(f"| {fila_str} |")

                textos.append("\n".join(bloques))

    return textos


def _parsear_a_key_value_simple(texto: str) -> dict:
    """
    Intenta extraer pares clave:valor de un texto.

    Busca líneas que coincidan con el patrón 'clave: valor' o similar.
    Retorna un dict con los pares encontrados.
    """
    import re

    resultado = {}
    # Patrones: "clave: valor", "clave - valor", "clave -> valor"
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue

        # Intentar "clave: valor"
        match = re.match(r"^(.+?):\s*(.+)$", linea)
        if match:
            clave = match.group(1).strip()
            valor = match.group(2).strip()
            if clave and valor and len(clave) < 50:  # Evitar claves muy largas
                resultado[clave] = valor
        else:
            # Intentar "clave -> valor"
            match2 = re.match(r"^(.+?)\s*-\>\s*(.+)$", linea)
            if match2:
                clave = match2.group(1).strip()
                valor = match2.group(2).strip()
                if clave and valor and len(clave) < 50:
                    resultado[clave] = valor

    return resultado


def cargar_pdfs_especiales(directorio: Path) -> dict[str, list[dict]]:
    """
    Lee el manifiesto y procesa los PDFs según su etiqueta.

    Retorna un dict con:
      - "tabular": lista de resultados para archivos TAB
      - "ocr": lista de resultados para archivos OCR

    Cada elemento tiene:
      - "texto": texto formateado para contexto LLM
      - "fuente": nombre del archivo
      - "formato": tipo de formato ("tabla-formateada", "key-value", etc.)
    """
    ruta_manifiesto = directorio / MANIFIESTO

    if not ruta_manifiesto.exists():
        raise FileNotFoundError(f"No existe el manifiesto: {ruta_manifiesto}")

    resultados = {"tabular": [], "ocr": []}

    for linea in ruta_manifiesto.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#"):
            continue

        if ":" not in linea:
            continue

        nombre, etiqueta = linea.split(":", 1)
        nombre = nombre.strip()
        etiqueta = etiqueta.strip().upper()

        pdf = directorio / nombre

        if not pdf.exists():
            print(f"[AVISO] PDF declarado pero no encontrado: {pdf}")
            continue

        if etiqueta == ETIQUETA_TABULAR:
            # Procesar PDF TAB: extraer tablas y formatear como texto
            try:
                textos = _extraer_texto_tabla_a_textos(pdf)
                for i, texto in enumerate(textos):
                    # También intentar parsear key-value simple como complemento
                    kv = _parsear_a_key_value_simple(texto)
                    complemento = ""
                    if kv:
                        complemento = "\n---\nKey-value extraído:\n" + "\n".join(
                            f"{k}: {v}" for k, v in list(kv.items())[:10]
                        )

                    resultados["tabular"].append({
                        "texto": texto + complemento,
                        "fuente": pdf.name,
                        "formato": "tabla-formateada",
                        "numero_tabla": i,
                    })
                print(f"[OK] PDF TAB procesado (textos formateados): {pdf.name} ({len(textos)} bloques)")
            except Exception as e:
                print(f"[ERROR] Error procesando {pdf.name} como TAB: {e}")

        elif etiqueta == ETIQUETA_OCR:
            # Procesar PDF OCR: intentar OCR con Tesseract, fallback a extracción directa
            try:
                # Intentar OCR (requiere tesseract)
                import pytesseract
                from pdf2image import convert_from_path

                imagenes = convert_from_path(str(pdf), dpi=300)
                texto_ocr = ""
                for img in imagenes:
                    texto_ocr += pytesseract.image_to_string(img, lang="spa") + "\n"

                if texto_ocr.strip():
                    # Intentar parsear key-value
                    kv = _parsear_a_key_value_simple(texto_ocr)
                    texto_final = texto_ocr
                    if kv:
                        kv_text = "\n".join(f"{k}: {v}" for k, v in list(kv.items())[:10])
                        texto_final = texto_ocr + "\n---\nKey-value OCR:\n" + kv_text

                    resultados["ocr"].append({
                        "texto": texto_final,
                        "fuente": pdf.name,
                        "formato": "key-value-ocr",
                    })
                    print(f"[OK] PDF OCR procesado (key-value): {pdf.name}")
                else:
                    # Fallback: texto vacío de OCR, usar extracción directa
                    raise Exception("OCR vacío")

            except Exception as e:
                # Fallback: extraer texto directo con pdfplumber
                try:
                    textos = _extraer_texto_tabla_a_textos(pdf)
                    for i, texto in enumerate(textos):
                        resultados["ocr"].append({
                            "texto": texto,
                            "fuente": pdf.name,
                            "formato": "tabla-formateada-fallback",
                            "numero_tabla": i,
                        })
                    print(f"[OK] PDF OCR fallback (texto directo): {pdf.name}")
                except Exception as e2:
                    print(f"[ERROR] No se pudo procesar {pdf.name} con OCR ni fallback: {e2}")

    return resultados


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python pdf_tabulares_desde_manifiesto.py /ruta/corpus")

    directorio = Path(sys.argv[1]).resolve()
    resultados = cargar_pdfs_especiales(directorio)

    print(f"\n=== Resumen de procesamiento ===")
    print(f"PDFs TAB (formato tabla): {len(resultados['tabular'])} bloques")
    for r in resultados["tabular"][:3]:  # Mostrar solo los primeros 3
        print(f"  - {r['fuente']}: {len(r['texto'])} chars, formato {r['formato']}")

    print(f"\nPDFs OCR (formato): {len(resultados['ocr'])} bloques")
    for r in resultados["ocr"][:3]:
        print(f"  - {r['fuente']}: {len(r['texto'])} chars, formato {r['formato']}")


if __name__ == "__main__":
    main()