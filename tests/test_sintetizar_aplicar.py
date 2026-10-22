"""Nodos reales y servicio con especialistas dobles; sin RAG, HTTP ni modelos."""

from copy import deepcopy

import pytest

from agentes.agent import AgentService
from agentes.contracts import Evidence, PendingAction, ToolResult
from agentes.documental_adapter import crear_adaptador_documental
from agentes.nodes.aplicar import aplicar, aplicar_node
from agentes.nodes.sintetizar import sintetizar, sintetizar_node
from agentes.settings import AgentSettings
from agentes.state import initial_state, plan_is_ready


def useful(answer="Texto de prueba", **kwargs):
    return ToolResult("ok", answer, **kwargs)


def state_with(**results):
    return {**initial_state("Consulta vigente"), "specialist_results": results}


def test_synthesis_two_useful_results_preserves_evidence_notes_and_input():
    state = state_with(
        documental=useful("Condición documental de prueba", evidence=[
            Evidence("test://documento", "Fragmento real del doble", metadata={
                "warnings": ["Vigencia pendiente"], "captured_at": "2026-10-13"})],
            data={"limitaciones": ["Sin imagen"], "eventos": [{"tool": "rag"}]}),
        instalaciones=useful("Datos del centro de prueba", evidence=[
            Evidence("test://centro", "")], data={"advertencias": ["No acredita plazas"]}))
    before = deepcopy(state)
    result = sintetizar_node(state, node=sintetizar)
    assert state == before
    assert plan_is_ready(result) and result["done"] is False and result["approved"] is None
    assert set(result) == {"final_answer", "plan", "done", "approved", "debug_trace"}
    for text in ("Consulta vigente", "Condición documental", "Datos del centro",
                 "test://documento", "Fragmento real del doble", "Vigencia pendiente",
                 "2026-10-13", "Sin imagen", "test://centro", "No acredita plazas"):
        assert text in result["final_answer"]
    assert result["final_answer"].count("Fragmento aportado:") == 1
    assert "score" not in result["final_answer"]
    assert "ambos especialistas" in result["final_answer"]
    assert result["debug_trace"] == ["síntesis: 2 de 2 resultados útiles"]


@pytest.mark.parametrize("other,label", [
    (ToolResult("error", "Texto parcial", error="Timeout", data={"errores": ["Detalle"]}), "error"),
    (ToolResult("abstained", "No hay evidencia", data={"limitaciones": ["Sin corpus"]}), "abstención"),
    (ToolResult("ok", ""), "sin contenido útil"),
])
def test_partial_result_does_not_turn_failure_into_success(other, label):
    state = state_with(documental=useful(), instalaciones=other)
    before = deepcopy(state)
    result = sintetizar(state)
    answer = result["final_answer"]
    assert label in answer and "Respuesta parcial" in answer
    assert "síntesis: 1 de 2 resultados útiles" in result["debug_trace"]
    if other.answer:
        assert f"Contenido declarado, no confirmado: {other.answer}" in answer
    if other.error:
        assert other.error in answer and "Detalle" in answer
    assert state == before and plan_is_ready(result)


@pytest.mark.parametrize("results", [
    {},
    {"documental": ToolResult("abstained", "Sin evidencia"),
     "instalaciones": ToolResult("error", "", error="Sin conexión")},
    {"documental": useful("")},
])
def test_no_useful_results_produces_informative_plan_without_invented_sources(results):
    result = sintetizar(state_with(**results))
    assert "No hay resultados útiles" in result["final_answer"]
    assert "Fuente:" not in result["final_answer"]
    assert any("Aportar" in step for step in result["plan"])
    assert any("Reformular" in step for step in result["plan"])
    assert plan_is_ready(result) and result["done"] is False and result["approved"] is None


def test_missing_role_differs_from_failed_or_abstained_role():
    answer = sintetizar(state_with(documental=useful()))["final_answer"]
    assert "instalaciones: sin resultado; especialista todavía no consultado" in answer
    assert "instalaciones: error" not in answer and "instalaciones: abstención" not in answer


@pytest.mark.parametrize("place", ["data", "metadata"])
def test_fallback_is_explicitly_historical_and_date_is_never_completed(place):
    notes = {"fallback": True, "fecha_captura_fallback": "13/10",
             "fecha_consulta": "2026-10-17", "advertencias": ["Datos antiguos"]}
    result = useful(evidence=[Evidence("test://historico", "", metadata=notes if place == "metadata" else {})],
                    data=notes if place == "data" else {})
    answer = sintetizar(state_with(documental=result))["final_answer"]
    assert "Fallback histórico" in answer and "no acredita condiciones actuales" in answer
    assert "13/10" in answer and "2026-10-17" in answer and "Datos antiguos" in answer
    assert "2026-10-13" not in answer and "Fragmento aportado" not in answer


@pytest.mark.parametrize("data", [{"abstained": True}, {"errores": ["Fallo"]}])
def test_inconsistent_ok_is_not_presented_as_useful(data):
    result = sintetizar(state_with(documental=useful("Texto no confirmado", data=data)))
    assert "No hay resultados útiles" in result["final_answer"]
    assert "Contenido declarado, no confirmado: Texto no confirmado" in result["final_answer"]


def test_error_and_abstention_survive_together():
    result = ToolResult("error", "Parcial", error="Error RAG", data={
        "abstained": True, "errores": ["Error RAG"], "limitaciones": ["Sin índice"]})
    answer = sintetizar(state_with(documental=result))["final_answer"]
    assert "error" in answer and "Abstención declarada" in answer and "Sin índice" in answer


