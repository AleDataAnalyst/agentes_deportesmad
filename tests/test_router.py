"""
tests/test_router.py

Tests de pre-procesamiento de datos (rag/clean.py).
Verifica que un archivo .csv y un .pdf pasen por normalizar_por_formato y
lleguen con contenido BIEN FORMADO (sin bytes binarios ni caracteres de
control) antes de llegar a la fase de etiquetado (etiquetar / TAG).
"""
import pytest
from langchain_core.documents import Document

from rag.load import _formato_documento
from rag.clean import (
    normalizar_por_formato,
    _limpiar_pdf,
    _limpiar_csv,
)


def _doc(source: str, content: str) -> Document:
    return Document(
        page_content=content,
        metadata={"source": source, "format": _formato_documento(source)},
    )


# Contenido de prueba
# Archivo CSV realista (el que antes daba JSON malformado).
CSV_RAW = (
    "Codigo_temporada,Codigo,Nombre\n"
    "2024-01,A,Abono piscina\n"
    "2024-02,B,Reserva pista"
)

# Extracto de PDF con ruido binario típico (los bytes que rompen el JSON).
PDF_RAW = (
    "%PDF-1.4\x00\x01\n"
    "1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    "2 0 obj\n<< /Pages /Type /Pages >>\nendobj\n"
    "trailer\n<< /Root 1 0 R >>\n%%EOF"
)

JSON_RAW = '{"categoria": "instalaciones", "relevancia": 0.5}'

_CONTROL_ADMITIDOS = frozenset("\n\t\r")

def _sin_control(texto: str) -> bool:
    """True si no hay bytes de control invisibles (admite tabulación)."""
    if not texto:
        return True
    return all(ord(ch) >= 0x20 or ch in _CONTROL_ADMITIDOS for ch in texto)


# Registro de formato

def test_detecta_formatos():
    assert _formato_documento("200186-0-polideportivos.csv") == "csv"
    assert _formato_documento("PiscinasAireLibre2026.pdf") == "pdf"
    assert _formato_documento("datos.json") == "json"
    assert _formato_documento("nota.txt") == "txt"
    assert _formato_documento("archivo") == "otro"


# Archivo CSV
def test_router_csv_contenido_bien_formado():
    docs = [_doc("200186-0-polideportivos.csv", CSV_RAW)]
    limpiados = normalizar_por_formato(docs)

    assert len(limpiados) == 1
    salida = limpiados[0].page_content
    # El CSV queda legible y sin ruido binario/control.
    assert salida.strip() == CSV_RAW.strip()
    assert _sin_control(salida)
    # Metadatos (fuente + formato) se conservan intactos.
    assert limpiados[0].metadata["source"] == "200186-0-polideportivos.csv"
    assert limpiados[0].metadata["format"] == "csv"


# Archivo PDF
def test_router_pdf_contenido_bien_formado():
    docs = [_doc("PiscinasAireLibre2026.pdf", PDF_RAW)]
    limpiados = normalizar_por_formato(docs)

    salida = limpiados[0].page_content
    # El extracto de PDF ya no debe contener bytes binarios ni control.
    assert "\x00" not in salida
    assert "\x01" not in salida
    assert _sin_control(salida)
    # El texto legible del PDF queda accesible para el LLM.
    assert "PDF-1.4" in salida
    assert limpiados[0].metadata["format"] == "pdf"


# Archivo JSON (passthrough)
def test_router_json_passthrough():
    docs = [_doc("datos.json", JSON_RAW)]
    limpiados = normalizar_por_formato(docs)
    assert limpiados[0].page_content == JSON_RAW


# Detalle por limpiador 
def test_limpieza_pdf_elimina_bytes_binarios():
    salida = _limpiar_pdf(PDF_RAW)
    assert "\x00" not in salida
    assert "\x01" not in salida


def test_limpieza_csv_conserva_datos():
    salida = _limpiar_csv(CSV_RAW)
    assert salida.strip() == CSV_RAW.strip()
    
