"""
Prueba que de que puede importar `extraer_piscina`.

Regresión sobre PDF del corpus para ver que pasa con estos
valores de tabla para páginas 1 y 2.
"""
from rag.pdf_tabular import extraer_piscinas


def test_extraer_piscinas():

    registros = extraer_piscinas(
        "data/corpus/PiscinasAireLibre2026.pdf"
    )
    
    assert len(registros) == 25
    
    assert sum(r["pagina"] == 1 for r in registros) == 17
    assert sum(r["pagina"] == 2 for r in registros) == 8
    
    assert sum(
        r["valores"]["Distrito"] == "Hortaleza"
        for r in registros
    ) == 2
    
    assert sum(
        r["valores"]["Distrito"] == "Usera"
        for r in registros
    ) == 3
    
    for registro in registros:
        assert len(registro["valores"]) == 4
        assert all(registro["valores"].values())