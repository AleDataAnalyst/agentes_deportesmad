"""
rag/load.py

Abstrae el formato: PDF, TXT, MD, CSV -> lista de LangChain Documents.
-----------------------------------------------------------------------
Los CSV se delegan a ``csv_transform.py`` / ``csv_advisor.py`` (entidad,
grupo o fila por documento según el perfil).

Los TXT y MD se comprueban si son tabulares (CSV/TSV disfrazados de texto
plano): si lo son, una fila = un documento (``row_as_doc`` forzado, sin
pasar por el advisor).

Los PDF declarados como ``TAB`` en ``especiales.txt`` se convierten a
Markdown tabular mediante ``pdf_tabular.py``. El Markdown generado se
carga como un documento más del corpus.
"""

import hashlib
import os
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from .vision import cargar_imagen
from .csv_advisor import CsvAdvice, leer_filas_csv
from .csv_transform import filas_a_documentos, transform_csv
from .pdf_tabular import ETIQUETA_TABULAR, ETIQUETA_OCR, MANIFIESTO, cargar_pdfs_especiales

_LOTES_HASH = 1 << 20  # 1 MiB por lectura en el hash


def _hash_file(ruta: str) -> str:
    """
    SHA-256 hex del contenido binario crudo del archivo, en streaming.

    Identifica unívocamente al archivo de origen: estable entre indexaciones
    y detecta contenido nuevo en una descarga repetida con el mismo nombre.
    """
    digest = hashlib.sha256()

    with open(ruta, "rb") as f:
        while True:
            bloque = f.read(_LOTES_HASH)
            if not bloque:
                break
            digest.update(bloque)

    return digest.hexdigest()


def _normalizar_source(
    documentos: list[Document],
    ruta: str,
) -> list[Document]:
    """
    Normaliza metadata.source al basename del archivo y añade file_hash.

    TextLoader/PyPDFLoader pueden fijar la ruta completa; aquí se fuerza
    siempre el basename para mantener coherencia en dedup, ids y evaluación.
    """
    file_hash = _hash_file(ruta)

    for d in documentos:
        d.metadata["source"] = os.path.basename(ruta)
        d.metadata["file_hash"] = file_hash

    return documentos


def _leer_pdfs_tabulares(directorio: Path) -> set[str]:
    """
    Lee ``especiales.txt`` y devuelve los basenames de PDF marcados como TAB.
    """
    ruta_manifiesto = directorio / MANIFIESTO

    if not ruta_manifiesto.exists():
        return set()

    pdfs_tabulares: set[str] = set()

    for linea in ruta_manifiesto.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#") or ":" not in linea:
            continue

        nombre, etiqueta = linea.split(":", 1)
        nombre = nombre.strip()
        etiqueta = etiqueta.strip().upper()

        if etiqueta == ETIQUETA_TABULAR:
            pdfs_tabulares.add(os.path.basename(nombre))

    return pdfs_tabulares


def _leer_pdfs_ocr_tab(directorio: Path) -> set[str]:
    """
    Lee ``especiales.txt`` y devuelve los basenames de PDF marcados como OCR.
    """
    ruta_manifiesto = directorio / MANIFIESTO

    if not ruta_manifiesto.exists():
        return set()

    pdfs_ocr: set[str] = set()

    for linea in ruta_manifiesto.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#") or ":" not in linea:
            continue

        nombre, etiqueta = linea.split(":", 1)
        nombre = nombre.strip()
        etiqueta = etiqueta.strip().upper()

        if etiqueta == ETIQUETA_OCR:
            pdfs_ocr.add(os.path.basename(nombre))

    return pdfs_ocr


def _load_pdf(
    path: str,
    directorio: Path,
    pdfs_tabulares: set[str],
    pdfs_ocr: set[str],
) -> list[Document]:
    """
    Carga un PDF.

    - Si está marcado como TAB en ``especiales.txt``, extrae texto key-value
      sin transformación a Markdown.
    - Si está marcado como OCR, usa Tesseract OCR y luego key-value.
    - En caso contrario, usa extracción nativa con PyPDFLoader.
    """
    base = os.path.basename(path)

    # Procesar PDFs tabulares (TAB) - key-value sin Markdown
    if base in pdfs_tabulares:
        try:
            resultados = cargar_pdfs_especiales(directorio)
            # Buscar el resultado para este PDF
            for r in resultados["tabular"]:
                if r["fuente"] == base:
                    docs = _load_text_from_kv(r["texto"])
                    for d in docs:
                        d.metadata["source"] = base
                        d.metadata["pdf_source"] = base
                        d.metadata["derived_from"] = f"tabular_key-value"
                        d.metadata["file_type"] = "pdf_tabular_key_value"
                    return docs
            # Fallback: procesar directamente este PDF
            texto_bruto = _extraer_texto_pdf_directo(pdf)
            kv = _parsear_key_value(texto_bruto)
            formatted = _formatear_key_value(kv)
            docs = _load_text_from_kv(formatted)
            for d in docs:
                d.metadata["source"] = base
                d.metadata["pdf_source"] = base
                d.metadata["derived_from"] = "tabular_key-value"
                d.metadata["file_type"] = "pdf_tabular_key_value"
            return docs
        except Exception as e:
            print(
                f"[PDF] AVISO: error procesando {base} como TAB: {e}. "
                "Se usará extracción nativa."
            )

    # Procesar PDFs OCR
    if base in pdfs_ocr:
        try:
            resultados = cargar_pdfs_especiales(directorio)
            for r in resultados["ocr"]:
                if r["fuente"] == base:
                    docs = _load_text_from_kv(r["texto"])
                    for d in docs:
                        d.metadata["source"] = base
                        d.metadata["pdf_source"] = base
                        d.metadata["derived_from"] = f"ocr_key-value"
                        d.metadata["file_type"] = "pdf_ocr_key_value"
                    return docs
        except Exception as e:
            print(f"[PDF] AVISO: error OCR en {base}: {e}")

    # Extracción nativa con PyPDFLoader
    loader = PyPDFLoader(path)
    return _normalizar_source(loader.load(), path)


