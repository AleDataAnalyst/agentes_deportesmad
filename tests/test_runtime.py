"""Montaje con tools dobles y sin llamadas RAG/red durante los tests.

La colección global puede haber importado RAG antes de estas fixtures. La
frontera de importación se verifica en subproceso en test_import_boundaries.py.
"""
from copy import deepcopy
from importlib.abc import MetaPathFinder
import json
import socket
import sys
from types import ModuleType, SimpleNamespace

import pytest

from agentes.runtime import crear_servicio, crear_servicio_real
from agentes.supervisor_llm import crear_proveedor_rutas


@pytest.fixture(autouse=True)
def isolated_tools(monkeypatch):
    # El sustituto y el finder evitan nuevas cargas si no ocurrió antes durante
    # colección. No deshacen imports previos: REGISTRY controla las llamadas.
    class BlockRag(MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in {"rag", "chromadb"}:
                raise AssertionError(f"Import inesperado: {fullname}")

    def forbidden(*args, **kwargs):
        pytest.fail("No debe consultar red ni herramientas sin un doble explícito")

    documental_modules = ("agentes.grafo_documental", "agentes.nodes.documental")
    already_loaded = set(sys.modules)
    tool = ModuleType("agentes.tools.rag")
    tool.rag_preguntar = forbidden
    monkeypatch.setitem(sys.modules, "agentes.tools.rag", tool)
    monkeypatch.setattr(sys, "meta_path", [BlockRag(), *sys.meta_path])
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    import agentes.nodes.instalaciones as ni
    import agentes.nodes.documental as nd
    monkeypatch.setitem(nd.REGISTRY, "rag", forbidden)
    monkeypatch.setattr(ni, "consultar_instalaciones", forbidden)
    yield
    # No dejar un documental ligado a la tool doble para otras suites.
    for name in documental_modules:
        if name not in already_loaded:
            module = sys.modules.pop(name, None)
            parent_name, attribute = name.rsplit(".", 1)
            parent = sys.modules.get(parent_name)
            if module is not None and getattr(parent, attribute, None) is module:
                delattr(parent, attribute)


@pytest.fixture
def instalaciones(monkeypatch):
    import agentes.nodes.instalaciones as ni
    observation = {
        "ok": True, "modo": "catalogo", "origen": "api",
        "fuente": "test://catalogo", "fecha_consulta": "2026-10-25T12:00:00+01:00",
        "fecha_captura_fallback": None, "advertencias": [], "error": None,
        "datos": [{"pk": "114782", "nombre": "Centro de prueba",
                   "distrito": "Distrito de prueba", "content_url": "test://centro"}],
    }
    calls = []

    def tool(**kwargs):
        calls.append(kwargs)
        return deepcopy(observation)

    monkeypatch.setattr(ni, "consultar_instalaciones", tool)
    return observation, calls


@pytest.fixture
def mixed(monkeypatch, instalaciones):
    import agentes.grafo_documental as gd
    import agentes.nodes.documental as nd
    calls = []

    def tool(consulta):
        calls.append(consulta)
        return {"ok": True, "resultado": "Respuesta simulada identificada",
                "fuentes": ["test://documento"], "abstained": False, "error": None}

    monkeypatch.setitem(nd.REGISTRY, "rag", tool)
    monkeypatch.setattr(gd, "_grafo", None)
    service = crear_servicio_real()
    assert calls == []  # Pasar invoke no debe ejecutar el componente.
    assert instalaciones[1] == []
    return service, calls


def test_public_gate_is_used_without_invoking_it(monkeypatch):
    import agentes.grafo_documental as gd
    import agentes.runtime as runtime
    from agentes.nodes.instalaciones import nodo_instalaciones

    class Gate:
        def invoke(self, state):
            pytest.fail("No debe consultarse al construir")

    requested = []

    def factory():
        requested.append(True)
        return Gate()

    monkeypatch.setattr(gd, "obtener_grafo_documental", factory)
    captured = {}
    monkeypatch.setattr(runtime, "AgentService", lambda **kwargs: captured.update(kwargs))
    crear_servicio_real()
    assert requested == [True]
    assert captured["instalaciones_node"] is nodo_instalaciones
    assert captured["route_provider"] is None


@pytest.mark.parametrize("approved", [True, False])
def test_injected_llm_provider_reaches_supervisor_and_preserves_hitl(mixed, instalaciones, approved):
    _, rag_calls = mixed
    model_calls = []

    def generate(**kwargs):
        model_calls.append(kwargs)
        view = json.loads(kwargs["messages"][1].content)
        route = ("FINISH" if view["plan_listo"] else "sintetizar"
                 if "instalaciones" in view["resultados_disponibles"] else "instalaciones")
        return SimpleNamespace(text=json.dumps({"ruta": route, "motivo": "Modelo doble"}), tool_calls=[])

    provider = crear_proveedor_rutas(
        adapter=SimpleNamespace(generate=generate), message_factory=SimpleNamespace)
    service = crear_servicio_real(route_provider=provider)
    assert model_calls == rag_calls == instalaciones[1] == []
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Catálogo municipal", tid)
    assert set(pending["specialist_results"]) == {"instalaciones"}
    assert pending["specialist_results"]["instalaciones"].status == "ok"
    assert len(model_calls) == 3 and len(instalaciones[1]) == 1 and rag_calls == []
    decisions = [line for line in pending["debug_trace"] if ": supervisor ->" in line]
    assert decisions == [
        f"iter {i}: supervisor -> {role}; origen=proveedor"
        for i, role in enumerate(("instalaciones", "sintetizar", "FINISH"), 1)
    ]
    assert pending["pendiente_hitl"] and pending["approved"] is None and not pending["done"]
    final = service.resolver_plan(tid, approved, plan_id=pending["plan_id"])
    assert final["thread_id"] == tid and final["plan_id"] == pending["plan_id"]
    assert final["done"] is approved and not final["pendiente_hitl"]
    assert len(model_calls) == 3 and len(instalaciones[1]) == 1 and rag_calls == []


def test_injected_provider_failure_uses_rules_fallback_in_real_runtime(mixed, instalaciones):
    _, rag_calls = mixed
    model_calls = []

    def generate(**kwargs):
        model_calls.append(kwargs)
        raise TimeoutError("Fallo inmediato del modelo doble")

    provider = crear_proveedor_rutas(
        adapter=SimpleNamespace(generate=generate), message_factory=SimpleNamespace)
    service = crear_servicio_real(route_provider=provider)
    assert model_calls == rag_calls == instalaciones[1] == []
    pending = service.procesar_turno("Catálogo municipal", service.nueva_conversacion())
    assert len(model_calls) == 4 and len(rag_calls) == len(instalaciones[1]) == 1
    assert set(pending["specialist_results"]) == {"documental", "instalaciones"}
    decisions = [line for line in pending["debug_trace"] if ": supervisor ->" in line]
    assert all("origen=fallback; causa=excepcion_proveedor" in line for line in decisions)
    assert pending["pendiente_hitl"] and pending["approved"] is None and not pending["done"]


@pytest.mark.parametrize("approved", [True, False])
def test_mixed_lifecycle_and_preserved_envelope(mixed, instalaciones, approved):
    service, calls = mixed
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Consulta sintética de prueba", tid)
    result = pending["specialist_results"]["documental"]
    assert result.answer == result.data["resultado"] == "Respuesta simulada identificada"
    assert result.data["fuentes"] == [e.source for e in result.evidence] == ["test://documento"]
    assert result.data["eventos"][0]["tool"] == "rag"
    assert result.data["request_id"]
    assert result.data["limitaciones"] == result.data["errores"] == []
    observation, external_calls = instalaciones
    installed = pending["specialist_results"]["instalaciones"]
    assert installed.status == "ok" and "Centro de prueba" in installed.answer
    assert installed.answer in pending["final_answer"]
    assert installed.evidence[0].source == "test://centro"
    assert installed.evidence[0].metadata == {"pk": "114782", "distrito": "Distrito de prueba"}
    for key in ("origen", "fuente", "fecha_consulta", "fecha_captura_fallback", "advertencias"):
        assert installed.data[key] == observation[key]
    assert "test://centro" in pending["final_answer"]
    assert observation["fecha_consulta"] in pending["final_answer"]
    assert pending["pendiente_hitl"] and pending["approved"] is None
    assert pending["done"] is False
    # Verifica la conexión de los nodos al supervisor principal: el componente
    # documental devuelve el control antes de instalaciones, síntesis y FINISH.
    decisions = [line for line in pending["debug_trace"] if ": supervisor ->" in line]
    assert decisions == [
        f"iter {i}: supervisor -> {role}; origen=reglas"
        for i, role in enumerate(("documental", "instalaciones", "sintetizar", "FINISH"), 1)
    ]
    assert not any("HITL ->" in line for line in pending["debug_trace"])
    with pytest.raises(ValueError, match="HITL_PENDING"):
        service.procesar_turno("No debe llamar a RAG", tid)
    final = service.resolver_plan(tid, approved, plan_id=pending["plan_id"])
    assert final["thread_id"] == tid and final["plan_id"] == pending["plan_id"]
    assert final["done"] is approved and not final["pendiente_hitl"]
    event = "HITL -> plan " + ("aprobado" if approved else "rechazado")
    assert final["debug_trace"].count(event) == 1
    before = deepcopy(final)
    assert service.resolver_plan(tid, approved, plan_id=pending["plan_id"]) == before
    assert len(calls) == 1
    assert external_calls == [{"modo": "catalogo", "centro_id": None}]
    second = service.procesar_turno("Segundo pedido sintético", tid)
    assert second["plan_id"] != pending["plan_id"]
    assert second["specialist_results"]["documental"].data["request_id"] != result.data["request_id"]
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        service.resolver_plan(tid, True, plan_id=pending["plan_id"])
    other = service.nueva_conversacion()
    assert service.consultar_estado(other)["specialist_results"] == {}
    assert service.consultar_estado(other)["debug_trace"] == ["inicio de pedido"]
    assert len(calls) == 2
    assert len(external_calls) == 2


@pytest.mark.parametrize("observation,status,text", [
    ({"ok": False, "resultado": "", "fuentes": [], "abstained": False,
      "error": "Fallo RAG de prueba"}, "error", "Fallo RAG de prueba"),
    ({"ok": True, "resultado": "", "fuentes": [], "abstained": True,
      "error": None}, "abstained", "abstención"),
])
def test_mixed_errors_are_presented_honestly(monkeypatch, instalaciones, observation, status, text):
    import agentes.grafo_documental as gd
    import agentes.nodes.documental as nd
    monkeypatch.setattr(gd, "_grafo", None)
    monkeypatch.setitem(nd.REGISTRY, "rag", lambda consulta: observation)
    service = crear_servicio_real()
    state = service.procesar_turno("Prueba de error", service.nueva_conversacion())
    assert state["specialist_results"]["documental"].status == status
    assert text in state["final_answer"]
    assert state["pendiente_hitl"]


@pytest.mark.parametrize("origin", ["api", "fallback"])
def test_installation_notice_provenance_survives_synthesis(mixed, instalaciones, origin):
    observation, calls = instalaciones
    observation.update(
        modo="avisos", origen=origin,
        fecha_captura_fallback="2026-10-19T10:00:00+02:00" if origin == "fallback" else None,
        advertencias=["Captura histórica de prueba"] if origin == "fallback" else [],
        datos=[{"centro_id": "114782", "texto_aviso": "Cierre de prueba",
                "aviso_detectado": True, "url_ficha": "test://aviso", "origen": origin}],
    )
    service, _ = mixed
    state = service.procesar_turno("Avisos del centro 114782", service.nueva_conversacion())
    result = state["specialist_results"]["instalaciones"]
    assert calls == [{"modo": "avisos", "centro_id": "114782"}]
    assert result.status == "ok" and "Cierre de prueba" in result.answer
    assert result.data["origen"] == result.evidence[0].metadata["origen"] == origin
    assert result.evidence[0].source == "test://aviso"
    assert result.data["fecha_captura_fallback"] == observation["fecha_captura_fallback"]
    assert result.data["advertencias"] == observation["advertencias"]
    assert result.answer in state["final_answer"] and "test://aviso" in state["final_answer"]
    assert ("Fallback histórico: no acredita condiciones actuales." in state["final_answer"]) is (origin == "fallback")
    if origin == "fallback":
        assert observation["fecha_captura_fallback"] in state["final_answer"]
        assert observation["advertencias"][0] in state["final_answer"]


@pytest.mark.parametrize("status", ["error", "abstained"])
def test_installation_failure_is_not_confirmed_and_keeps_documental(mixed, instalaciones, status):
    observation, _ = instalaciones
    observation.update(ok=status != "error", datos=[],
                       error="Fallo externo de prueba" if status == "error" else None)
    service, _ = mixed
    state = service.procesar_turno("Catálogo de centros", service.nueva_conversacion())
    result = state["specialist_results"]["instalaciones"]
    assert result.status == status
    assert f"instalaciones: {'error' if status == 'error' else 'abstención'}" in state["final_answer"]
    assert "instalaciones: resultado disponible" not in state["final_answer"]
    if status == "error":
        assert result.error == "Fallo externo de prueba"
        assert result.error in state["final_answer"]
    assert state["specialist_results"]["documental"].answer == "Respuesta simulada identificada"
    assert state["pendiente_hitl"] and state["approved"] is None and state["done"] is False


def test_real_creation_failure_never_falls_back_to_demo(monkeypatch):
    import agentes.grafo_documental as gd
    import agentes.demo as demo

    def fail():
        raise RuntimeError("Fallo real de prueba")

    monkeypatch.setattr(gd, "obtener_grafo_documental", fail)
    monkeypatch.setattr(demo, "crear_servicio_demo", lambda: pytest.fail("Fallback prohibido"))
    with pytest.raises(RuntimeError, match="Fallo real de prueba"):
        crear_servicio(modo="real")
    with pytest.raises(ValueError, match="modo"):
        crear_servicio(modo="mixto")
