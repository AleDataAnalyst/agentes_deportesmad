"""Comprueba marcadores de simulación, escenarios y ejecutor de la demo."""
import json
from copy import deepcopy

import pytest

from agentes.demo import (
    _aplicar_demo, _especialista_demo, _sintetizar_demo,
    crear_servicio_demo, main, run_demo,
)
from agentes.settings import AgentSettings
from agentes.state import initial_state


@pytest.mark.parametrize("role", ["documental", "instalaciones"])
@pytest.mark.parametrize("scenario", ["ok", "abstained", "error"])
def test_specialist_returns_only_new_events_without_mutating_state(role, scenario):
    state = initial_state("Consulta")
    state["debug_trace"] = ["evento previo"]
    before = deepcopy(state)
    update = _especialista_demo(state, role=role, scenario=scenario)
    assert update["debug_trace"] == [f"[SIMULADO] {role}: {scenario}"]
    assert state == before


def test_synthesis_returns_only_new_events_without_mutating_state():
    state = initial_state("Consulta")
    before = deepcopy(state)
    update = _sintetizar_demo(state)
    assert update["debug_trace"] == ["[SIMULADO] síntesis: borrador de prueba listo"]
    assert state == before


@pytest.mark.parametrize("approved", [True, False])
def test_apply_leaves_hitl_trace_to_wrapper_and_does_not_mutate_state(approved):
    state = {**initial_state("Consulta"), **_sintetizar_demo(initial_state("Consulta")),
             "approved": approved}
    before = deepcopy(state)
    update = _aplicar_demo(state)
    assert "debug_trace" not in update
    assert state == before


@pytest.mark.parametrize("scenario", ["ok", "abstained", "error"])
def test_scenarios_pause_without_approval(scenario):
    report = run_demo(scenario=scenario, settings=AgentSettings())
    assert report["mode"] == "demo" and report["final_state"] is None
    pending = report["pending_state"]
    assert pending["pendiente_hitl"] and pending["approved"] is None and not pending["done"]
    assert "DEMO SIMULADA" in pending["final_answer"]
    assert len(pending["plan"]) == 2
    assert set(pending["specialist_results"]) == {"documental", "instalaciones"}
    for role, result in pending["specialist_results"].items():
        assert result.status == scenario and result.data["simulated"] is True
        if scenario == "ok":
            assert result.evidence[0].source == f"demo://{role}"
            assert result.evidence[0].metadata["simulated"] is True
        else:
            assert result.evidence == []
        if scenario == "error":
            assert result.error.startswith("DEMO_ERROR")


@pytest.mark.parametrize("approved", [True, False])
def test_explicit_decision(approved):
    report = run_demo(aprobado=approved, settings=AgentSettings())
    pending, final = report["pending_state"], report["final_state"]
    assert final["done"] is approved and not final["pendiente_hitl"]
    assert pending["thread_id"] == final["thread_id"]
    assert pending["plan_id"] == final["plan_id"]
    assert pending["approved"] is None and pending["plan"]
    assert "SIMULAD" in final["final_answer"]
    if not approved:
        assert final["plan"] == [] and final["specialist_results"] == {}


def test_factory_can_be_reused_and_client_copies_are_isolated():
    service = crear_servicio_demo(settings=AgentSettings())
    tid = service.nueva_conversacion()
    state = service.procesar_turno("Primero", tid)
    state["specialist_results"]["documental"].evidence[0].metadata.clear()
    assert service.consultar_estado(tid)["specialist_results"]["documental"].evidence[0].metadata["simulated"]
    service.resolver_plan(tid, False, plan_id=state["plan_id"])
    new = service.procesar_turno("Segundo", tid)
    assert new["plan_id"] != state["plan_id"] and new["approved"] is None
    other = service.nueva_conversacion()
    assert service.consultar_estado(other)["specialist_results"] == {}


def test_limit_declares_missing_results():
    report = run_demo(settings=AgentSettings(max_iter=1))
    state = report["pending_state"]
    assert state["specialist_results"] == {}
    assert state["final_answer"].count("no ejecutado") == 2
    assert state["pendiente_hitl"]


@pytest.mark.parametrize("decision,expected", [("pausa", None), ("aprobar", True), ("rechazar", False)])
def test_console_serializes_contracts(capsys, decision, expected):
    assert main(["--decision", decision, "--max-iter", "8"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pending_state"]["specialist_results"]["documental"]["evidence"][0]["metadata"]["simulated"]
    if expected is None:
        assert report["final_state"] is None
    else:
        assert report["final_state"]["done"] is expected


def test_interactive_requires_a_valid_human_choice(monkeypatch, capsys):
    choices = iter(["incorrecto", "rechazar"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(choices))
    assert main(["--interactivo", "--max-iter", "8"]) == 0
    output = capsys.readouterr().out
    assert "Escribe aprobar, rechazar o salir." in output
    final = json.loads(output[output.index("{", output.index("Escribe aprobar")):])
    assert final["final_state"]["done"] is False


def test_interactive_eof_does_not_approve(monkeypatch, capsys):
    def eof(prompt):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    assert main(["--interactivo", "--max-iter", "8"]) == 0
    output = capsys.readouterr().out
    pending, _ = json.JSONDecoder().raw_decode(output)
    assert pending["final_state"] is None
    assert "salida sin aprobar" in output


def test_invalid_scenario_and_non_boolean_decision():
    with pytest.raises(ValueError, match="scenario"):
        crear_servicio_demo(scenario="real")
    with pytest.raises(TypeError, match="aprobado"):
        run_demo(aprobado="False")
