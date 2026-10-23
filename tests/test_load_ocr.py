"""tests/test_load_ocr.py

El forzado por OCR.txt debe ser OCR real (Tesseract), no extracción nativa.
Y si el motor OCR no está instalado, el documento no puede desaparecer.
"""
from pathlib import Path

import rag.load as load


def test_ocr_txt_fuerza_ambos_pdfs():
    ruta = Path(load.__file__).parent.parent / "data" / "corpus" / "OCR.txt"
    config = load.leer_config_ocr(str(ruta))

    assert config["PreciosPublicos2026.pdf"] == "OCR"
    assert config["PiscinasAireLibre2026.pdf"] == "OCR"


def test_ocr_forzado_usa_tesseract(monkeypatch):
    monkeypatch.setattr(load, "convert_from_path", lambda *a, **k: ["pagina"])
    monkeypatch.setattr(load.pytesseract, "image_to_string", lambda imagen, **k: "texto ocr")
    monkeypatch.setattr(
        load, "_extraer_pdf_nativo", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe extraer nativo"))
    )

    docs = load._ocr_pdf("x.pdf", "PreciosPublicos2026.pdf")

    assert [d.page_content for d in docs] == ["texto ocr"]
    assert docs[0].metadata["file_type"] == "pdf_ocr"
    assert docs[0].metadata["ocr_reason"] == "ocr.txt"


def test_ocr_no_disponible_cae_a_nativo(monkeypatch, capsys):
    def _falla(*a, **k):
        raise RuntimeError("poppler missing")

    monkeypatch.setattr(load, "convert_from_path", _falla)

    docs = load._ocr_pdf("no_existe.pdf", "PiscinasAireLibre2026.pdf")

    assert docs == []
    assert "AVISO OCR no disponible" in capsys.readouterr().out
