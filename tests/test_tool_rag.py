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
from rag.logic import UMBRAL_ABSTENCION

import os


diag = os.getenv("RAG_CON_DIAGNOSTICO")

if diag:
    CLAVES_CONTRATO = {"respuesta", "fuentes", "abstained", "error", "distancia_mejor", "respuesta_llm", "motivo"}
else: 
    CLAVES_CONTRATO = {"respuesta", "fuentes", "abstained", "error"}
    

# Set de evaluación (23 preguntas; 4 fuera de corpus) 
_RUTA_EVAL = pathlib.Path(__file__).parent / "evaluation_questions.json"
EVALS: list[tuple[str, bool, str | None]] = []
if _RUTA_EVAL.exists():
    _qs = json.loads(_RUTA_EVAL.read_text(encoding="utf-8"))
    EVALS = [
        (q["pregunta"], bool(q.get("out_of_corpus")), q.get("fuente_esperada"))
        for q in _qs
    ]

def _indice_disponible() -> bool:
    from rag.retrieve import obtener_coleccion
    return obtener_coleccion().count() > 0


INDICE_OK = _indice_disponible()



# Forma del dict (no requiere índice) 

def test_claves_de_contrato():
    r = rag_preguntar("¿Cuánto cuesta el abono anual?", diag)
    assert set(r) == CLAVES_CONTRATO  # las claves del contrato 
    # Claves "fijas": siempre del tipo esperado
    assert isinstance(r["respuesta"], str)
    assert isinstance(r["fuentes"], list)
    assert isinstance(r["abstained"], bool)
    assert r["error"] is None or isinstance(r["error"], str)
    
    if diag:
        # Claves de diagnóstico: valor real O None (nunca deben romperse la cadena)
        assert r["distancia_mejor"] is None or isinstance(r["distancia_mejor"], (int, float))
        assert r["respuesta_llm"] is None or isinstance(r["respuesta_llm"], str)
        assert r["motivo"] is None or isinstance(r["motivo"], str)
        
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
@pytest.mark.skipif(not INDICE_OK, reason="índice no indexado (ejecutar_pipeline)")
@pytest.mark.parametrize("pregunta, out_of_corpus, fuente_esperada", EVALS)
# mejora en el test, pretende obtener por qué hay abstención y por que´ se podría negar
# a responder habiendo cercanos en cuanto a semántica
def test_eval_set(pregunta, out_of_corpus, fuente_esperada):
    r = rag_preguntar(pregunta)
    assert r["error"] is None

    if out_of_corpus:
        assert r["abstained"] is True
        return

    # para saber por qué el sistema se abstiene de responder
    if r["abstained"]:
        if r.get("distancia_mejor", 0.0) > UMBRAL_ABSTENCION:
            return                          # no parece el guardrail
        # por si se niega a responder teniendo cercanos
        assert False, (
            f"El LLM se abstuvo sin disparar el guardrail para la pregunta: "
            f"'{pregunta}'."
            f"Revisar el prompt o el chunking."
        )

    assert r["respuesta"].strip()
    assert r["fuentes"], "debe citar al menos una fuente"

    if fuente_esperada:
        import re
        # evita fallos por diferencias de formato (mayus/minus, espacios, ...), no por contenido
        esperada = re.sub(r"\s+", " ", fuente_esperada).strip().lower()
        fuentes_norm = [re.sub(r"\s+", " ", str(f)).strip().lower() for f in r["fuentes"]]
        assert esperada in fuentes_norm, f"debe citar {fuente_esperada}; fuentes={r['fuentes']}"