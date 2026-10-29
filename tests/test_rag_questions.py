"""Aceptación explícita del RAG real; recopilar tests nunca consulta modelos."""
import json
from pathlib import Path
import re

import pytest

EVAL = Path(__file__).with_name("evaluation_questions.json")
PREGUNTAS = json.loads(EVAL.read_text(encoding="utf-8"))


@pytest.mark.integration
@pytest.mark.parametrize("item", PREGUNTAS, ids=lambda item: item["pregunta"])
def test_pregunta_real(item):
    from agentes.tools.rag import rag_preguntar

    r = rag_preguntar(item["pregunta"])
    assert r["error"] is None, r["error"]
    if item.get("out_of_corpus"):
        assert r["abstained"] is True
        return
    assert not r["abstained"]
    assert r["respuesta"].strip()
    assert r["fuentes"]
    if esperada := item.get("fuente_esperada"):
        normalizar = lambda texto: re.sub(r"\s+", " ", str(texto)).strip().lower()
        assert any(normalizar(esperada) in normalizar(f) for f in r["fuentes"])
