"""Wrapper original de RAG con responder doble; no importa el RAG real."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


@pytest.mark.parametrize('error_type', [TimeoutError, ConnectionError, RuntimeError])
def test_original_tool_normalizes_provider_error_without_success(monkeypatch, error_type):
    calls = []
    fake_package = ModuleType('rag')
    fake_package.__path__ = []
    fake_logic = ModuleType('rag.logic')

    def responder_doble(consulta):
        calls.append(consulta)
        raise error_type('[DOBLE] fallo inmediato')

    fake_logic.responder = responder_doble
    monkeypatch.setitem(sys.modules, 'rag', fake_package)
    monkeypatch.setitem(sys.modules, 'rag.logic', fake_logic)
    path = Path(__file__).resolve().parents[1] / 'agentes/tools/rag.py'
    spec = importlib.util.spec_from_file_location('_wrapper_rag_en_prueba', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.rag_preguntar('[DOBLE] consulta')
    assert calls == ['[DOBLE] consulta']
    assert set(result) == {'respuesta', 'fuentes', 'abstained', 'error'}
    assert result['respuesta'] == '' and result['fuentes'] == []
    assert result['abstained'] is False
    assert result['error'] == 'Error interno del RAG: [DOBLE] fallo inmediato'
