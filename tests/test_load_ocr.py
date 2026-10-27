"""tests/test_load_ocr.py

Valida la ruta OCR actual:
- especiales.txt declara PDFs como OCR.
- _load_pdf() usa los bloques OCR generados por cargar_pdfs_especiales().
- Si no hay bloques OCR, el PDF no desaparece: cae a PyPDFLoader.
"""

from pathlib import Path

import rag.load as load
from langchain_core.documents import Document


def test_especiales_txt_marca_pdfs_ocr(tmp_path: Path):
    (tmp_path / "especiales.txt").write_text(
        "\n".join(
            [
                "# Manifiesto de PDFs especiales",
                "PreciosPublicos2026.pdf: OCR",
                "PiscinasAireLibre2026.pdf: OCR",
                "Otro.pdf: TAB",
            ]
        ),
        encoding="utf-8",
    )

    pdfs_ocr = load._leer_pdfs_ocr_tab(tmp_path)

    assert pdfs_ocr == {
        "PreciosPublicos2026.pdf",
        "PiscinasAireLibre2026.pdf",
    }


def test_pdf_ocr_usa_bloques_ocr(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "PreciosPublicos2026.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    bloques = [
        {
            "fuente": "PreciosPublicos2026.pdf",
            "texto": "# Página 1\n| concepto | precio |\n| --- | --- |\n| abono | 45 |",
        },
        {
            "fuente": "PreciosPublicos2026.pdf",
            "texto": "# Página 2\n| concepto | precio |\n| --- | --- |\n| entrada | 3 |",
        },
    ]

    monkeypatch.setattr(
        load,
        "cargar_pdfs_especiales",
        lambda directorio: {"tabular": [], "ocr": bloques},
    )

    docs = load._load_pdf(
        path=str(pdf),
        directorio_raiz=tmp_path,
        pdfs_tabulares=set(),
        pdfs_ocr={"PreciosPublicos2026.pdf"},
    )

    # Una fila de tabla Markdown = un Document, con la cabecera en el contenido.
    assert [d.page_content for d in docs] == [
        "concepto: abono\nprecio: 45",
        "concepto: entrada\nprecio: 3",
    ]
    assert [d.metadata["page"] for d in docs] == [1, 2]
    assert all(
        d.metadata["file_type"] == "pdf_ocr_key_value"
        for d in docs
    )
    assert all(
        d.metadata["derived_from"] == "ocr_key-value"
        for d in docs
    )
    assert all(
        d.metadata["source"] == "PreciosPublicos2026.pdf"
        for d in docs
    )


def test_pdf_ocr_sin_bloques_cae_a_nativo(monkeypatch, tmp_path: Path):
    pdf = tmp_path / "PiscinasAireLibre2026.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        load,
        "cargar_pdfs_especiales",
        lambda directorio: {"tabular": [], "ocr": []},
    )

    documento_nativo = Document(
        page_content="texto nativo",
        metadata={"source": "PiscinasAireLibre2026.pdf"},
    )

    class FakePyPDFLoader:
        def __init__(self, ruta: str):
            assert ruta == str(pdf)

        def load(self):
            return [documento_nativo]

    monkeypatch.setattr(load, "PyPDFLoader", FakePyPDFLoader)

    docs = load._load_pdf(
        path=str(pdf),
        directorio_raiz=tmp_path,
        pdfs_tabulares=set(),
        pdfs_ocr={"PiscinasAireLibre2026.pdf"},
    )

    assert len(docs) == 1
    assert docs[0].page_content == "texto nativo"
    assert docs[0].metadata["source"] == "PiscinasAireLibre2026.pdf"
