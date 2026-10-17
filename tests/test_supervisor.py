"""Regresión del supervisor síncrono: política, trazabilidad e inmutabilidad."""
from copy import deepcopy

import pytest

from agentes.contracts import Evidence, SupervisorDecision, ToolResult
from agentes.graph import router_supervisor
from agentes.nodes.supervisor import supervisor_node
from agentes.state import initial_state


def assert_decision(update, route, origin, cause=None):
    assert update["supervisor_decision"].specialist == route
    event = update["debug_trace"][-1]
    assert f"supervisor -> {route}; origen={origin}" in event
    if cause is None:
        assert "causa=" not in event
    else:
        assert f"causa={cause}" in event


def test_rules_visit_pending_roles_before_finishing():
    state = initial_state("consulta")
    assert_decision(supervisor_node(state), "documental", "reglas")
    state["specialist_results"]["documental"] = ToolResult("ok", "Notas")
    assert_decision(supervisor_node(state), "instalaciones", "reglas")
    state["specialist_results"]["instalaciones"] = ToolResult("ok", "Notas")
    assert_decision(supervisor_node(state), "sintetizar", "reglas")
    state.update(final_answer="Respuesta", plan=["Paso"])
    assert_decision(supervisor_node(state), "FINISH", "reglas")


@pytest.mark.parametrize("route", ["documental", "instalaciones", "sintetizar", "FINISH"])
def test_valid_provider_proposals_preserve_decision(route):
    proposal = SupervisorDecision(route, "Motivo completo del proveedor que no debe copiarse a la traza")
    update = supervisor_node(initial_state("consulta"), route_provider=lambda state: proposal)
    assert_decision(update, route, "proveedor")
    assert update["supervisor_decision"] is proposal
    assert proposal.reason not in update["debug_trace"][-1]


def test_provider_exception_logs_only_category():
    def broken(state):
        raise RuntimeError("credencial-secreta y prompt privado")
    update = supervisor_node(initial_state("consulta"), route_provider=broken)
    assert_decision(update, "documental", "fallback", "excepcion_proveedor")
    assert "credencial-secreta" not in str(update)
    assert "prompt privado" not in str(update)


@pytest.mark.parametrize("proposal,cause", [
    (None, "tipo_respuesta_incorrecto"),
    ({"specialist": "documental", "reason": "texto"}, "tipo_respuesta_incorrecto"),
    (SupervisorDecision("ruta_privada_desconocida", "texto"), "ruta_desconocida"),
    (SupervisorDecision("documental", None), "tipo_motivo_incorrecto"),
    (SupervisorDecision("documental", 123), "tipo_motivo_incorrecto"),
])
def test_invalid_proposals_use_same_deterministic_fallback(proposal, cause):
    update = supervisor_node(initial_state("consulta"), route_provider=lambda state: proposal)
    assert_decision(update, "documental", "fallback", cause)
    assert "ruta_privada_desconocida" not in update["debug_trace"][-1]


@pytest.mark.parametrize("status", ["error", "abstained"])
def test_completed_attempt_advances_and_repeated_role_falls_back(status):
    state = initial_state("consulta")
    state["specialist_results"]["documental"] = ToolResult(status, "")
    assert_decision(supervisor_node(state), "instalaciones", "reglas")
    repeated = lambda state: SupervisorDecision("documental", "Repetir")
    assert_decision(supervisor_node(state, route_provider=repeated),
                    "instalaciones", "fallback", "especialista_ya_consultado")
    state["specialist_results"]["instalaciones"] = ToolResult(status, "")
    assert_decision(supervisor_node(state), "sintetizar", "reglas")


@pytest.mark.parametrize("has_plan", [False, True])
def test_limit_forces_finish_and_leaves_router_guard_unchanged(has_plan):
    state = initial_state("consulta")
    state["iterations"] = 7
    if has_plan:
        state.update(final_answer="Respuesta", plan=["Paso"])
    def must_not_run(state):
        pytest.fail("El proveedor no se llama al alcanzar max_iter")
    update = supervisor_node(state, max_iter=8, route_provider=must_not_run)
    assert update["iterations"] == 8
    assert_decision(update, "FINISH", "limite")
    assert router_supervisor({**state, **update}) == ("aplicar" if has_plan else "sintetizar")
    # La propuesta forzada no completa ni aprueba el pedido.
    assert state["approved"] is None and state["done"] is False


def test_plan_ready_does_not_skip_pending_roles_in_rules():
    state = initial_state("consulta")
    state.update(final_answer="Respuesta", plan=["Paso"])
    assert_decision(supervisor_node(state), "documental", "reglas")


def test_counter_boundary_is_unchanged():
    state = initial_state("consulta")
    state["iterations"] = 6
    below = supervisor_node(state, max_iter=8)
    assert below["iterations"] == 7
    assert_decision(below, "documental", "reglas")
    state["iterations"] = 8
    above = supervisor_node(state, max_iter=8)
    assert above["iterations"] == 9
    assert_decision(above, "FINISH", "limite")
    assert_decision(supervisor_node(initial_state("consulta"), max_iter=1), "FINISH", "limite")


@pytest.mark.parametrize("provider,origin,cause", [
    (None, "reglas", None),
    (lambda state: SupervisorDecision("instalaciones", "Texto"), "proveedor", None),
    (lambda state: None, "fallback", "tipo_respuesta_incorrecto"),
])
def test_partial_update_does_not_mutate_input_or_collections(provider, origin, cause):
    state = initial_state("consulta")
    state["specialist_results"]["documental"] = ToolResult(
        "ok", "Notas", evidence=[Evidence("prueba", "Fragmento", metadata={"tags": ["uno"]})])
    state["plan"] = ["Plan previo"]
    before = deepcopy(state)
    update = supervisor_node(state, route_provider=provider)
    assert state == before
    assert set(update) == {"supervisor_decision", "iterations", "debug_trace"}
    assert update["debug_trace"] is not state["debug_trace"]
    assert len(update["debug_trace"]) == 1
    assert_decision(update, "instalaciones", origin, cause)
    update["debug_trace"].append("Solo en la copia")
    assert state == before
