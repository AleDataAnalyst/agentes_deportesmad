"""Estado síncrono con datos sintéticos; sin LangGraph, red, LLM ni RAG."""
from copy import deepcopy

import pytest

from agentes.contracts import Evidence, PendingAction, SupervisorDecision, ToolResult
from agentes.state import _acumular, initial_state, plan_is_ready, state_from_graph


@pytest.mark.parametrize("actual,nuevo,expected", [
    (None, None, []), (None, ["nuevo"], ["nuevo"]),
    (["previo"], None, ["previo"]),
    (["previo"], ["uno", "dos"], ["previo", "uno", "dos"]),
])
def test_accumulator_combines_without_mutating_inputs(actual, nuevo, expected):
    before = deepcopy((actual, nuevo))
    result = _acumular(actual, nuevo)
    assert result == expected
    assert (actual, nuevo) == before
    assert result is not actual and result is not nuevo


def test_python_dict_update_replaces_trace_without_running_accumulator():
    state = initial_state("prueba")
    state.update({"debug_trace": ["nuevo"]})
    assert state["debug_trace"] == ["nuevo"]


def synthetic_result():
    return ToolResult(
        "ok", "[PRUEBA SINTÉTICA] respuesta",
        evidence=[Evidence("test://documental", "[PRUEBA SINTÉTICA] fragmento",
                           metadata={"tags": ["prueba"], "details": {"pages": [1]}})],
        data={"simulated": True, "items": [{"name": "prueba"}]},
    )


@pytest.mark.parametrize("message,thread", [
    ("[PRUEBA SINTÉTICA] pedido", "hilo-prueba"),
    ("", "hilo-prueba"),  # La implementación admite mensaje vacío.
    ("  texto de prueba  ", " hilo-prueba "),  # Valida sin normalizar.
])
def test_initial_state_preserves_input_and_initializes_clean_fields(message, thread):
    state = initial_state(message, thread)
    assert state["user_message"] == message and state["thread_id"] == thread
    assert state["approved"] is None and state["done"] is False
    assert state["iterations"] == 0 and state["supervisor_decision"] is None
    assert state["specialist_results"] == {} and state["final_answer"] == ""
    assert state["plan"] == [] and state["pending_action"] is None


def test_initial_states_have_independent_collections():
    first, second = initial_state("prueba"), initial_state("prueba")
    for field in ("specialist_results", "plan", "debug_trace"):
        assert first[field] is not second[field]
    before = deepcopy(second)
    first["specialist_results"]["documental"] = synthetic_result()
    first["plan"].append("[PRUEBA SINTÉTICA] paso")
    first["debug_trace"].append("Evento de prueba")
    assert second == before


@pytest.mark.parametrize("approved", [True, False])
def test_new_request_on_same_thread_does_not_reuse_previous_data(approved):
    # Python puro: initial_state prepara el input, no combina checkpoints.
    previous = initial_state("pedido anterior", "hilo-prueba")
    previous.update(specialist_results={"documental": synthetic_result()},
                    final_answer="Respuesta anterior", plan=["Paso anterior"],
                    approved=approved, done=approved, iterations=7,
                    supervisor_decision=SupervisorDecision("FINISH", "Prueba"))
    before = deepcopy(previous)
    new = initial_state("pedido nuevo", "hilo-prueba")
    assert new["thread_id"] == previous["thread_id"]
    assert new["specialist_results"] == {} and new["plan"] == []
    assert new["approved"] is None and new["supervisor_decision"] is None
    assert new["final_answer"] == "" and new["done"] is False and new["iterations"] == 0
    assert previous == before


@pytest.mark.parametrize("message", [None, 1, True, [], {}, b"prueba"])
def test_initial_state_rejects_existing_invalid_message_types(message):
    with pytest.raises(TypeError, match="user_message"):
        initial_state(message)


@pytest.mark.parametrize("thread", [None, 1, True, [], {}, "", " \t\n"])
def test_initial_state_rejects_existing_invalid_thread_ids(thread):
    with pytest.raises(ValueError, match="thread_id"):
        initial_state("prueba", thread)


def test_conversion_incorporates_known_fields_and_replaces_collections():
    # state_from_graph copia la salida ya acumulada; no aplica el reducer.
    base = initial_state("anterior", "hilo-prueba")
    base.update(specialist_results={"instalaciones": synthetic_result()},
                plan=["Paso anterior"], debug_trace=["Evento anterior"],
                presentation={"expanded": True, "labels": ["prueba"]})
    result = {
        "user_message": "[PRUEBA SINTÉTICA] nuevo",
        "thread_id": "hilo-prueba",
        "supervisor_decision": SupervisorDecision("FINISH", "Prueba"),
        "specialist_results": {"documental": synthetic_result()},
        "final_answer": "[PRUEBA SINTÉTICA] respuesta",
        "plan": ["[PRUEBA SINTÉTICA] paso"],
        "pending_action": PendingAction("prueba", "Borrador sintético", {"items": [1]}),
        "approved": None, "iterations": 4, "done": False,
        "debug_trace": ["Evento nuevo"],
    }
    before_base, before_result = deepcopy(base), deepcopy(result)
    copied = state_from_graph(result, base)
    for field, value in result.items():
        assert copied[field] == value
    assert copied["presentation"] == base["presentation"]
    assert set(copied["specialist_results"]) == {"documental"}
    assert copied["plan"] == result["plan"] and copied["debug_trace"] == result["debug_trace"]
    assert base == before_base and result == before_result


