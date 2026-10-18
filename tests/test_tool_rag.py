"""
test_tool_rag.py

Tests de la tool RAG (agentes/tools/rag.py).

Contrato:
    rag_preguntar(consulta: str) -> dict
        {"respuesta": str, "fuentes": list[str], "abstained": bool, "error": str|None}

La tool NUNCA lanza excepción: los fallos se devuelven en "error".
"""
import json
import pathlib

import pytest

from agentes.tools.rag import rag_preguntar

CLAVES_CONTRATO = {"respuesta", "fuentes", "abstained", "error"}

# Set de evaluación (22 preguntas; 4 fuera de corpus) 
_RUTA_EVAL = pathlib.Path(__file__).parent / "evaluation_questions.json"
EVALS: list[tuple[str, bool, str | None]] = []
if _RUTA_EVAL.exists():
    _qs = json.loads(_RUTA_EVAL.read_text(encoding="utf-8"))
    EVALS = [
        (q["pregunta"], bool(q.get("out_of_corpus")), q.get("fuente_esperada"))
        for q in _qs
    ]

# El índice se abre únicamente en la fixture opt-in indice_real.


# Forma del dict (no requiere índice) 

def test_claves_de_contrato(monkeypatch):
    # Forma del contrato con doble explícito; no es una evaluación del RAG.
    import agentes.tools.rag as mod
    monkeypatch.setattr(mod, "responder", lambda consulta: {
        "respuesta": "Respuesta simulada", "fuentes": ["test://fuente"],
        "abstained": False, "error": None})
    r = rag_preguntar("¿Cuánto cuesta el abono anual?")
    assert set(r) == CLAVES_CONTRATO
    assert isinstance(r["respuesta"], str)
    assert isinstance(r["fuentes"], list)
    assert isinstance(r["abstained"], bool)
    assert r["error"] is None or isinstance(r["error"], str)


# Validación pre-LLM (no requiere índice) 

def test_consulta_vacia_devuelve_error():
    r = rag_preguntar("")
    assert r["error"]
    assert r["respuesta"] == ""
    assert r["abstained"] is False
    assert r["fuentes"] == []


# Robustez: la tool nunca lanza 

def test_error_interno_no_lanza(monkeypatch):
    import agentes.tools.rag as mod

    def _falla(consulta, top_k=None):
        raise RuntimeError("Chroma caído")

    monkeypatch.setattr(mod, "responder", _falla)
    r = rag_preguntar("cualquiera")
    assert r["error"]
    assert "Error interno del RAG" in r["error"]
    assert r["respuesta"] == ""
    assert r["fuentes"] == []
    assert r["abstained"] is False


# Integración contra el índice (22 preguntas de evaluación) 

@pytest.mark.skipif(not EVALS, reason="falta evaluation_questions.json")
@pytest.mark.rag_eval
@pytest.mark.parametrize("pregunta, out_of_corpus, fuente_esperada", EVALS)
def test_eval_set(pregunta, out_of_corpus, fuente_esperada, indice_real):
    r = rag_preguntar(pregunta)
    assert r["error"] is None
    if out_of_corpus:
        assert r["abstained"] is True
    else:
        assert r["abstained"] is False
        assert r["respuesta"].strip()
        assert r["fuentes"], "debe citar al menos una fuente"
        if fuente_esperada:
            assert fuente_esperada in r["fuentes"], \
                f"debe citar {fuente_esperada}; fuentes={r['fuentes']}"
