"""Pruebas de la API síncrona usando dobles; no requieren modelo ni red."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from agentes.agent import AgentService
from agentes.contracts import PendingAction, SupervisorDecision
from agentes.settings import AgentSettings, load_settings
from tests.test_sync_integration import specialist, synthesize, apply


def service(**options):
    nodes = dict(documental_node=specialist("documental"),
                 instalaciones_node=specialist("instalaciones"),
                 sintetizar_node=synthesize, aplicar_node=apply,
                 settings=AgentSettings())
    return AgentService(**{**nodes, **options})


@pytest.mark.parametrize("approved", [True, False])
def test_service_lifecycle_and_idempotency(approved):
    calls = []

    def counted_apply(state):
        calls.append(state["approved"])
        return apply(state)

    agent = service(aplicar_node=counted_apply)
    tid = agent.nueva_conversacion()
    pending = agent.procesar_turno("Consulta simulada", tid)
    assert pending["pendiente_hitl"] and not pending["done"]
    assert pending["plan_id"] and calls == []
    pending["plan"].clear()
    assert agent.consultar_estado(tid)["plan"] == ["Paso simulado"]
    with pytest.raises(ValueError, match="HITL_PENDING"):
        agent.procesar_turno("Otro mensaje", tid)
    plan_id = pending["plan_id"]
    final = agent.resolver_plan(tid, approved, plan_id=plan_id)
    assert final["done"] is approved and not final["pendiente_hitl"]
    assert final["debug_trace"][-1] == "HITL -> " + ("plan aprobado" if approved else "plan rechazado")
    assert agent.resolver_plan(tid, approved, plan_id=plan_id) == final
    assert agent.consultar_estado(tid) == final
    assert final["debug_trace"].count(final["debug_trace"][-1]) == 1
    assert calls == [approved]
    with pytest.raises(ValueError, match="PLAN_ALREADY_RESOLVED"):
        agent.resolver_plan(tid, not approved, plan_id=plan_id)
    assert agent.consultar_estado(tid) == final
    new = agent.procesar_turno("Nuevo pedido", tid)
    assert new["plan_id"] != plan_id and new["approved"] is None
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        agent.resolver_plan(tid, True, plan_id=plan_id)


def test_unknown_thread_and_isolation():
    agent = service()
    first, second = agent.nueva_conversacion(), agent.nueva_conversacion()
    assert first != second
    empty = agent.consultar_estado(second)
    assert empty["thread_id"] == second and empty["plan_id"] is None
    pending = agent.procesar_turno("Consulta", first)
    assert agent.consultar_estado(second) == empty
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        agent.resolver_plan(second, True, plan_id=pending["plan_id"])


def test_invalid_inputs_do_not_change_checkpoint():
    agent = service()
    tid = agent.nueva_conversacion()
    empty = agent.consultar_estado(tid)
    for message in ["", "   "]:
        with pytest.raises(ValueError, match="mensaje"):
            agent.procesar_turno(message, tid)
    with pytest.raises(TypeError, match="mensaje"):
        agent.procesar_turno(None, tid)
    with pytest.raises(ValueError, match="thread_id"):
        agent.consultar_estado("")
    assert agent.consultar_estado(tid) == empty
    pending = agent.procesar_turno("Consulta", tid)
    with pytest.raises(TypeError, match="aprobado"):
        agent.resolver_plan(tid, "False", plan_id=pending["plan_id"])
    assert agent.consultar_estado(tid)["approved"] is None


def test_node_error_is_visible_and_cannot_be_overwritten():
    agent = service(sintetizar_node=lambda state: {})
    tid = agent.nueva_conversacion()
    with pytest.raises(ValueError, match="SYNTHESIS_CONTRACT"):
        agent.procesar_turno("Consulta", tid)
    with pytest.raises(ValueError, match="REQUEST_INCOMPLETE"):
        agent.procesar_turno("Otro pedido", tid)


def test_same_thread_serializes_messages():
    entered, release, second_started = Event(), Event(), Event()
    calls = []
    original = specialist("documental")

    def blocked(state):
        calls.append(state["user_message"])
        entered.set()
        assert release.wait(5)
        return original(state)

    agent = service(documental_node=blocked)
    tid = agent.nueva_conversacion()

    def second():
        second_started.set()
        return agent.procesar_turno("Segundo", tid)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(agent.procesar_turno, "Primero", tid)
        try:
            assert entered.wait(5)
            following = pool.submit(second)
            assert second_started.wait(5)
        finally:
            release.set()
        assert first.result(timeout=5)["pendiente_hitl"]
        with pytest.raises(ValueError, match="HITL_PENDING"):
            following.result(timeout=5)
    assert calls == ["Primero"]


@pytest.mark.parametrize("raw,expected", [("", 8), ("  ", 8), ("3", 3), ("20", 20)])
def test_settings_from_environment(monkeypatch, raw, expected):
    monkeypatch.setenv("MAX_ITER", raw)
    assert load_settings().max_iter == expected


@pytest.mark.parametrize("raw", ["0", "-1", "ocho", "2.5"])
def test_invalid_settings(monkeypatch, raw):
    monkeypatch.setenv("MAX_ITER", raw)
    with pytest.raises(ValueError, match="MAX_ITER"):
        load_settings()


def test_service_uses_iteration_setting():
    agent = service(settings=AgentSettings(max_iter=1))
    state = agent.procesar_turno("Consulta simulada", agent.nueva_conversacion())
    assert state["specialist_results"] == {}
    assert state["pendiente_hitl"]


def test_service_recursion_budget_allows_configured_limit():
    agent = service(settings=AgentSettings(max_iter=20),
                    route_provider=lambda state: SupervisorDecision("sintetizar", "Prueba del límite"))
    state = agent.procesar_turno("Consulta simulada", agent.nueva_conversacion())
    assert state["iterations"] == 20
    assert state["pendiente_hitl"]


@pytest.mark.parametrize("approved", [True, False])
def test_requests_accumulate_trace_but_reset_operational_data(approved):
    starts = []

    def provider(state):
        if state["iterations"] == 0:
            starts.append(deepcopy(state))
        from agentes.nodes.supervisor import fallback_decision
        return fallback_decision(state)

    def with_action(state):
        return {**synthesize(state),
                "pending_action": PendingAction("prueba", "Borrador", {"items": [1]})}

    agent = service(route_provider=provider, sintetizar_node=with_action)
    graph_instance = agent._graph
    tid = agent.nueva_conversacion()
    pending = agent.procesar_turno("Primero", tid)
    final = agent.resolver_plan(tid, approved, plan_id=pending["plan_id"])
    new = agent.procesar_turno("Segundo", tid)
    assert agent._graph is graph_instance
    assert len(starts) == 2
    second_start = starts[1]
    assert second_start["debug_trace"] == final["debug_trace"] + ["inicio de pedido"]
    assert second_start["user_message"] == "Segundo" and second_start["thread_id"] == tid
    assert second_start["specialist_results"] == {} and second_start["final_answer"] == ""
    assert second_start["plan"] == [] and second_start["pending_action"] is None
    assert second_start["approved"] is None and second_start["supervisor_decision"] is None
    assert second_start["iterations"] == 0 and second_start["done"] is False
    assert new["iterations"] == pending["iterations"] == 4
    assert new["debug_trace"] == final["debug_trace"] + pending["debug_trace"]

    other = agent.nueva_conversacion()
    independent = agent.procesar_turno("Otro hilo", other)
    assert independent["debug_trace"] == pending["debug_trace"]
    assert independent["debug_trace"].count("inicio de pedido") == 1
    assert agent.consultar_estado(tid) == new
    independent["debug_trace"].append("cambio del cliente")
    assert agent.consultar_estado(other)["debug_trace"] == pending["debug_trace"]
