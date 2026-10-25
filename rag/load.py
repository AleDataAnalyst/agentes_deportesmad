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

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from .csv_advisor import CsvAdvice, leer_filas_csv
from .csv_transform import filas_a_documentos, transform_csv
from .pdf_tabular import (
    ETIQUETA_OCR,
    ETIQUETA_TABULAR,
    MANIFIESTO,
    _extraer_texto_tabla_a_textos,
    _parsear_a_key_value_simple,
    cargar_pdfs_especiales,
)

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

    for documento in documentos:
        documento.metadata["source"] = os.path.basename(ruta)
        documento.metadata["file_hash"] = file_hash

    return documentos


def _leer_pdfs_tabulares(directorio: Path) -> set[str]:
    """
    Lee ``especiales.txt`` y devuelve los basenames de PDF marcados como TAB.
    """
    return _leer_pdfs_por_etiqueta(
        directorio,
        ETIQUETA_TABULAR,
    )


def _leer_pdfs_ocr_tab(directorio: Path) -> set[str]:
    """
    Lee ``especiales.txt`` y devuelve los basenames de PDF marcados como OCR.
    """
    return _leer_pdfs_por_etiqueta(
        directorio,
        ETIQUETA_OCR,
    )


def _leer_pdfs_por_etiqueta(
    directorio: Path,
    etiqueta_esperada: str,
) -> set[str]:
    """
    Lee el manifiesto ``especiales.txt`` y devuelve los basenames de PDF
    asociados a una etiqueta concreta.
    """
    ruta_manifiesto = directorio / MANIFIESTO

    if not ruta_manifiesto.exists():
        return set()

    pdfs: set[str] = set()

    for linea in ruta_manifiesto.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()

        if not linea or linea.startswith("#") or ":" not in linea:
            continue

        nombre, etiqueta = linea.split(":", 1)
        nombre = nombre.strip()
        etiqueta = etiqueta.strip().upper()

        if etiqueta == etiqueta_esperada:
            pdfs.add(os.path.basename(nombre))

    return pdfs


def _load_pdf(
    path: str,
    directorio: Path,
    pdfs_tabulares: set[str],
    pdfs_ocr: set[str],
) -> list[Document]:
    """
    Carga un PDF.

    - Si está marcado como TAB en ``especiales.txt``, carga todos los bloques
      tabulares/páginas extraídos por ``cargar_pdfs_especiales``.
    - Si está marcado como OCR, carga todos los bloques OCR disponibles.
    - Si no hay resultados para el PDF TAB, intenta una extracción directa.
    - En caso contrario, usa extracción nativa con PyPDFLoader.
    """
    base = os.path.basename(path)

    if base in pdfs_tabulares:
        try:
            resultados = cargar_pdfs_especiales(directorio)

            bloques = [
                resultado
                for resultado in resultados["tabular"]
                if resultado["fuente"] == base
            ]

            if bloques:
                return _documentos_desde_bloques(
                    bloques=bloques,
                    base=base,
                    derived_from="tabular_key-value",
                    file_type="pdf_tabular_key_value",
                )

            return _fallback_tab_directo(
                path=path,
                base=base,
            )
        except Exception as exc:
            print(
                f"[PDF] AVISO: error procesando {base} como TAB: {exc}. "
                "Se usará extracción nativa."
            )

    if base in pdfs_ocr:
        try:
            resultados = cargar_pdfs_especiales(directorio)

            bloques = [
                resultado
                for resultado in resultados["ocr"]
                if resultado["fuente"] == base
            ]

            if bloques:
                return _documentos_desde_bloques(
                    bloques=bloques,
                    base=base,
                    derived_from="ocr_key-value",
                    file_type="pdf_ocr_key_value",
                )
        except Exception as exc:
            print(f"[PDF] AVISO: error OCR en {base}: {exc}")

    loader = PyPDFLoader(path)
    return _normalizar_source(loader.load(), path)


def _documentos_desde_bloques(
    bloques: list[dict],
    base: str,
    derived_from: str,
    file_type: str,
) -> list[Document]:
    """
    Convierte todos los bloques extraídos de un PDF en Documents con
    metadata de trazabilidad.

    Cada bloque puede representar una página, una tabla o una sección
    detectada por ``pdf_tabular.cargar_pdfs_especiales``.
    """
    documentos: list[Document] = []

    for numero_bloque, bloque in enumerate(bloques):
        texto = bloque.get("texto", "")

        if not texto.strip():
            continue

        documentos.extend(
            _documentos_desde_texto(
                texto=texto,
                base=base,
                derived_from=derived_from,
                file_type=file_type,
                numero_bloque=numero_bloque,
            )
        )

    if not documentos:
        raise ValueError(
            f"El PDF {base!r} no generó documentos a partir de "
            f"{len(bloques)} bloque(s) extraído(s)."
        )

    return documentos


def _documentos_desde_texto(
    texto: str,
    base: str,
    derived_from: str,
    file_type: str,
    numero_bloque: int,
) -> list[Document]:
    """
    Convierte el texto de un bloque TAB/OCR en Documents.

    Se conserva una línea por Document para mantener granularidad en la
    ingesta, pero cada Document conserva el número de bloque de origen.
    """
    lineas = [
        linea.strip()
        for linea in texto.splitlines()
        if linea.strip()
    ]

    documentos: list[Document] = []

    for indice_linea, linea in enumerate(lineas):
        documentos.append(
            Document(
                page_content=linea,
                metadata={
                    "source": base,
                    "pdf_source": base,
                    "derived_from": derived_from,
                    "file_type": file_type,
                    "block_index": numero_bloque,
                    "line_index": indice_linea,
                },
            )
        )

    return documentos


