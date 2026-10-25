"""Contrato del adaptador con dobles explícitos; no valida retrieval ni modelos."""

from copy import deepcopy
import pytest

from agentes.agent import AgentService
from agentes.contracts import ToolResult
from agentes.documental_adapter import crear_adaptador_documental
from agentes.state import initial_state
from tests.test_import_boundaries import run_python


def envelope(request, **patch):
    return {"request_id": request["request_id"], "resultado": "Respuesta de prueba",
            "fuentes": ["test://normativa"], "abstained": False, "errores": [],
            "limitaciones": ["Imagen no disponible"],
            "eventos": [{"tool": "rag", "ok": True}], **patch}


def adapter_for(patch=None, calls=None):
    def invoke(request):
        if calls is not None:
            calls.append(deepcopy(request))
        return {**request, "documental": envelope(request, **(patch or {})),
                "approved": True, "final_answer": "No copiar"}
    return crear_adaptador_documental(ejecutar_documental=invoke)


@pytest.mark.parametrize("patch,status", [
    ({}, "ok"),
    ({"abstained": True}, "abstained"),
    ({"resultado": " "}, "abstained"),
    ({"errores": ["Fallo RAG", "Timeout"]}, "error"),
    ({"abstained": True, "errores": ["Fallo RAG"]}, "error"),
])
def test_mapping_preserves_all_information_and_only_updates_own_fields(patch, status):
    calls = []
    node = adapter_for(patch, calls)
    state = initial_state("Consulta", "mismo-hilo")
    state["specialist_results"] = {"instalaciones": ToolResult("ok", "Catálogo")}
    before = deepcopy(state)
    update = node(state)
    assert state == before
    assert set(update) == {"specialist_results", "debug_trace"}
    assert update["specialist_results"]["instalaciones"] == before["specialist_results"]["instalaciones"]
    result = update["specialist_results"]["documental"]
    assert result.status == status
    assert result.data == envelope(calls[0], **patch)
    assert result.answer == result.data["resultado"]
    assert result.error == ("; ".join(patch["errores"]) if patch.get("errores") else None)
    assert result.evidence[0].source == "test://normativa"
    assert result.evidence[0].content == ""
    assert result.evidence[0].score is None and result.evidence[0].metadata == {}
    assert update["debug_trace"] == [f"documental: {status}"]
    update["specialist_results"]["instalaciones"].data["changed"] = True
    assert state == before
    node(state)
    assert calls[0]["request_id"] != calls[1]["request_id"]
    assert calls[0]["pedido"] == "Consulta"
    assert "thread_id" not in calls[0] and "approved" not in calls[0]


def test_injected_callable_is_only_called_on_execution():
    calls = []
    def invoke(request):
        calls.append(request)
        return {"documental": envelope(request)}
    node = crear_adaptador_documental(ejecutar_documental=invoke)
    assert calls == []
    assert node(initial_state("Consulta"))["specialist_results"]["documental"].status == "ok"
    assert len(calls) == 1


