"""Guardias de infraestructura con implementaciones inyectadas, sin red."""

from copy import deepcopy

import pytest

from agentes.agent import AgentService
from agentes.contracts import Evidence, ToolResult
from agentes.nodes.aplicar import aplicar_node
from agentes.nodes.sintetizar import sintetizar_node
from agentes.settings import AgentSettings
from agentes.state import initial_state


def pending_plan():
    return {**initial_state("Consulta"), "final_answer": "Borrador informativo",
            "plan": ["Revisar el borrador"]}


@pytest.mark.parametrize("update", [
    None, {}, {"final_answer": "Respuesta"},
    {"plan": ["Revisar"]},
    {"final_answer": None, "plan": ["Revisar"]},
    {"final_answer": 123, "plan": ["Revisar"]},
    {"final_answer": "Respuesta", "plan": "Revisar"},
    {"final_answer": "Respuesta", "plan": ["Revisar", None]},
    {"final_answer": " ", "plan": ["Revisar"]},
    {"final_answer": "Respuesta", "plan": [""]},
    {"final_answer": "Respuesta", "plan": ["Revisar"], "approved": True},
    {"final_answer": "Respuesta", "plan": ["Revisar"], "approved": False},
    {"final_answer": "Respuesta", "plan": ["Revisar"], "approved": 0},
    {"final_answer": "Respuesta", "plan": ["Revisar"], "done": True},
    {"final_answer": "Respuesta", "plan": ["Revisar"], "done": 0},
])
def test_synthesis_rejects_invalid_output_even_with_previous_plan(update):
    with pytest.raises(ValueError, match="SYNTHESIS_CONTRACT"):
        sintetizar_node(pending_plan(), node=lambda state: update)


@pytest.mark.parametrize("patch", [
    {"approved": False}, {"approved": True}, {"approved": 0},
    {"done": True}, {"done": 0}, {"done": None},
])
def test_synthesis_checks_input_before_calling_implementation(patch):
    def unexpected(state):
        pytest.fail("No debe ejecutarse con un pedido resuelto")

    with pytest.raises(ValueError, match="SYNTHESIS_CONTRACT"):
        sintetizar_node({**pending_plan(), **patch}, node=unexpected)


def test_synthesis_keeps_implementation_output_without_approving():
    update = {"final_answer": "Sin evidencia suficiente", "plan": ["Reformular consulta"],
              "debug_trace": ["síntesis de prueba"]}
    state = initial_state("Consulta")
    assert sintetizar_node(state, node=lambda state: update) == update
    assert state["approved"] is None
    assert state["done"] is False


@pytest.mark.parametrize("decision", [None, 0, 1, "aprobar"])
def test_apply_requires_real_boolean_before_calling_implementation(decision):
    def unexpected(state):
        pytest.fail("No debe ejecutarse sin decisión válida")

    with pytest.raises(ValueError, match="HITL_DECISION_REQUIRED"):
        aplicar_node({**pending_plan(), "approved": decision}, node=unexpected)


def test_apply_requires_plan_before_calling_implementation():
    def unexpected(state):
        pytest.fail("No debe ejecutarse sin plan")

    with pytest.raises(ValueError, match="HITL_PLAN_REQUIRED"):
        aplicar_node({**initial_state("Consulta"), "approved": True}, node=unexpected)


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("invalid", [None, {}, {"done": 1}, {"done": 0}])
def test_apply_rejects_missing_or_non_boolean_done(decision, invalid):
    with pytest.raises(ValueError, match="APPLY_CONTRACT"):
        aplicar_node({**pending_plan(), "approved": decision}, node=lambda state: invalid)


@pytest.mark.parametrize("decision", [True, False])
def test_apply_checks_done_and_adds_one_event(decision):
    state = {**pending_plan(), "approved": decision}
    with pytest.raises(ValueError, match="APPLY_CONTRACT"):
        aplicar_node(state, node=lambda state: {"done": not decision})
    update = {"done": decision, "debug_trace": ["cierre de prueba"]}
    result = aplicar_node(state, node=lambda state: update)
    assert result["done"] is decision
    assert result["debug_trace"] == [
        "cierre de prueba", "HITL -> " + ("plan aprobado" if decision else "plan rechazado")]
    assert update["debug_trace"] == ["cierre de prueba"]


@pytest.mark.parametrize("wrapper", [sintetizar_node, aplicar_node])
def test_implementation_errors_propagate_without_simulated_fallback(wrapper):
    def failing(state):
        raise RuntimeError("Implementación pendiente")

    with pytest.raises(RuntimeError, match="Implementación pendiente"):
        wrapper({**pending_plan(), "approved": True} if wrapper is aplicar_node
                else pending_plan(), node=failing)