@pytest.fixture
def nested_inputs():
    base = initial_state("prueba", "hilo-prueba")
    base.update(specialist_results={"documental": synthetic_result()},
                pending_action=PendingAction("prueba", "Borrador", {"nested": {"items": [1]}}),
                presentation={"messages": [{"text": "[PRUEBA SINTÉTICA] burbuja"}]})
    result = {"specialist_results": {"documental": synthetic_result()},
              "plan": ["Paso de prueba"], "debug_trace": ["Evento de prueba"]}
    return base, result


def mutate_result(result):
    tool = result["specialist_results"]["documental"]
    tool.answer = "Modificación de prueba"
    tool.evidence[0].content = "Fragmento modificado"
    tool.evidence[0].metadata["tags"].append("otro")
    tool.evidence[0].metadata["details"]["pages"].append(2)
    tool.evidence.append(Evidence("test://otro", "Otro fragmento de prueba"))
    tool.data["items"][0]["name"] = "modificado"


@pytest.mark.parametrize("use_result", [True, False])
def test_client_copy_cannot_mutate_base_or_result(nested_inputs, use_result):
    base, result = nested_inputs
    if not use_result:
        result.pop("specialist_results")  # Comprueba también objetos heredados de base.
    before_base, before_result = deepcopy(base), deepcopy(result)
    copied = state_from_graph(result, base)
    mutate_result(copied)
    copied["plan"].append("Otro paso")
    copied["debug_trace"].append("Otro evento")
    copied["pending_action"].payload["nested"]["items"].append(2)
    copied["presentation"]["messages"][0]["text"] = "Cambio del cliente"
    assert base == before_base and result == before_result


@pytest.mark.parametrize("use_result", [True, False])
def test_changes_to_originals_after_copy_do_not_reach_client(nested_inputs, use_result):
    base, result = nested_inputs
    if not use_result:
        result.pop("specialist_results")
    copied = state_from_graph(result, base)
    before_copy = deepcopy(copied)
    mutate_result(base)
    if use_result:
        mutate_result(result)
    result["plan"].append("Paso posterior")
    result["debug_trace"].append("Evento posterior")
    base["pending_action"].payload["nested"]["items"].append(2)
    base["presentation"]["messages"][0]["text"] = "Cambio posterior"
    assert copied == before_copy


def test_conversion_without_base_uses_initial_defaults():
    copied = state_from_graph({"final_answer": "Respuesta sintética"}, base=None)
    expected = initial_state("")
    expected["final_answer"] = "Respuesta sintética"
    assert copied == expected


def test_empty_base_does_not_insert_initial_defaults():
    base = {}
    assert state_from_graph({"plan": ["Paso de prueba"]}, base) == {"plan": ["Paso de prueba"]}
    assert state_from_graph({}, base) == {}
    assert base == {}


def test_unknown_result_fields_are_ignored_and_base_presentation_is_preserved():
    base = {"plan_id": "plan-prueba", "pendiente_hitl": True,
            "presentation": {"labels": ["base"]}}
    result = {"plan_id": "otro-plan", "pendiente_hitl": False,
              "presentation": {"labels": ["resultado"]}, "unknown": "prueba",
              "final_answer": "Respuesta sintética"}
    copied = state_from_graph(result, base)
    assert copied == {**base, "final_answer": "Respuesta sintética"}
    assert "unknown" not in copied
    without_base = state_from_graph(result)
    assert all(field not in without_base for field in ("plan_id", "pendiente_hitl", "presentation", "unknown"))


@pytest.mark.parametrize("approved", [None, False, True])
def test_ready_plan_is_independent_of_approval(approved):
    state = {"final_answer": "  [PRUEBA SINTÉTICA] respuesta  ",
             "plan": ["  Paso de prueba  ", "Segundo paso"], "approved": approved}
    assert plan_is_ready(state) is True
    state.pop("approved")
    assert plan_is_ready(state) is True


@pytest.mark.parametrize("state", [
    {}, {"plan": ["Paso"]}, {"final_answer": "Respuesta"},
    {"final_answer": "", "plan": ["Paso"]},
    {"final_answer": " \t\n", "plan": ["Paso"]},
    {"final_answer": None, "plan": ["Paso"]},
    {"final_answer": 1, "plan": ["Paso"]},
    {"final_answer": True, "plan": ["Paso"]},
    {"final_answer": ["Respuesta"], "plan": ["Paso"]},
    {"final_answer": "Respuesta", "plan": []},
    {"final_answer": "Respuesta", "plan": None},
    {"final_answer": "Respuesta", "plan": "Paso"},
    {"final_answer": "Respuesta", "plan": ("Paso",)},
    {"final_answer": "Respuesta", "plan": {"paso": "Texto"}},
    {"final_answer": "Respuesta", "plan": [""]},
    {"final_answer": "Respuesta", "plan": [" \t\n"]},
    {"final_answer": "Respuesta", "plan": ["Paso válido", ""]},
    {"final_answer": "Respuesta", "plan": ["Paso válido", None]},
    {"final_answer": "Respuesta", "plan": [1]},
    {"final_answer": "Respuesta", "plan": [False]},
    {"final_answer": "Respuesta", "plan": [["Paso"]]},
])
def test_plan_rejects_missing_empty_or_wrongly_typed_values(state):
    assert plan_is_ready(state) is False
