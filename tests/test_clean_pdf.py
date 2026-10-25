"""Tests de _limpiar_pdf (rag/clean.py)."""
from rag.clean import _limpiar_pdf


def test_conserva_tildes_enye_y_euro():
    texto = "Año 2026: el abono cuesta 45 € para niños y mayores."
    assert _limpiar_pdf(texto) == texto


def test_quita_controles_y_caracter_de_reemplazo():
    assert _limpiar_pdf("hola\x85 mundo\ufffd") == "hola mundo"


def test_colapsa_saltos_y_espacios():
    assert _limpiar_pdf("a\n\n\n\nb   c") == "a\n\nb c"