def _fallback_tab_directo(
    path: str,
    base: str,
) -> list[Document]:
    """
    Fallback para un PDF TAB sin resultados en el procesamiento por lotes.

    Extrae directamente tablas y texto mediante ``pdfplumber`` y añade, cuando
    es posible, pares clave-valor detectados en el texto.
    """
    textos = _extraer_texto_tabla_a_textos(Path(path))

    if not textos:
        raise ValueError(
            f"No se pudo extraer contenido TAB directamente de {base!r}."
        )

    bloques: list[dict] = []

    for numero_bloque, texto in enumerate(textos):
        texto_final = texto

        kv = _parsear_a_key_value_simple(texto)

        if kv:
            complemento = "\n---\nKey-value extraído:\n" + "\n".join(
                f"{clave}: {valor}"
                for clave, valor in list(kv.items())[:10]
            )
            texto_final += complemento

        bloques.append(
            {
                "texto": texto_final,
                "fuente": base,
                "formato": "tabla-formateada-fallback",
                "numero_tabla": numero_bloque,
            }
        )

    return _documentos_desde_bloques(
        bloques=bloques,
        base=base,
        derived_from="tabular_key-value-fallback",
        file_type="pdf_tabular_key_value",
    )


def _load_text_from_kv(texto_kv: str) -> list[Document]:
    """
    Carga texto key-value como documento LangChain.

    El formato esperado es "clave: valor" por línea, que se convierte en
    page_content estructurado para mejor ingesta por el LLM.
    """
    lineas = [
        linea.strip()
        for linea in texto_kv.splitlines()
        if linea.strip()
    ]

    return [
        Document(
            page_content=linea,
            metadata={
                "source": "pdf_key_value",
                "chunk_id": indice,
                "file_type": "pdf_key_value",
            },
        )
        for indice, linea in enumerate(lineas)
    ]


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

    for encoding in _CODIFICACIONES:
        try:
            raw.decode(encoding)
            return encoding
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

        documentos = filas_a_documentos(
            source,
            filas,
            columnas,
            advice,
        )

        return _normalizar_source(documentos, ruta)

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
    extension = Path(source).suffix.lower().lstrip(".")

    return {
        "pdf": "pdf",
        "csv": "csv",
        "json": "json",
        "txt": "txt",
        "md": "md",
    }.get(extension, "otro")


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
        Lista de Document con page_content y metadata normalizada.
    """
    if isinstance(rutas, str):
        rutas = [rutas]

    todos: list[Path] = []
    archivos: list[str] = []
    directorios: list[Path] = []

    # 1. Descubrir archivos y carpetas
    for ruta in rutas:
        ruta_path = Path(ruta)

        if ruta_path.is_dir():
            directorios.append(ruta_path)
            todos.extend(sorted(ruta_path.rglob("*")))
        elif ruta_path.is_file():
            todos.append(ruta_path)

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
    for archivo in todos:
        if not archivo.is_file():
            continue

        if archivo.name == MANIFIESTO:
            continue

        if archivo.suffix.lower() in _LOADERS:
            archivos.append(str(archivo))
        else:
            print(
                f"[LOAD] ignorado (extensión no soportada): {archivo.name}"
            )

    # 4. Cargar documentos
    documentos: list[Document] = []

    for archivo in archivos:
        extension = Path(archivo).suffix.lower()
        loader_fn = _LOADERS[extension]

        if extension == ".pdf":
            docs = loader_fn(
                archivo,
                Path(archivo).parent,
                pdfs_tabulares,
                pdfs_ocr,
            )
        else:
            docs = loader_fn(archivo)

        file_hash = _hash_file(archivo)

        for indice, documento in enumerate(docs):
            documento.metadata["doc_id"] = indice
            documento.metadata.setdefault(
                "source",
                os.path.basename(archivo),
            )
            documento.metadata.setdefault("file_hash", file_hash)
            documento.metadata.setdefault(
                "format",
                _formato_documento(os.path.basename(archivo)),
            )

        documentos.extend(docs)

    return documentos

    """Cambios clave
    _load_pdf() ya no retorna en el primer bloque coincidente: filtra todos los bloques cuyo fuente sea el PDF actual.
    
    El fallback TAB usa _extraer_texto_tabla_a_textos() y _parsear_a_key_value_simple(), que sí existen en pdf_tabular.py; desaparece la referencia a pdf, que estaba indefinida.
    
    Cada documento TAB/OCR conserva source, pdf_source, derived_from, file_type, block_index y line_index, lo que permite auditar cobertura y procedencia.
    
    Si un PDF TAB declarado no genera ningún documento, se lanza un error explícito en el fallback en lugar de caer silenciosamente a extracción nativa; si el fallback mismo falla, entonces sí se registra el aviso y se usa PyPDFLoader.
    
    _leer_pdfs_tabulares() y _leer_pdfs_ocr_tab() se unifican en _leer_pdfs_por_etiqueta() para eliminar duplicación.
    """