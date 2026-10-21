"""Contrato puro compartido: límites, respuestas incompatibles e inmutabilidad."""

from copy import deepcopy

import pytest

from agentes.validation import (
    MAX_ENTRADA, validar_decision, validar_entrada, validar_estado, validar_id, validar_mensaje,
)


@pytest.mark.parametrize("texto", ["", "   ", "Consulta sobre natación", "x" * MAX_ENTRADA])
def test_entrada_valida_sin_normalizar(texto):
    assert validar_entrada(texto) is None


@pytest.mark.parametrize("texto", [None, 42, b"texto", "x" * (MAX_ENTRADA + 1),
                                   "a\nb", "a\tb", "a\x00b", "a\x1bb", "a\u200bb", "a\u202eb"])
def test_entrada_invalida(texto):
    with pytest.raises(ValueError):
        validar_entrada(texto)


@pytest.mark.parametrize("texto", ["", " ", "\u00a0", None, 1, "a\nb", "x" * (MAX_ENTRADA + 1)])
def test_mensaje_vacio_o_invalido_no_puede_enviarse(texto):
    with pytest.raises(ValueError):
        validar_mensaje(texto)


@pytest.mark.parametrize("texto", ["  Consulta  ", "x" * MAX_ENTRADA])
def test_mensaje_valido_no_se_normaliza(texto):
    assert validar_mensaje(texto) is None


@pytest.mark.parametrize("decision", [True, False])
def test_decision_booleana_estricta_valida(decision):
    assert validar_decision(decision) is None


@pytest.mark.parametrize("decision", [None, 0, 1, "true", "false", "aprobar", [], {}])
def test_decision_no_booleana_no_se_coacciona(decision):
    with pytest.raises(TypeError):
        validar_decision(decision)


@pytest.mark.parametrize("decision", [0, 1, "false"])
def test_estado_con_decision_incompatible_no_se_modifica(decision):
    estado = {"thread_id": "hilo", "pendiente_hitl": False, "approved": decision}
    antes = deepcopy(estado)
    with pytest.raises(TypeError):
        validar_estado(estado, "hilo")
    assert estado == antes


@pytest.mark.parametrize("valor", [None, 0, 1, "false"])
def test_estado_con_indicador_de_ejecucion_invalido(valor):
    with pytest.raises(ValueError):
        validar_estado({"thread_id": "hilo", "pendiente_hitl": False,
                        "ejecucion_incompleta": valor}, "hilo")


@pytest.mark.parametrize("valor", ["hilo-1", "x" * 256])
def test_id_valido(valor):
    assert validar_id(valor) is None


@pytest.mark.parametrize("valor", [None, True, 1, "", " ", "dos hilos", "a\u00a0b",
                                   "a\u200bb", "a\x00b", "x" * 257])
def test_id_invalido(valor):
    with pytest.raises(ValueError):
        validar_id(valor)


@pytest.mark.parametrize("pendiente", [True, False])
def test_estado_devuelve_mismo_objeto_sin_mutarlo(pendiente):
    estado = {"thread_id": "hilo", "pendiente_hitl": pendiente,
              "plan_id": "plan", "plan": ["Paso"], "extra": {"lista": [1]}}
    antes = deepcopy(estado)
    assert validar_estado(estado, "hilo") is estado
    assert estado == antes


def test_estado_sin_pendiente_no_exige_plan():
    estado = {"thread_id": "hilo", "pendiente_hitl": False}
    assert validar_estado(estado, "hilo") is estado


@pytest.mark.parametrize("cambio", [
    {"thread_id": "otro"}, {"pendiente_hitl": 1}, {"pendiente_hitl": None},
    {"pendiente_hitl": "false"}, {"plan_id": None}, {"plan_id": "a b"},
    {"plan": []}, {"plan": "paso"}, {"plan": [None]}, {"plan": [" "]},
])
def test_estado_incompatible_no_se_modifica(cambio):
    estado = {"thread_id": "hilo", "pendiente_hitl": True,
              "plan_id": "plan", "plan": ["Paso"], **cambio}
    antes = deepcopy(estado)
    with pytest.raises(ValueError):
        validar_estado(estado, "hilo")
    assert estado == antes


@pytest.mark.parametrize("estado", [None, [], {}, "estado"])
def test_estado_ausente_o_tipo_invalido(estado):
    with pytest.raises(ValueError):
        validar_estado(estado, "hilo")
