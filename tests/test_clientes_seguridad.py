"""Fallback marcado con origen y plan HITL sin credenciales ni mutar el estado."""

import copy

from agentes.secret_filter import sin_secretos
from clientes.debug import _origen


def test_origen_fallback():
    assert _origen({"data": {"origen": "fallback"}}) == "fallback"


def test_plan_filtrado_sin_mutar():
    estado = {"plan": ["Consultar API con api_key=sk-abcdef1234567890XYZ"]}
    original = copy.deepcopy(estado)
    salida = [sin_secretos(p) for p in estado["plan"]]
    assert "sk-abcdef" not in salida[0]
    assert "OCULT" in salida[0]
    assert estado == original
