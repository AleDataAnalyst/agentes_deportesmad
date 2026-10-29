"""Wrapper original de RAG con responder doble; no importa el RAG real."""
import importlib.util
from pathlib import Path
from sys import modules 
from types import ModuleType

import pytest


@pytest.mark.parametrize("valor", [None, [], {"fuentes": None}])
@pytest.mark.parametrize("diagnostico", [False, True])
def test_salida_malformada_respeta_contrato_incluso_con_diagnostico(monkeypatch, valor, diagnostico):
    import agentes.tools.rag as tool
    monkeypatch.setattr(tool, "responder", lambda consulta: valor)
    r = tool.rag_preguntar("consulta", con_diagnostico=diagnostico)
    assert r["error"]
    assert r["respuesta"] == "" and r["fuentes"] == []
    assert r["abstained"] is False
    if diagnostico:
        assert r["distancia_mejor"] is None
        assert r["respuesta_llm"] is None
        assert r["motivo"] is None


@pytest.mark.parametrize('error_type', [TimeoutError, ConnectionError])
def test_original_tool_normalizes_provider_error_without_success(monkeypatch, error_type):
    """Un fallo del RAG se convierte en error, nunca en respuesta ni abstención."""
    calls = []

    rag_falso = ModuleType("rag")
    rag_falso.__path__ = []

    logic_falsa = ModuleType("rag.logic")

    def responder_falso(consulta: str) -> dict:
        calls.append(consulta)
        raise error_type("[DOBLE] fallo de red o timeout")

    logic_falsa.responder = responder_falso

    monkeypatch.setitem(modules, "rag", rag_falso)
    monkeypatch.setitem(modules, "rag.logic", logic_falsa)

    ruta_tool = (
        Path(__file__).resolve().parents[1] / "agentes" / "tools" / "rag.py"
    )
    spec = importlib.util.spec_from_file_location(
        "_tool_rag_en_prueba", ruta_tool
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    resultado = modulo.rag_preguntar("[DOBLE] consulta de prueba")

    assert calls == ["[DOBLE] consulta de prueba"]
    assert set(resultado) == {"respuesta", "fuentes", "abstained", "error"}
    assert resultado["respuesta"] == ""
    assert resultado["fuentes"] == []
    assert resultado["abstained"] is False
    assert resultado["error"] == (
        "Error interno del RAG: [DOBLE] fallo de red o timeout"
    )
