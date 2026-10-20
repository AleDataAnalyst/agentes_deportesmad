"""Regresión del grafo con oráculos revisables en JSON y especialistas dobles.

Las preguntas son contexto del caso, no etiquetas para evaluar un router LLM.
Las expectativas no se generan ejecutando el código que se está comprobando.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from agentes.agent import AgentService
from agentes.contracts import Evidence, SupervisorDecision, ToolResult
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.settings import AgentSettings

DATASET = json.loads((Path(__file__).parent / "data/golden_graph_v1.json").read_text(encoding="utf-8"))
PARAMS = [(case, decision) for case in DATASET["cases"]
          for decision in ([None] if "exception" in case["expected"] else [True, False])]


def test_golden_catalog_is_explicit_and_fixtures_are_complete():
    assert DATASET["schema_version"] == 1
    assert DATASET["mode"] == "simulated_specialists"
    ids = [case["id"] for case in DATASET["cases"]]
    assert len(ids) == len(set(ids))
    for case in DATASET["cases"]:
        assert case["question"].startswith("[SIMULADO]")
        assert set(case["specialists"]) == {"documental", "instalaciones"}
        for fixture in case["specialists"].values():
            value = DATASET["fixtures"][fixture]
            assert value["status"] in ("ok", "abstained", "error")
            assert isinstance(value["answer"], str)
            assert all(evidence["source"].startswith("test://") for evidence in value["evidence"])


def _service(case, calls):
    """Usa montaje público y funciones reales; solo simula resultados externos."""
    def documentary(request):
        calls.append(("documental", request["pedido"]))
        if case.get("documental_behavior") == "raise":
            raise RuntimeError("EJECUTOR_DOCUMENTAL_SIMULADO")
        fixture = deepcopy(DATASET["fixtures"][case["specialists"]["documental"]])
        data = fixture["data"]
        return {"documental": {
            **data, "request_id": request["request_id"], "resultado": fixture["answer"],
            "fuentes": [evidence["source"] for evidence in fixture["evidence"]],
            "abstained": data.get("abstained", fixture["status"] == "abstained"),
            "errores": [fixture["error"]] if fixture.get("error") else [],
            "limitaciones": data.get("limitaciones", []), "eventos": [],
        }}

    def installations(state):
        calls.append(("instalaciones", state["user_message"]))
        fixture = deepcopy(DATASET["fixtures"][case["specialists"]["instalaciones"]])
        fixture["evidence"] = [Evidence(**item) for item in fixture["evidence"]]
        return {"specialist_results": {**state["specialist_results"],
                "instalaciones": ToolResult(**fixture)}}

    def counted_apply(state):
        calls.append(("aplicar", state["approved"]))
        return aplicar(state)

    provider = None
    if case.get("route_provider") == "invalid":
        provider = lambda state: SupervisorDecision("ruta_inexistente", "[SIMULADO]")
    elif case.get("route_provider") == "finish":
        provider = lambda state: SupervisorDecision("FINISH", "[SIMULADO]")
    return AgentService(
        documental_node=crear_adaptador_documental(ejecutar_documental=documentary),
        instalaciones_node=installations, sintetizar_node=sintetizar,
        aplicar_node=counted_apply, route_provider=provider,
        settings=AgentSettings(max_iter=case.get("max_iter", 8)),
    )


@pytest.mark.parametrize("case,decision", PARAMS,
                         ids=[case["id"] + ("-error" if decision is None else "-aprobar" if decision else "-rechazar")
                              for case, decision in PARAMS])
def test_golden_graph_lifecycle(case, decision):
    before = deepcopy(DATASET)
    calls = []
    service = _service(case, calls)
    tid, other = service.nueva_conversacion(), service.nueva_conversacion()
    untouched = service.consultar_estado(other)
    expected = case["expected"]
    if "exception" in expected:
        assert expected["exception"] == "RuntimeError"
        with pytest.raises(RuntimeError, match=expected["error_contains"]):
            service.procesar_turno(case["question"], tid)
        state = service.consultar_estado(tid)
        assert state["plan_id"] is None and not state["pendiente_hitl"]
        assert state["approved"] is None and state["done"] is False
        assert not state["specialist_results"] and not state["final_answer"] and not state["plan"]
        assert [name for name, _ in calls] == ["documental"]
        with pytest.raises(ValueError, match="REQUEST_INCOMPLETE"):
            service.procesar_turno("[SIMULADO] No sobrescribir", tid)
        assert service.consultar_estado(other) == untouched
        assert DATASET == before
        return

    pending = service.procesar_turno(case["question"], tid)
    assert pending["pendiente_hitl"] and pending["approved"] is None and pending["done"] is False
    assert pending["plan"] and all(isinstance(item, str) and item.strip() for item in pending["plan"])
    assert pending["plan_id"] and service.consultar_estado(other) == untouched
    trace = pending["debug_trace"]
    routes = [event.split(" -> ", 1)[1].split(";", 1)[0]
              for event in trace if event.startswith("iter ")]
    assert routes == expected["routes"]
    assert [name for name, _ in calls] == [role for role in routes if role in ("documental", "instalaciones")]
    assert f"síntesis: {expected['useful']} de 2 resultados útiles" in trace
    for text in expected.get("trace_contains", []):
        assert any(text in event for event in trace)
    answer = pending["final_answer"]
    sources = [line.removeprefix("Fuente: ") for line in answer.splitlines() if line.startswith("Fuente: ")]
    assert sources == expected["sources"]
    for text in expected["contains"]:
        assert text in answer
    for text in expected["not_contains"] + DATASET["forbidden_claims"]:
        assert text not in answer
    with pytest.raises(ValueError, match="HITL_PENDING"):
        service.procesar_turno("[SIMULADO] Esperar decisión", tid)

    final = service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
    assert final["thread_id"] == tid and final["plan_id"] == pending["plan_id"]
    assert final["done"] is decision and not final["pendiente_hitl"]
    assert [value for name, value in calls if name == "aplicar"] == [decision]
    assert final["debug_trace"] == trace + ["HITL -> " + ("plan aprobado" if decision else "plan rechazado")]
    if decision:
        assert answer in final["final_answer"]
    else:
        assert final["plan"] == [] and final["specialist_results"] == {} and final["pending_action"] is None
    call_snapshot = list(calls)
    assert service.resolver_plan(tid, decision, plan_id=pending["plan_id"]) == final
    assert calls == call_snapshot
    new = service.procesar_turno("[SIMULADO] Otro pedido", tid)
    assert new["plan_id"] != pending["plan_id"] and new["approved"] is None and new["done"] is False
    assert new["debug_trace"] == final["debug_trace"] + trace
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
    assert service.consultar_estado(other) == untouched
    assert DATASET == before