def pending_state():
    state = state_with(documental=useful())
    state.update(sintetizar(state))
    state["pending_action"] = PendingAction("informativo", "Propuesta", {"items": [1]})
    return state


@pytest.mark.parametrize("decision", [True, False])
def test_apply_is_partial_does_not_mutate_and_wrapper_adds_one_event(decision):
    state = {**pending_state(), "approved": decision}
    before = deepcopy(state)
    patch = aplicar(state)
    assert patch["done"] is decision and state == before
    assert "debug_trace" not in patch and "approved" not in patch and "plan_id" not in patch
    assert patch["pending_action"] is None
    if decision:
        assert state["final_answer"] in patch["final_answer"]
        assert "No se ha ejecutado ninguna acción externa" in patch["final_answer"]
    else:
        assert patch["plan"] == [] and patch["specialist_results"] == {}
        assert "rechazada" in patch["final_answer"]
    wrapped = aplicar_node(state, node=aplicar)
    assert wrapped["debug_trace"] == ["HITL -> " + ("plan aprobado" if decision else "plan rechazado")]
    assert state == before


@pytest.mark.parametrize("decision", [None, 0, 1, "True", [], {}])
def test_apply_standalone_requires_real_boolean(decision):
    with pytest.raises(ValueError, match="HITL_DECISION_REQUIRED"):
        aplicar({**pending_state(), "approved": decision})


def test_apply_requires_decision_field_and_valid_plan():
    state = pending_state()
    del state["approved"]
    with pytest.raises(ValueError, match="HITL_DECISION_REQUIRED"):
        aplicar(state)
    with pytest.raises(ValueError, match="HITL_PLAN_REQUIRED"):
        aplicar({**state, "approved": True, "plan": []})


@pytest.mark.parametrize("patch", [{"approved": False}, {"approved": True}, {"done": True}])
def test_standalone_synthesis_never_overrides_a_resolved_state(patch):
    with pytest.raises(ValueError, match="SYNTHESIS_CONTRACT"):
        sintetizar({**state_with(), **patch})


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("doc_status", ["ok", "abstained", "error"])
def test_real_nodes_in_service_pause_resume_idempotency_new_request_and_isolation(decision, doc_status):
    calls = []
    apply_calls = []
    def documental(request):
        calls.append(deepcopy(request))
        return {"documental": {
            "request_id": request["request_id"], "resultado": "Texto documental de prueba",
            "fuentes": ["test://fuente"], "abstained": doc_status == "abstained",
            "errores": ["Fallo simulado"] if doc_status == "error" else [],
            "limitaciones": ["Sin imagen"], "eventos": [{"tool": "rag", "ok": doc_status == "ok"}]}}
    def installations(state):
        return {"specialist_results": {**state["specialist_results"],
                "instalaciones": useful("Centro simulado", evidence=[Evidence("test://centro", "")])}}
    def counted_apply(state):
        apply_calls.append(state["approved"])
        return aplicar(state)
    service = AgentService(
        documental_node=crear_adaptador_documental(ejecutar_documental=documental),
        instalaciones_node=installations, sintetizar_node=sintetizar,
        aplicar_node=counted_apply, settings=AgentSettings())
    tid, other = service.nueva_conversacion(), service.nueva_conversacion()
    untouched = service.consultar_estado(other)
    pending = service.procesar_turno("Primer pedido", tid)
    assert pending["pendiente_hitl"] and pending["approved"] is None
    assert pending["done"] is False and apply_calls == [] and len(calls) == 1
    assert set(pending["specialist_results"]) == {"documental", "instalaciones"}
    assert "test://fuente" in pending["final_answer"] and "Sin imagen" in pending["final_answer"]
    assert service.consultar_estado(other) == untouched
    assert pending["debug_trace"].count(f"documental: {doc_status}") == 1
    assert sum(event.startswith("síntesis:") for event in pending["debug_trace"]) == 1
    final = service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
    assert not final["pendiente_hitl"] and final["done"] is decision
    assert apply_calls == [decision] and len(calls) == 1
    assert final["debug_trace"] == pending["debug_trace"] + [
        "HITL -> " + ("plan aprobado" if decision else "plan rechazado")]
    assert service.resolver_plan(tid, decision, plan_id=pending["plan_id"]) == final
    assert apply_calls == [decision]
    if not decision:
        assert final["plan"] == [] and final["specialist_results"] == {}
    new = service.procesar_turno("Segundo pedido", tid)
    assert new["approved"] is None and new["done"] is False and new["pendiente_hitl"]
    assert new["plan_id"] != pending["plan_id"] and len(calls) == 2
    assert calls[0]["request_id"] != calls[1]["request_id"]
    assert "Primer pedido" not in new["final_answer"] and "Segundo pedido" in new["final_answer"]
    assert new["debug_trace"] == final["debug_trace"] + pending["debug_trace"]
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        service.resolver_plan(tid, True, plan_id=pending["plan_id"])
    independent = service.procesar_turno("Tercer pedido", other)
    assert independent["debug_trace"] == pending["debug_trace"]
    assert service.consultar_estado(tid) == new


def test_iteration_limit_can_synthesize_without_specialist_results():
    def unexpected(state):
        pytest.fail("No se debe consultar ningún especialista con max_iter=1")
    service = AgentService(documental_node=unexpected, instalaciones_node=unexpected,
                           sintetizar_node=sintetizar, aplicar_node=aplicar,
                           settings=AgentSettings(max_iter=1))
    pending = service.procesar_turno("Consulta", service.nueva_conversacion())
    assert pending["pendiente_hitl"] and "No hay resultados útiles" in pending["final_answer"]
