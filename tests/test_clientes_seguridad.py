"""Fallback marcado con origen y plan HITL sin credenciales ni mutar el estado."""

import copy

from agentes.secret_filter import sin_secretos
from clientes.debug import _origen, fuentes_de_estado
from clientes.hitl import mensaje_recuperacion


def test_origen_fallback():
    assert _origen({"data": {"origen": "fallback"}}) == "fallback"


def test_plan_filtrado_sin_mutar():
    estado = {"plan": ["Consultar API con api_key=sk-abcdef1234567890XYZ"]}
    original = copy.deepcopy(estado)
    salida = [sin_secretos(p) for p in estado["plan"]]
    assert "sk-abcdef" not in salida[0]
    assert "OCULT" in salida[0]
    assert estado == original


def test_fuentes_sin_repetir_y_sin_evidencias():
    estado = {"specialist_results": {
        "documental": {"evidence": [{"source": "a.pdf"}, {"source": "a.pdf"}, {"source": "b.pdf"}]},
        "instalaciones": {"evidence": []},
    }}
    assert fuentes_de_estado(estado) == ["a.pdf", "b.pdf"]
    assert fuentes_de_estado({}) == []


def test_mensaje_recuperacion_segun_estado():
    assert mensaje_recuperacion({"pendiente_hitl": True})[0] == "info"
    assert mensaje_recuperacion({"ejecucion_incompleta": True})[0] == "warning"
    assert mensaje_recuperacion({})[0] == "success"