def test_synthesis_does_not_require_operational_fields_in_minimal_state():
    update = {"final_answer": "Borrador", "plan": ["Revisar"]}
    assert sintetizar_node({}, node=lambda state: update) == update


def test_synthesis_preserves_specialist_results_and_pending_state():
    state = initial_state("Consulta")
    state["specialist_results"] = {"documental": ToolResult(
        "ok", "Respuesta sintética", evidence=[Evidence(
            "test://documental", "Fragmento sintético",
            metadata={"fallback": True, "captured_at": "2026-10-13"})],
        data={"warnings": ["Datos históricos de prueba"]})}
    before = deepcopy(state)
    calls = []
    update = {"final_answer": "Borrador sintético: datos históricos de prueba",
              "plan": ["Revisar la fecha de captura"], "debug_trace": ["síntesis"]}
    before_update = deepcopy(update)

    def implementation(received):
        calls.append(deepcopy(received))
        return update

    result = sintetizar_node(state, node=implementation)
    assert calls == [before]
    assert result == before_update
    assert state == before and update == before_update
    assert set(result) == {"final_answer", "plan", "debug_trace"}


def test_apply_rejects_missing_decision_without_calling_implementation():
    state = pending_plan()
    state.pop("approved")

    def unexpected(state):
        pytest.fail("No debe ejecutarse sin el campo approved")

    with pytest.raises(ValueError, match="HITL_DECISION_REQUIRED"):
        aplicar_node(state, node=unexpected)


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("patch", [
    {"final_answer": " "}, {"final_answer": None},
    {"plan": []}, {"plan": "Revisar"}, {"plan": ["Revisar", " "]},
])
def test_apply_rejects_malformed_plan_before_calling_implementation(decision, patch):
    state = {**pending_plan(), "approved": decision, **patch}
    before = deepcopy(state)

    def unexpected(state):
        pytest.fail("No debe ejecutarse con un plan inválido")

    with pytest.raises(ValueError, match="HITL_PLAN_REQUIRED"):
        aplicar_node(state, node=unexpected)
    assert state == before


@pytest.fixture
def service_factory():
    def specialist(state):
        return {}  # Doble sin resultados; max_iter=1 fuerza síntesis directa.

    def create(synthesis, apply):
        return AgentService(
            documental_node=specialist, instalaciones_node=specialist,
            sintetizar_node=synthesis, aplicar_node=apply,
            settings=AgentSettings(max_iter=1))

    return create


@pytest.mark.parametrize("failure", ["contract", "exception"])
def test_failed_synthesis_never_reaches_apply_or_exposes_a_plan(service_factory, failure):
    calls = []

    def synthesis(state):
        if failure == "exception":
            raise RuntimeError("Fallo sintético")
        return {"final_answer": "Borrador inválido", "plan": []}

    def apply(state):
        calls.append(state["approved"])
        return {"done": state["approved"]}

    service = service_factory(synthesis, apply)
    tid = service.nueva_conversacion()
    expected = ValueError if failure == "contract" else RuntimeError
    with pytest.raises(expected, match="SYNTHESIS_CONTRACT|Fallo sintético"):
        service.procesar_turno("Consulta sintética", tid)
    state = service.consultar_estado(tid)
    assert calls == []
    assert state["plan_id"] is None and not state["pendiente_hitl"]
    assert state["approved"] is None and state["done"] is False
    assert state["plan"] == [] and state["final_answer"] == ""
    with pytest.raises(ValueError, match="REQUEST_INCOMPLETE"):
        service.procesar_turno("Otra consulta", tid)


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("failure", ["contract", "exception"])
def test_failed_apply_does_not_publish_a_successful_close(service_factory, decision, failure):
    calls = []

    def synthesis(state):
        return {"final_answer": "Borrador sintético", "plan": ["Revisar"]}

    def apply(state):
        calls.append(state["approved"])
        if failure == "exception":
            raise RuntimeError("Fallo sintético")
        return {"done": not state["approved"], "final_answer": "No debe publicarse"}

    service = service_factory(synthesis, apply)
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Consulta sintética", tid)
    assert calls == []
    expected = ValueError if failure == "contract" else RuntimeError
    with pytest.raises(expected, match="APPLY_CONTRACT|Fallo sintético"):
        service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
    state = service.consultar_estado(tid)
    assert calls == [decision]
    assert state["pendiente_hitl"] and state["done"] is False
    assert state["approved"] is decision
    assert state["plan_id"] == pending["plan_id"]
    assert state["final_answer"] == pending["final_answer"]
    assert state["plan"] == pending["plan"]
    assert state["debug_trace"] == pending["debug_trace"]
