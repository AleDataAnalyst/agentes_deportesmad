"""
rag/load.py

Abstrae el formato: PDF, TXT, MD, CSV -> lista de LangChain Documents.

Los PDF declarados como ``TAB`` en ``especiales.txt`` se convierten a
Markdown tabular mediante ``pdf_tabular.py``. El Markdown generado se
carga como un documento más del corpus.
"""

import hashlib
import os
import re
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
    extraer_piscinas,
)

_LOTES_HASH = 1 << 20  # 1 MiB por lectura en el hash

# Cache por directorio: evita reprocesar TAB/OCR por cada PDF del corpus.
_RESULTADOS_ESPECIALES: dict[Path, dict[str, list[dict]]] = {}

from .file_hash import sha256_archivo


def _hash_file(ruta: str) -> str:
    return sha256_archivo(ruta)

def _normalizar_source(
    documentos: list[Document],
    ruta: str,
) -> list[Document]:
    """Fuerza source al basename y añade file_hash a todos los Documents."""
    file_hash = _hash_file(ruta)

    for documento in documentos:
        documento.metadata["source"] = os.path.basename(ruta)
        documento.metadata["file_hash"] = file_hash

    return documentos


def _leer_pdfs_por_etiqueta(
    directorio: Path,
    etiqueta_esperada: str,
) -> set[str]:
    """Lee ``especiales.txt`` y devuelve los basenames de una etiqueta."""
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


def _leer_pdfs_tabulares(directorio: Path) -> set[str]:
    """Devuelve los PDF marcados como TAB."""
    return _leer_pdfs_por_etiqueta(directorio, ETIQUETA_TABULAR)


def _leer_pdfs_ocr_tab(directorio: Path) -> set[str]:
    """Devuelve los PDF marcados como OCR."""
    return _leer_pdfs_por_etiqueta(directorio, ETIQUETA_OCR)


def _resultados_especiales(directorio: Path) -> dict[str, list[dict]]:
    """
    Procesa ``especiales.txt`` una única vez por directorio.

    Evita repetir OCR y extracción tabular por cada PDF encontrado.
    """
    clave = directorio.resolve()

    if clave not in _RESULTADOS_ESPECIALES:
        _RESULTADOS_ESPECIALES[clave] = cargar_pdfs_especiales(clave)

    return _RESULTADOS_ESPECIALES[clave]

def _load_piscinas_tabular(path: str) -> list[Document]:
    """Carga cada instalación como un documento columna: valor."""
    registros = extraer_piscinas(path)
    base = os.path.basename(path)
    documentos: list[Document] = []

    for row_index, registro in enumerate(registros):
        valores = registro["valores"]

        contenido = (
            "Piscinas municipales al aire libre — Verano 2026\n\n"
            + "\n".join(
                f"{columna}: {valor}"
                for columna, valor in valores.items()
            )
        )

        documentos.append(
            Document(
                page_content=contenido,
                metadata={
                    "source": base,
                    "pdf_source": base,
                    "derived_from": "tabular_geometry",
                    "file_type": "pdf_tabular_key_value",
                    "content_type": "table_row",
                    "dedup_policy": "exact_only",
                    "page": registro["pagina"],
                    "table": registro["tabla"],
                    "row": row_index,
                    "extracted_row": registro["fila_extraida"],
                    "headers": list(valores),
                },
            )
        )

    documentos = _normalizar_source(documentos, path)

    print(
        f"[PDF TAB] {base}: "
        f"{len(documentos)} filas completas | dedup=exact_only"
    )

    return documentos

