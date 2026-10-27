# tests/test_load_pdf_tabular.py
from pathlib import Path
from unittest.mock import patch

from rag.load import _load_pdf


def test_load_pdf_tabular_carga_todos_los_bloques(tmp_path):
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    bloques = [
        {"fuente": "informe.pdf", "texto": "# Página 1\n| clave |\n| --- |\n| valor1 |"},
        {"fuente": "informe.pdf", "texto": "# Página 2\n| clave |\n| --- |\n| valor2 |"},
        {"fuente": "informe.pdf", "texto": "# Página 3\n| clave |\n| --- |\n| valor3 |"},
    ]

    with patch(
        "rag.load.cargar_pdfs_especiales",
        return_value={"tabular": bloques, "ocr": []},
    ):
        docs = _load_pdf(
            str(pdf),
            tmp_path,
            {"informe.pdf"},
            set(),
        )

    assert len(docs) == 3  # Cada bloque conserva juntas sus líneas y contexto.
    assert [doc.page_content for doc in docs] == [
        "clave: valor1",
        "clave: valor2",
        "clave: valor3",
    ]
    assert {doc.metadata["pdf_source"] for doc in docs} == {"informe.pdf"}
    assert {doc.metadata["block_index"] for doc in docs} == {0, 1, 2}
    assert all(
        doc.metadata["derived_from"] == "tabular_key-value"
        for doc in docs
    )


def test_load_pdf_tabular_fallback_sin_resultados(tmp_path):
    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    with patch(
        "rag.load.cargar_pdfs_especiales",
        return_value={"tabular": [], "ocr": []},
    ), patch(
        "rag.load._extraer_texto_tabla_a_textos",
        return_value=["Pagina 1\nclave: valor"],
    ):
        docs = _load_pdf(
            str(pdf),
            tmp_path,
            {"informe.pdf"},
            set(),
        )

    assert docs
    assert all(
        doc.metadata["derived_from"] == "tabular_key-value-fallback"
        for doc in docs
    )
    assert all(
        doc.metadata["pdf_source"] == "informe.pdf"
        for doc in docs
    )
