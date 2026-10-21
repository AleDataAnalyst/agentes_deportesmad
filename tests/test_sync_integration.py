"""Integracion sin LLM ni tools reales, usando nodos simulados explicitos."""
from copy import deepcopy

import pytest

from agentes.contracts import SupervisorDecision, ToolResult
from agentes.graph import _aplicar_checked, build_graph
from agentes.nodes.supervisor import fallback_decision, supervisor_node
from agentes.state import initial_state


def specialist(role):
    def node(state):
        return {"specialist_results": {
            **state.get("specialist_results", {}),
            role: ToolResult("abstained", "Doble de prueba; sin evidencia real"),
        }}
    return node


def synthesize(state):
    return {"final_answer": "Propuesta simulada", "plan": ["Paso simulado"]}


def apply(state):
    if state["approved"]:
        return {"done": True}
    return {"done": False, "plan": [], "specialist_results": {}, "final_answer": "Rechazado"}


def graph(**options):
    nodes = dict(documental_node=specialist("documental"),
                 instalaciones_node=specialist("instalaciones"),
                 sintetizar_node=synthesize, aplicar_node=apply)
    return build_graph(**{**nodes, **options})


@pytest.mark.parametrize("approved", [True, False])
def test_pause_resume_and_new_request(approved):
    app = graph()
    cfg = {"configurable": {"thread_id": "test"}}
    pending = app.invoke(initial_state("consulta", "test"), cfg)
    assert set(pending["specialist_results"]) == {"documental", "instalaciones"}
    assert pending["plan"] == ["Paso simulado"]
    assert pending["iterations"] == 4
    assert pending["approved"] is None and pending["done"] is False
    assert app.get_state(cfg).next == ("aplicar",)
    app.update_state(cfg, {"approved": approved})
    final = app.invoke(None, cfg)
    assert final["done"] is approved
    assert not app.get_state(cfg).next
    app.invoke(initial_state("otro", "test"), cfg)
    assert app.get_state(cfg).values["approved"] is None
    assert app.get_state(cfg).next == ("aplicar",)
    assert not app.get_state({"configurable": {"thread_id": "otro"}}).values


def test_resume_requires_explicit_decision():
    app = graph()
    cfg = {"configurable": {"thread_id": "pending"}}
    app.invoke(initial_state("consulta"), cfg)
    with pytest.raises(ValueError, match="HITL_DECISION_REQUIRED"):
        app.invoke(None, cfg)


@pytest.mark.parametrize("update", [
    {}, {"final_answer": "texto", "plan": []},
    {"final_answer": "texto", "plan": ["paso"], "approved": True},
    {"final_answer": "texto", "plan": ["paso"], "done": True},
])
def test_invalid_synthesis(update):
    app = graph(sintetizar_node=lambda state: update)
    with pytest.raises(ValueError, match="SYNTHESIS_CONTRACT"):
        app.invoke(initial_state("consulta"), {"configurable": {"thread_id": "invalid"}})


def test_repeated_synthesis_stops_at_limit():
    app = graph(route_provider=lambda state: SupervisorDecision("sintetizar", "prueba"), max_iter=3)
    cfg = {"configurable": {"thread_id": "limit"}}
    pending = app.invoke(initial_state("consulta"), cfg)
    assert pending["iterations"] == 3
    assert app.get_state(cfg).next == ("aplicar",)


@pytest.mark.parametrize("provider", [
    lambda state: SupervisorDecision("inventado", "prueba"),
    lambda state: SupervisorDecision("documental", "rol repetido"),
    lambda state: 1 / 0,
])
def test_provider_falls_back(provider):
    state = initial_state("consulta")
    state["specialist_results"] = {"documental": ToolResult("error", "", error="prueba")}
    assert supervisor_node(state, route_provider=provider)["supervisor_decision"].specialist == "instalaciones"
    assert fallback_decision(state).specialist == "instalaciones"


def test_limit_before_any_specialist_still_prepares_plan():
    app = graph(max_iter=1)
    cfg = {"configurable": {"thread_id": "early"}}
    pending = app.invoke(initial_state("consulta"), cfg)
    assert pending["plan"]
    assert pending["specialist_results"] == {}
    assert app.get_state(cfg).next == ("aplicar",)


def test_apply_cannot_close_a_rejected_plan():
    app = graph(aplicar_node=lambda state: {"done": True})
    cfg = {"configurable": {"thread_id": "reject-contract"}}
    app.invoke(initial_state("consulta"), cfg)
    app.update_state(cfg, {"approved": False})
    with pytest.raises(ValueError, match="APPLY_CONTRACT"):
        app.invoke(None, cfg)
    assert app.get_state(cfg).values["done"] is False


@pytest.mark.parametrize("approved", [True, False])
@pytest.mark.parametrize("events", [None, [], ["aplicar: uno", "aplicar: dos"]])
def test_apply_wrapper_returns_only_new_events_and_preserves_input(approved, events):
    state = {**initial_state("consulta"), "approved": approved,
             "final_answer": "Respuesta", "plan": ["Paso"],
             "debug_trace": ["evento previo"]}
    update = {"done": approved}
    if events is not None:
        update["debug_trace"] = events
    before_state, before_update = deepcopy(state), deepcopy(update)
    result = _aplicar_checked(state, node=lambda state: update)
    hitl = "HITL -> " + ("plan aprobado" if approved else "plan rechazado")
    assert result["debug_trace"] == (events or []) + [hitl]
    assert state == before_state and update == before_update


@pytest.mark.parametrize("approved", [True, False])
def test_real_graph_accumulates_events_once_in_order(approved):
    def traced_specialist(role):
        def node(state):
            return {**specialist(role)(state), "debug_trace": [f"{role}: uno", f"{role}: dos"]}
        return node

    app = graph(
        documental_node=traced_specialist("documental"),
        instalaciones_node=traced_specialist("instalaciones"),
        sintetizar_node=lambda state: {**synthesize(state), "debug_trace": ["síntesis"]},
        aplicar_node=lambda state: {**apply(state), "debug_trace": ["aplicar: uno", "aplicar: dos"]},
    )
    cfg = {"configurable": {"thread_id": "traza"}}
    input_state = initial_state("consulta", "traza")
    before = deepcopy(input_state)
    pending = app.invoke(input_state, cfg)
    expected = [
        "inicio de pedido", "iter 1: supervisor -> documental; origen=reglas",
        "documental: uno", "documental: dos",
        "iter 2: supervisor -> instalaciones; origen=reglas",
        "instalaciones: uno", "instalaciones: dos",
        "iter 3: supervisor -> sintetizar; origen=reglas", "síntesis",
        "iter 4: supervisor -> FINISH; origen=reglas",
    ]
    assert pending["debug_trace"] == expected
    assert input_state == before
    app.update_state(cfg, {"approved": approved})
    assert app.get_state(cfg).values["debug_trace"] == expected
    final = app.invoke(None, cfg)
    hitl = "HITL -> " + ("plan aprobado" if approved else "plan rechazado")
    assert final["debug_trace"] == expected + ["aplicar: uno", "aplicar: dos", hitl]
