"""Proveedor con modelo doble: no acredita transporte ni inferencia reales."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from agentes.agent import AgentService
from agentes.contracts import Evidence, ROUTE_NAMES, SupervisorDecision, ToolResult
from agentes.nodes.aplicar import aplicar
from agentes.nodes.sintetizar import sintetizar
from agentes.nodes.supervisor import supervisor_node
from agentes.settings import AgentSettings
from agentes.state import initial_state
from agentes.supervisor_llm import MAX_PEDIDO, PROMPT_SUPERVISOR, crear_proveedor_rutas
from tests.test_import_boundaries import run_python


def response(route="instalaciones", reason="Consultar catálogo."):
    return SimpleNamespace(text=json.dumps({"ruta": route, "motivo": reason}), tool_calls=[])


class ModelDouble:
    def __init__(self, result=None):
        self.calls = []
        self.result = result if result is not None else response()

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result(kwargs) if callable(self.result) else self.result


def provider(model, **kwargs):
    return crear_proveedor_rutas(adapter=model, message_factory=SimpleNamespace, **kwargs)


def test_prompt_bounded_view_configuration_and_mutation_isolation(capsys, caplog):
    state = initial_state("x" * (MAX_PEDIDO + 100), "identificador-privado")
    state["specialist_results"]["documental"] = ToolResult(
        "ok", "Respuesta privada", evidence=[Evidence("Fuente privada", "Fragmento privado")],
        data={"password": "secreto"})
    state["debug_trace"].append("Traza privada")
    before = deepcopy(state)
    model = ModelDouble()
    route = provider(model, temperature=0.2, max_output_tokens=128, timeout=7)
    assert model.calls == []
    assert route(state) == SupervisorDecision("instalaciones", "Consultar catálogo.")
    call = model.calls[0]
    assert call["tools"] == [] and call["timeout"] == 7
    assert call["temperature"] == 0.2 and call["max_output_tokens"] == 128
    system, user = call["messages"]
    assert system.role == "system" and system.content == PROMPT_SUPERVISOR
    for role in ROUTE_NAMES:
        assert role in system.content
    assert "No es obligatorio recorrerlos todos" in system.content
    view = json.loads(user.content)
    assert view == {
        "pedido": "x" * MAX_PEDIDO, "rutas_permitidas": list(ROUTE_NAMES),
        "resultados_disponibles": {"documental": {"status": "ok", "tiene_respuesta": True}},
        "tiene_respuesta": False, "plan_listo": False,
    }
    assert user.role == "user"
    assert "privad" not in user.content and "secreto" not in user.content
    user.content = "Mutado por el transporte doble"
    assert state == before
    assert capsys.readouterr().out == caplog.text == ""


@pytest.mark.parametrize("text", [
    "", "  ", "no es JSON", "```json\n{}\n```", "[]", "null", "true",
    '{}', '{"ruta":"documental"}',
    '{"ruta":5,"motivo":"texto"}', '{"ruta":null,"motivo":"texto"}',
    '{"ruta":" ","motivo":"texto"}', '{"ruta":"documental","motivo":false}',
    '{"ruta":"documental","motivo":" "}',
    '{"ruta":"documental","motivo":"texto","approved":true}',
    json.dumps({"ruta": "documental", "motivo": "x" * 241}),
    "x" * 4097, None,
])
def test_invalid_model_output_uses_existing_fallback(text):
    model = ModelDouble(SimpleNamespace(text=text, tool_calls=[]))
    route = provider(model)
    with pytest.raises(ValueError, match="^SUPERVISOR_RESPONSE_INVALID$"):
        route(initial_state("Consulta"))
    update = supervisor_node(initial_state("Consulta"), route_provider=route)
    assert update["supervisor_decision"].specialist == "documental"
    assert "origen=fallback; causa=excepcion_proveedor" in update["debug_trace"][0]


def test_proposed_tools_are_never_executed():
    result = response()
    result.tool_calls = [{"name": "rag_preguntar", "arguments": {"consulta": "Privado"}}]
    with pytest.raises(ValueError, match="SUPERVISOR_RESPONSE_INVALID"):
        provider(ModelDouble(result))(initial_state("Consulta"))


@pytest.mark.parametrize("kind,cause", [
    ("desconocida", "ruta_desconocida"), ("repetida", "especialista_ya_consultado"),
])
def test_route_validation_stays_in_supervisor(kind, cause):
    state = initial_state("Consulta")
    state["specialist_results"]["documental"] = ToolResult("abstained", "")
    proposed = "ruta_no_permitida" if kind == "desconocida" else "documental"
    route = provider(ModelDouble(response(proposed)))
    # El proveedor convierte formato; supervisor mantiene la autoridad de rutas.
    assert route(state).specialist == proposed
    update = supervisor_node(state, route_provider=route)
    assert update["supervisor_decision"].specialist == "instalaciones"
    assert f"origen=fallback; causa={cause}" in update["debug_trace"][0]


@pytest.mark.parametrize("error_type", [RuntimeError, TimeoutError])
def test_adapter_failure_falls_back_without_logging_raw_error(error_type, capsys, caplog):
    # Timeout inmediato doble: no prueba el timeout efectivo de ningún transporte.
    model = ModelDouble(error_type("secreto y respuesta cruda"))
    state = initial_state("Consulta")
    before = deepcopy(state)
    update = supervisor_node(state, route_provider=provider(model))
    assert len(model.calls) == 1
    assert state == before
    assert update["supervisor_decision"].specialist == "documental"
    assert "origen=fallback; causa=excepcion_proveedor" in update["debug_trace"][0]
    assert "secreto" not in str(update)
    assert capsys.readouterr().out == caplog.text == ""


@pytest.mark.parametrize("config", [
    {"timeout": 0}, {"timeout": True}, {"max_output_tokens": -1},
    {"temperature": float("nan")}, {"temperature": -1},
])
def test_invalid_configuration_fails_before_inference(config):
    model = ModelDouble()
    with pytest.raises(ValueError, match="SUPERVISOR_"):
        provider(model, **config)
    assert model.calls == []


@pytest.mark.parametrize("approved", [True, False])
def test_model_can_skip_unneeded_specialist_and_keep_same_plan_hitl(approved):
    def choose(call):
        view = json.loads(call["messages"][1].content)
        if view["plan_listo"]:
            return response("FINISH")
        if "instalaciones" in view["resultados_disponibles"]:
            return response("sintetizar")
        return response("instalaciones")

    def documental_not_needed(state):
        pytest.fail("No debe consultar documental solo por completar una secuencia")

    model = ModelDouble(choose)
    service = AgentService(
        documental_node=documental_not_needed,
        instalaciones_node=lambda state: {"specialist_results": {
            "instalaciones": ToolResult("ok", "Catálogo doble", [Evidence("test://centro", "Centro")])}},
        sintetizar_node=sintetizar, aplicar_node=aplicar, route_provider=provider(model),
    )
    assert model.calls == []
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Catálogo municipal", tid)
    assert len(model.calls) == 3
    assert set(pending["specialist_results"]) == {"instalaciones"}
    assert pending["pendiente_hitl"] and pending["approved"] is None and not pending["done"]
    final = service.resolver_plan(tid, approved, plan_id=pending["plan_id"])
    assert final["thread_id"] == tid and final["plan_id"] == pending["plan_id"]
    assert final["done"] is approved and not final["pendiente_hitl"]
    assert len(model.calls) == 3


def test_repeated_synthesis_stops_at_existing_limit_without_another_model_call():
    model = ModelDouble(response("sintetizar"))
    service = AgentService(
        documental_node=lambda state: pytest.fail("Especialista no solicitado"),
        instalaciones_node=lambda state: pytest.fail("Especialista no solicitado"),
        sintetizar_node=sintetizar, aplicar_node=aplicar, route_provider=provider(model),
        settings=AgentSettings(max_iter=3),
    )
    pending = service.procesar_turno("Consulta", service.nueva_conversacion())
    assert len(model.calls) == 2
    assert pending["iterations"] == 3 and pending["pendiente_hitl"]
    assert "origen=limite" in pending["debug_trace"][-1]


def test_fresh_import_and_service_construction_do_not_load_rag_or_model_modules():
    run_python('''
        import sys
        from importlib.abc import MetaPathFinder
        from types import SimpleNamespace
        class BlockDependencies(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if (fullname.split('.')[0] in {'rag', 'chromadb', 'google'}
                        or fullname.startswith('agentes.llm')):
                    raise AssertionError('Import inesperado: ' + fullname)
        sys.meta_path.insert(0, BlockDependencies())
        from agentes.supervisor_llm import crear_proveedor_rutas
        from agentes.agent import AgentService
        from agentes.nodes.sintetizar import sintetizar
        from agentes.nodes.aplicar import aplicar
        def forbidden(*args, **kwargs):
            raise AssertionError('Consulta durante construcción')
        import socket
        socket.socket.connect = forbidden
        route = crear_proveedor_rutas(
            adapter=SimpleNamespace(generate=forbidden), message_factory=SimpleNamespace)
        AgentService(documental_node=forbidden, instalaciones_node=forbidden,
                     sintetizar_node=sintetizar, aplicar_node=aplicar, route_provider=route)
    ''')