def _load_pdf(
    path: str,
    directorio_raiz: Path,
    pdfs_tabulares: set[str],
    pdfs_ocr: set[str],
) -> list[Document]:
    """Carga un PDF con perfiles específicos, TAB, OCR o extracción nativa."""
    base = os.path.basename(path)

    # Perfil específico: no pasar por Markdown ni por extracción genérica.
    # Los errores se propagan para evitar indexar una extracción incorrecta.
    if base == "PiscinasAireLibre2026.pdf":
        return _load_piscinas_tabular(path)

    if base in pdfs_tabulares:
        try:
            resultados = _resultados_especiales(directorio_raiz)

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
            resultados = _resultados_especiales(directorio_raiz)

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

            print(
                f"[PDF] AVISO: {base} está marcado como OCR, pero no generó "
                "bloques. Se usará extracción nativa."
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
    """Convierte los bloques TAB/OCR en Documents trazables."""
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


_RE_TITULO = re.compile(r"^# Página (\d+)(?:\s*-\s*Tabla (\d+))?\s*$")
_RE_FILA = re.compile(r"^\|\s*(.+?)\s*\|$")
_RE_SEPARADOR = re.compile(r"^\|?(?:\s*:?-+:?\s*\|)+\s*$")


def _documentos_desde_texto(
    texto: str,
    base: str,
    derived_from: str,
    file_type: str,
    numero_bloque: int,
) -> list[Document]:
    """
    Convierte Markdown tabular en Documents.

    Una fila de tabla = un Document. La cabecera se incluye en el contenido
    y en metadata; el título de página/tabla se conserva como metadato.
    """
    documentos: list[Document] = []
    pagina: int | None = None
    tabla: int | None = None
    cabeceras: list[str] = []

    for linea in texto.splitlines():
        linea = linea.strip()

        if not linea:
            continue

        titulo = _RE_TITULO.match(linea)
        if titulo:
            pagina = int(titulo.group(1))
            tabla = int(titulo.group(2)) if titulo.group(2) else None
            cabeceras = []
            continue

        if _RE_SEPARADOR.match(linea):
            continue

        fila = _RE_FILA.match(linea)
        if not fila:
            continue

        celdas = [
            celda.strip().replace("\\|", "|")
            for celda in fila.group(1).split("|")
        ]

        if not cabeceras:
            cabeceras = celdas
            continue

        pares = list(zip(cabeceras, celdas))
        contenido = "\n".join(
            f"{clave}: {valor}"
            for clave, valor in pares
            if clave or valor
        )

        if not contenido:
            continue

        documentos.append(
            Document(
                page_content=contenido,
                metadata={
                    "source": base,
                    "pdf_source": base,
                    "derived_from": derived_from,
                    "file_type": file_type,
                    "block_index": numero_bloque,
                    "page": pagina,
                    "table": tabla,
                    "headers": cabeceras,
                },
            )
        )

    if not documentos and texto.strip():
        # OCR y PDFs TAB sin tablas Markdown también contienen evidencia.
        # Conservar el bloque completo evita perder contexto entre líneas.
        documentos.append(Document(
            page_content=texto.strip(),
            metadata={
                "source": base, "pdf_source": base,
                "derived_from": derived_from, "file_type": file_type,
                "block_index": numero_bloque,
            },
        ))
    return documentos


def _fallback_tab_directo(
    path: str,
    base: str,
) -> list[Document]:
    """Fallback para un PDF TAB sin resultados en el procesamiento por lotes."""
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
            complemento = (
                "\n---\nKey-value extraído:\n"
                + "\n".join(
                    f"{clave}: {valor}"
                    for clave, valor in list(kv.items())[:10]
                )
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

    return "latin-1"


_TAB_MIN_FILAS = 50
_TAB_MIN_COLS = 2


def _es_tabular(ruta: str) -> bool:
    """Determina si un TXT/MD es realmente tabular."""
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
    """Carga TXT/MD: fila por Document si es tabular; texto plano si no."""
    if _es_tabular(ruta):
        columnas, filas = leer_filas_csv(ruta)

        source = urllib.parse.unquote(Path(ruta).name)

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
    """Carga CSV mediante csv_advisor y csv_transform."""
    return _normalizar_source(transform_csv(ruta), ruta)


def _formato_documento(source: str) -> str:
    """Devuelve el formato lógico a partir de la extensión."""
    extension = Path(source).suffix.lower().lstrip(".")

    return {
        "pdf": "pdf",
        "csv": "csv",
        "json": "json",
        "txt": "txt",
        "md": "md",
    }.get(extension, "otro")


Loader = Callable[..., list[Document]]

_LOADERS: dict[str, Loader] = {
    ".pdf": _load_pdf,
    ".txt": _load_txt,
    ".md": _load_txt,
    ".csv": _load_csv,
}


def cargar_archivos(
    rutas: list[str] | str,
    auditoria_archivos: list[dict] | None = None,
) -> list[Document]:
    """
    Punto de entrada público.

    Acepta una ruta o lista de rutas a archivos/carpetas y devuelve Documents
    normalizados para indexación.
    """
    if isinstance(rutas, str):
        rutas = [rutas]

    todos: list[Path] = []
    archivos: list[str] = []
    directorios: list[Path] = []

    for ruta in rutas:
        ruta_path = Path(ruta)

        if ruta_path.is_dir():
            directorios.append(ruta_path)
            todos.extend(sorted(ruta_path.rglob("*")))
        elif ruta_path.is_file():
            todos.append(ruta_path)

    pdfs_tabulares: set[str] = set()
    pdfs_ocr: set[str] = set()

    for directorio in directorios:
        pdfs_tabulares.update(_leer_pdfs_tabulares(directorio))
        pdfs_ocr.update(_leer_pdfs_ocr_tab(directorio))

    if pdfs_tabulares:
        print(f"[LOAD] PDFs tabulares declarados: {sorted(pdfs_tabulares)}")

    if pdfs_ocr:
        print(f"[LOAD] PDFs OCR declarados: {sorted(pdfs_ocr)}")

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

    documentos: list[Document] = []

    for archivo in archivos:
        extension = Path(archivo).suffix.lower()
        loader_fn = _LOADERS[extension]

        if extension == ".pdf":
            # La raíz del manifiesto es el primer directorio recibido,
            # no la carpeta inmediata del PDF.
            directorio_raiz = directorios[0] if directorios else Path(archivo).parent

            docs = loader_fn(
                archivo,
                directorio_raiz,
                pdfs_tabulares,
                pdfs_ocr,
            )
        else:
            docs = loader_fn(archivo)

        file_hash = _hash_file(archivo)

        if auditoria_archivos is not None:
            auditoria_archivos.append(
                {
                    "ruta": str(Path(archivo).resolve()),
                    "source": Path(archivo).name,
                    "sha256_carga": file_hash,
                    "documentos_cargados": len(docs),
                }
            )

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
