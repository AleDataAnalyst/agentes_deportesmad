"""
rag/load.py

Abstrae el formato: PDF, TXT, MD, CSV -> lista de LangChain Documents.
-----------------------------------------------------------------------
Los CSV se delegan a ``csv_transform.py`` / ``csv_advisor.py`` (entidad,
grupo o fila por documento según el perfil).
Los TXT y MD se comprueban si son tabulares (CSV/TSV disfrazados de texto
plano): si lo son, una fila = un documento (``row_as_doc`` forzado, sin
pasar por el advisor).
--------------------------------------------------------------------------
Si un PDF aparece en ``OCR.txt`` con acción ``OCR``, pasa obligatoriamente
por OCR, aunque tenga texto nativo.
Para los PDFs marcados como OCR se usa Tesseract con ``--psm 6``, pensado
para bloques uniformes de texto: listados, horarios y tablas sencillas
"""

import urllib.parse
import hashlib
import os
from pathlib import Path
from collections.abc import Callable
from typing import List

from pdf2image import convert_from_path
import pytesseract

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

from .csv_advisor import CsvAdvice, leer_filas_csv
from .csv_transform import filas_a_documentos, transform_csv


_LOTES_HASH = 1 << 20  # 1 MiB por lectura en el hash

OCR_AGENT = os.environ.get("OCR_AGENT", "tesseract")

# PSM 6: Tesseract asume un único bloque uniforme de texto.
# Es una buena opción para PDFs tipo listado, horario o tabla sencilla.
OCR_PSM = int(os.environ.get("OCR_PSM", "6"))

# Conserva espacios entre palabras: útil para no fusionar columnas.
OCR_CONFIG = (
    f"--psm {OCR_PSM} "
    "-c preserve_interword_spaces=1"
)

# Resolución de conversión PDF -> imagen.
# 300 DPI es un buen equilibrio entre calidad OCR y coste.
OCR_DPI = int(os.environ.get("OCR_DPI", "300"))

# Ruta de Poppler en Windows. Debe apuntar a la carpeta que contiene
# pdfinfo.exe y pdftoppm.exe. En Linux/Docker normalmente no hace falta.
POPPLER_PATH = os.environ.get(
    "POPPLER_PATH",
    r"C:\tools\poppler-25.07.0\Library\bin",
)


def _hash_file(ruta: str) -> str:
    """
    SHA-256 hex del contenido binario crudo del archivo, en streaming.

    Identifica unívocamente al archivo de origen: estable entre indexaciones
    y detecta contenido nuevo en una descarga repetida con el mismo nombre
    """
    digest = hashlib.sha256()

    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(_LOTES_HASH)
            if not bloque:
                break
            digest.update(bloque)

    return digest.hexdigest()


def leer_config_ocr(ruta: str) -> dict[str, str]:
    """
    Lee OCR.txt y devuelve {nombre_archivo: accion}.

    Cada línea válida tiene el formato:

        nombre.pdf: OCR
        nombre.pdf: NO_OCR

    Las líneas vacías y las que empiezan por '#' se ignoran
    """
    resultado: dict[str, str] = {}

    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()

            if not linea or linea.startswith("#"):
                continue

            try:
                nombre, accion = linea.split(":", 1)
            except ValueError:
                print(f"[LOAD] línea OCR.txt mal formada ignorada: {linea!r}")
                continue

            resultado[os.path.basename(nombre.strip())] = accion.strip().upper()

    return resultado


def _normalizar_source(
    documentos: list[Document],
    ruta: str,
) -> list[Document]:
    """
    Normaliza metadata.source al basename del archivo y añade file_hash.

    TextLoader/PyPDFLoader pueden fijar la ruta completa; aquí se fuerza
    siempre el basename para mantener coherencia en dedup, ids y evaluación
    """
    file_hash = _hash_file(ruta)

    for d in documentos:
        d.metadata["source"] = os.path.basename(ruta)
        d.metadata["file_hash"] = file_hash

    return documentos


def _ocr_pdf(path: str, nombre: str) -> list[Document]:
    """Diagnóstico: extrae texto y tablas nativas con pdfplumber."""
    import pdfplumber

    print(f"[PDF] Extrayendo texto/tablas nativas de {nombre}")

    docs: list[Document] = []

    try:
        with pdfplumber.open(path) as pdf:
            for i, pagina in enumerate(pdf.pages):
                texto = pagina.extract_text() or ""
                tablas = pagina.extract_tables() or []

                contenido = texto

                for tabla in tablas:
                    filas = [
                        " | ".join("" if celda is None else str(celda).strip() for celda in fila)
                        for fila in tabla
                    ]
                    contenido += "\n\n" + "\n".join(filas)

                docs.append(
                    Document(
                        page_content=contenido.strip(),
                        metadata={
                            "page": i + 1,
                            "source": nombre,
                            "file_type": "pdf_native_table",
                            "ocr_reason": "native_extraction",
                        },
                    )
                )

    except Exception as exc:
        print(f"[PDF] ERROR extrayendo {nombre}: {exc}")
        return []

    return docs


def _load_pdf(
    path: str,
    nombres_ocr: set[str] | None = None,
) -> list[Document]:
    """
    Carga un PDF.

    - Si su basename está en OCR.txt con acción OCR: OCR obligatorio.
    - En caso contrario: extracción nativa con PyPDFLoader
    """
    nombres_ocr = nombres_ocr or set()
    base = os.path.basename(path)

    if base in nombres_ocr:
        return _ocr_pdf(path, base)

    loader = PyPDFLoader(path)
    return _normalizar_source(loader.load(), path)


