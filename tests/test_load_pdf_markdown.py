"""Bloques OCR y tabulares en Markdown: una fila de tabla = un Document.

Complementa tests/test_load_ocr.py y tests/test_load_pdf_tab.py, que cubren los
bloques de texto plano; no los sustituye.
"""

from pathlib import Path
from unittest.mock import patch

import rag.load as load


def test_pdf_ocr_markdown_genera_un_documento_por_fila(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "PreciosPublicos2026.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    bloques = [
        {"fuente": "PreciosPublicos2026.pdf",
         "texto": "# Página 1\n| concepto | precio |\n| --- | --- |\n| abono | 45 |"},
        {"fuente": "PreciosPublicos2026.pdf",
         "texto": "# Página 2\n| concepto | precio |\n| --- | --- |\n| entrada | 3 |"},
    ]
    monkeypatch.setattr(
        load, "cargar_pdfs_especiales", lambda directorio: {"tabular": [], "ocr": bloques},
    )

    docs = load._load_pdf(
        path=str(pdf),
        directorio_raiz=tmp_path,
        pdfs_tabulares=set(),
        pdfs_ocr={"PreciosPublicos2026.pdf"},
    )

    assert [d.page_content for d in docs] == [
        "concepto: abono\nprecio: 45",
        "concepto: entrada\nprecio: 3",
    ]
    assert [d.metadata["page"] for d in docs] == [1, 2]
    assert all(d.metadata["file_type"] == "pdf_ocr_key_value" for d in docs)


def test_pdf_tabular_markdown_genera_un_documento_por_fila(tmp_path):
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    bloques = [
        {"fuente": "informe.pdf", "texto": f"# Página {n}\n| clave |\n| --- |\n| valor{n} |"}
        for n in (1, 2, 3)
    ]

    with patch("rag.load.cargar_pdfs_especiales", return_value={"tabular": bloques, "ocr": []}):
        docs = load._load_pdf(str(pdf), tmp_path, {"informe.pdf"}, set())

    assert [d.page_content for d in docs] == ["clave: valor1", "clave: valor2", "clave: valor3"]
    assert {d.metadata["block_index"] for d in docs} == {0, 1, 2}


def test_pdf_tabular_markdown_en_fallback_directo(tmp_path):
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    with patch(
        "rag.load.cargar_pdfs_especiales", return_value={"tabular": [], "ocr": []},
    ), patch(
        "rag.load._extraer_texto_tabla_a_textos",
        return_value=["# Página 1\n| clave |\n| --- |\n| valor |"],
    ):
        docs = load._load_pdf(str(pdf), tmp_path, {"informe.pdf"}, set())

    assert docs
    assert all(d.metadata["derived_from"] == "tabular_key-value-fallback" for d in docs)
    assert all(d.metadata["pdf_source"] == "informe.pdf" for d in docs)