def _load_text_from_kv(texto_kv: str) -> list[Document]:
    """
    Carga texto key-value como documento LangChain.

    El formato esperado es "clave: valor" por línea, que se convierte en
    page_content estructurado para mejor ingesta por el LLM.
    """
    from langchain_core.documents import Document

    lineas = [l.strip() for l in texto_kv.splitlines() if l.strip()]
    docs = []
    for i, linea in enumerate(lineas):
        d = Document(
            page_content=linea,
            metadata={
                "source": "pdf_key_value",
                "chunk_id": i,
                "file_type": "pdf_key_value",
            },
        )
        docs.append(d)
    return docs


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
    """Detecta la encoding de un archivo probando varias codificaciones."""
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
    sin leer necesariamente todo el fichero.
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

    - Si es tabular, una fila = un documento.
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
    CSV: csv_advisor.py decide el tratamiento y csv_transform.py lo aplica.
    """
    return _normalizar_source(transform_csv(ruta), ruta)


def _formato_documento(source: str) -> str:
    """Devuelve el formato lógico de un documento a partir de su nombre."""
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
    ".jpg": cargar_imagen,
    ".jpeg": cargar_imagen,
    ".png": cargar_imagen,
}


def cargar_archivos(rutas: list[str] | str) -> list[Document]:
    """
    Punto de entrada público.

    Params:
        rutas: una ruta o lista de rutas a archivos/carpetas.

    Returns:
        Lista de Document con page_content y metadata normalizada.
    """
    if isinstance(rutas, str):
        rutas = [rutas]

    todos: list[Path] = []
    archivos: list[str] = []
    directorios: list[Path] = []

    # 1. Descubrir archivos y carpetas
    for ruta in rutas:
        p = Path(ruta)

        if p.is_dir():
            directorios.append(p)
            todos.extend(sorted(p.rglob("*")))
        elif p.is_file():
            todos.append(p)

    # 2. Leer manifiestos de PDFs tabulares y OCR por directorio raíz recibido
    pdfs_tabulares: set[str] = set()
    pdfs_ocr: set[str] = set()

    for directorio in directorios:
        pdfs_tabulares.update(_leer_pdfs_tabulares(directorio))
        pdfs_ocr.update(_leer_pdfs_ocr_tab(directorio))

    if pdfs_tabulares:
        print(f"[LOAD] PDFs tabulares declarados: {sorted(pdfs_tabulares)}")
    if pdfs_ocr:
        print(f"[LOAD] PDFs OCR declarados: {sorted(pdfs_ocr)}")

    # 3. Filtrar archivos indexables; especiales.txt nunca se indexa
    for f in todos:
        if not f.is_file():
            continue

        if f.name == MANIFIESTO:
            continue

        if f.suffix.lower() in _LOADERS:
            archivos.append(str(f))
        else:
            print(f"[LOAD] ignorado (extensión no soportada): {f.name}")

    # 4. Cargar documentos
    documentos: list[Document] = []

    for archivo in archivos:
        ext = Path(archivo).suffix.lower()
        loader_fn = _LOADERS[ext]

        if ext == ".pdf":
            docs = loader_fn(archivo, Path(archivo).parent, pdfs_tabulares, pdfs_ocr)
        elif ext in {".jpg", ".jpeg", ".png"}:
            docs = loader_fn(archivo)
        else:
            docs = loader_fn(archivo)

        file_hash = _hash_file(archivo)

        for i, d in enumerate(docs):
            d.metadata["doc_id"] = i
            d.metadata.setdefault("source", os.path.basename(archivo))
            d.metadata.setdefault("file_hash", file_hash)
            d.metadata.setdefault("document_id", file_hash)
            d.metadata.setdefault(
                "format",
                _formato_documento(os.path.basename(archivo)),

            )

    return documentos