# En orden de preferencia:
# - utf-8-sig maneja BOM.
# - cp1252 mapea mejor que latin-1 guiones y comillas típicas de Windows.
# - latin-1 decodifica cualquier secuencia de bytes.
_CODIFICACIONES: tuple[str, ...] = (
    "utf-8-sig",
    "cp1252",
    "latin-1",
)


def _detectar_encoding(ruta: str) -> str:
    """
    Detecta la encoding de un archivo probando varias codificaciones
    """
    raw = Path(ruta).read_bytes()

    for enc in _CODIFICACIONES:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue

    # latin-1 decodifica cualquier byte, pero se mantiene como fallback.
    return "latin-1"


# Heurística de tabulares: mínimos de filas y columnas para considerar
# tabular un .txt/.md. Exige número de columnas estable y suficientes filas.
_TAB_MIN_FILAS = 50
_TAB_MIN_COLS = 2


def _es_tabular(ruta: str) -> bool:
    """
    ¿Es un .txt/.md realmente tabular (CSV/TSV disfrazado de texto plano)?

    Reutiliza ``leer_filas_csv`` y muestrea las primeras filas para decidir
    sin leer necesariamente todo el fichero
    """
    try:
        columnas, filas = leer_filas_csv(
            ruta,
            sample_size=_TAB_MIN_FILAS,
        )
    except Exception as exc:  # noqa: BLE001
        print(
            f"[LOAD] {os.path.basename(ruta)}: no tabular "
            f"({exc.__class__.__name__}): {exc}"
        )
        return False

    return len(columnas) >= _TAB_MIN_COLS and len(filas) >= _TAB_MIN_FILAS


def _load_txt(ruta: str) -> list[Document]:
    """
    TXT/MD:

    - Si es tabular, una fila = un documento
    - Si no, texto plano: un documento por archivo.
    """
    if _es_tabular(ruta):
        columnas, filas = leer_filas_csv(ruta)

        source = urllib.parse.unquote(Path(ruta).name)
        print(f"source: {source}")

        advice = CsvAdvice(
            source=source,
            csv_kind="tabular_txt",
            treatment="row_as_doc",
            dedup_policy="exact_only",
            confidence=1.0,
            reason="tabular .txt/.md: row_as_doc forzado (sin advisor)",
        )

        docs = filas_a_documentos(
            source,
            filas,
            columnas,
            advice,
        )

        return _normalizar_source(docs, ruta)

    return _load_text(ruta)


def _load_text(ruta: str) -> list[Document]:
    """Carga TXT/MD como texto plano usando la encoding detectada."""
    loader = TextLoader(
        ruta,
        encoding=_detectar_encoding(ruta),
    )
    return _normalizar_source(loader.load(), ruta)


def _load_csv(ruta: str) -> list[Document]:
    """
    CSV: csv_advisor.py decide el tratamiento y csv_transform.py lo aplica
    """
    return _normalizar_source(transform_csv(ruta), ruta)


def _formato_documento(source: str) -> str:
    """
    Devuelve el formato lógico de un documento a partir de su nombre
    """
    ext = Path(source).suffix.lower().lstrip(".")

    return {
        "pdf": "pdf",
        "csv": "csv",
        "json": "json",
        "txt": "txt",
        "md": "md",
    }.get(ext, "otro")


# Registro extensión -> loader.
# .txt/.md comparten el loader tabular-aware.
Loader = Callable[..., list[Document]]

_LOADERS: dict[str, Loader] = {
    ".pdf": _load_pdf,
    ".txt": _load_txt,
    ".md": _load_txt,
    ".csv": _load_csv,
}


def cargar_archivos(rutas: list[str] | str) -> list[Document]:
    """
    Punto de entrada público.

    Params:
        rutas: una ruta o lista de rutas a archivos/carpetas.

    Returns:
        Lista de Document con page_content y metadata normalizada
    """
    if isinstance(rutas, str):
        rutas = [rutas]

    todos: list[Path] = []
    archivos: list[str] = []
    ruta_ocr: str | None = None
    nombres_ocr: set[str] = set()

    # 1. Descubrir archivos y carpetas
    for ruta in rutas:
        p = Path(ruta)

        if p.is_dir():
            todos.extend(sorted(p.rglob("*")))
        elif p.is_file():
            todos.append(p)

    # 2. Localizar OCR.txt antes de filtrar por extensión
    for f in todos:
        if f.is_file() and f.name == "OCR.txt":
            ruta_ocr = str(f)
            break

    # 3. Leer configuración OCR
    if ruta_ocr:
        config = leer_config_ocr(ruta_ocr)

        nombres_ocr = {
            nombre
            for nombre, accion in config.items()
            if accion == "OCR"
        }

        print(f"[LOAD] forzados por OCR.txt: {sorted(nombres_ocr)}")

    # 4. Filtrar archivos indexables; OCR.txt nunca se indexa
    for f in todos:
        if not f.is_file():
            continue

        if f.name == "OCR.txt":
            continue

        if f.suffix.lower() in _LOADERS:
            archivos.append(str(f))
        else:
            print(f"[LOAD] ignorado (extensión no soportada): {f.name}")

    # 5. Cargar documentos
    documentos: list[Document] = []

    for archivo in archivos:
        ext = Path(archivo).suffix.lower()
        loader_fn = _LOADERS[ext]

        if ext == ".pdf":
            docs = loader_fn(archivo, nombres_ocr)
        else:
            docs = loader_fn(archivo)

        file_hash = _hash_file(archivo)

        for i, d in enumerate(docs):
            d.metadata["doc_id"] = i
            d.metadata.setdefault("source", os.path.basename(archivo))
            d.metadata.setdefault("file_hash", file_hash)
            d.metadata.setdefault(
                "format",
                _formato_documento(os.path.basename(archivo)),
            )

        documentos.extend(docs)

    return documentos