def test_adapter_import_does_not_load_specialist_or_rag():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder
        class Block(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in ("agentes.grafo_documental", "agentes.nodes.documental",
                                "agentes.tools.rag", "rag") or fullname.startswith("rag."):
                    raise AssertionError(fullname)
        sys.meta_path.insert(0, Block())
        from agentes.documental_adapter import crear_adaptador_documental
        crear_adaptador_documental(ejecutar_documental=lambda state: {})
    ''')


def test_real_documental_graph_public_entry_with_explicit_specialist_double():
    # Compila el componente real, pero sustituye únicamente su nodo documental.
    # No prueba las tools, el RAG ni las dependencias del nodo sustituido.
    run_python('''
        import sys
        from types import ModuleType
        module = ModuleType("agentes.nodes.documental")
        calls = []
        def specialist(state):
            calls.append(dict(state))
            return {"documental": {
                "request_id": state["request_id"], "resultado": "Prueba",
                "fuentes": ["test://fuente"], "abstained": False,
                "errores": [], "limitaciones": [], "eventos": []}}
        module.nodo_documental = specialist
        sys.modules[module.__name__] = module
        from agentes.grafo_documental import obtener_grafo_documental
        from agentes.documental_adapter import crear_adaptador_documental
        from agentes.state import initial_state
        graph = obtener_grafo_documental()
        assert obtener_grafo_documental() is graph
        assert set(graph.get_graph().nodes) == {"__start__", "documental", "__end__"}
        # La puerta histórica sigue siendo compatible, independientemente del adaptador.
        output = graph.invoke({"request_id": "prueba", "pedido": "Consulta"})
        assert output["documental"]["request_id"] == "prueba"
        assert len(calls) == 1
        update = crear_adaptador_documental(ejecutar_documental=specialist)(initial_state("Consulta"))
        assert update["specialist_results"]["documental"].answer == "Prueba"
        assert len(calls) == 2 and calls[1]["pedido"] == "Consulta"
    ''')


def test_explicit_options_and_payload_are_isolated():
    context = ["test://normativa"]
    responses = []
    calls = []
    def invoke(request):
        calls.append(deepcopy(request))
        request["contexto_permitido"].clear()
        output = {"documental": envelope(request)}
        responses.append(output)
        return output
    node = crear_adaptador_documental(
        ejecutar_documental=invoke,
        contexto_permitido=context, image_id="imagen_demo", presupuesto_tools=2,
        preparar_borrador=True)
    context.clear()
    legacy_state = initial_state("Consulta")
    legacy_state.pop("image_id")  # Consumidor anterior al campo por pedido.
    result = node(legacy_state)["specialist_results"]["documental"]
    responses[0]["documental"]["eventos"][0]["ok"] = False
    assert result.data["eventos"][0]["ok"] is True
    node({**legacy_state, "user_message": "Otra consulta"})
    assert all(call["contexto_permitido"] == ["test://normativa"] for call in calls)
    from agentes.image_input import validar_image_id
    assert calls[0]["image_id"] == validar_image_id("imagen_demo")
    assert calls[0]["presupuesto_tools"] == 2 and calls[0]["preparar_borrador"] is True


@pytest.mark.parametrize("patch", [
    {"request_id": "otro"}, {"resultado": None}, {"abstained": 1},
    {"fuentes": "url"}, {"errores": [None]}, {"limitaciones": None},
    {"eventos": ["evento"]},
])
def test_malformed_contract_fails_without_fabricating_result(patch):
    with pytest.raises(ValueError, match="DOCUMENTAL_CONTRACT"):
        adapter_for(patch)(initial_state("Consulta"))


@pytest.mark.parametrize("output", [None, {}, {"documental": None}])
def test_missing_envelope(output):
    node = crear_adaptador_documental(
        ejecutar_documental=lambda request: output)
    with pytest.raises(ValueError, match="DOCUMENTAL_CONTRACT"):
        node(initial_state("Consulta"))


def test_technical_exceptions_propagate():
    def fail(*args):
        raise RuntimeError("Dependencia RAG no disponible")
    with pytest.raises(RuntimeError, match="Dependencia RAG"):
        crear_adaptador_documental(ejecutar_documental=fail)(initial_state("Consulta"))


@pytest.mark.parametrize("message", [None, "", " ", 1])
def test_invalid_message_does_not_execute_callable(message):
    def unexpected(state):
        pytest.fail("No invocar con entrada inválida")
    with pytest.raises(ValueError, match="DOCUMENTAL_INPUT"):
        crear_adaptador_documental(ejecutar_documental=unexpected)({"user_message": message})


@pytest.mark.parametrize("patch", [
    {"presupuesto_tools": 0}, {"presupuesto_tools": True},
    {"contexto_permitido": "url"}, {"image_id": 1}, {"preparar_borrador": 1},
])
def test_invalid_options(patch):
    with pytest.raises((TypeError, ValueError)):
        crear_adaptador_documental(ejecutar_documental=lambda state: {}, **patch)


def test_callable_is_required_and_must_be_callable():
    with pytest.raises(TypeError):
        crear_adaptador_documental()
    with pytest.raises(TypeError, match="ejecutar_documental"):
        crear_adaptador_documental(ejecutar_documental=None)


@pytest.mark.parametrize("decision", [True, False])
@pytest.mark.parametrize("patch", [{}, {"abstained": True}, {"errores": ["Fallo RAG"]}])
def test_main_service_keeps_supervisor_and_human_pause(decision, patch):
    calls = []
    applied = []
    def installations(state):
        return {"specialist_results": {**state["specialist_results"],
                "instalaciones": ToolResult("abstained", "Sin datos de prueba")}}
    def synthesis(state):
        assert set(state["specialist_results"]) == {"documental", "instalaciones"}
        return {"final_answer": "Borrador de integración con dobles", "plan": ["Revisar"]}
    def apply(state):
        applied.append(state["approved"])
        return {"done": state["approved"]}
    service = AgentService(documental_node=adapter_for(patch, calls),
                           instalaciones_node=installations,
                           sintetizar_node=synthesis, aplicar_node=apply)
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Consulta de prueba", tid)
    assert pending["pendiente_hitl"] and pending["approved"] is None
    assert pending["done"] is False and applied == [] and len(calls) == 1
    event = f"documental: {pending['specialist_results']['documental'].status}"
    assert pending["debug_trace"].count(event) == 1
    final = service.resolver_plan(tid, decision, plan_id=pending["plan_id"])
    assert applied == [decision] and final["done"] is decision
    assert not final["pendiente_hitl"] and len(calls) == 1
