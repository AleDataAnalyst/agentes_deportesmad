"""Montaje mixto SOLO de pruebas: grafo documental real y tool RAG doble."""
from copy import deepcopy

import pytest

from agentes.runtime import crear_servicio, crear_servicio_real


@pytest.fixture
def mixed(monkeypatch):
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
    return service, calls


def test_public_gate_is_used_without_invoking_it(monkeypatch):
    import agentes.grafo_documental as gd

    class Gate:
        def invoke(self, state):
            pytest.fail("No debe consultarse al construir")

    requested = []

    def factory():
        requested.append(True)
        return Gate()

    monkeypatch.setattr(gd, "obtener_grafo_documental", factory)
    crear_servicio_real()
    assert requested == [True]


@pytest.mark.parametrize("approved", [True, False])
def test_mixed_lifecycle_and_preserved_envelope(mixed, approved):
    service, calls = mixed
    tid = service.nueva_conversacion()
    pending = service.procesar_turno("Consulta sintética de prueba", tid)
    result = pending["specialist_results"]["documental"]
    assert result.answer == result.data["resultado"] == "Respuesta simulada identificada"
    assert result.data["fuentes"] == [e.source for e in result.evidence] == ["test://documento"]
    assert result.data["eventos"][0]["tool"] == "rag"
    assert result.data["request_id"]
    assert result.data["limitaciones"] == result.data["errores"] == []
    unavailable = pending["specialist_results"]["instalaciones"]
    assert unavailable.status == "abstained" and unavailable.data["available"] is False
    assert "Instalaciones no disponibles" in pending["final_answer"]
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
    assert final["done"] is approved and not final["pendiente_hitl"]
    event = "HITL -> plan " + ("aprobado" if approved else "rechazado")
    assert final["debug_trace"].count(event) == 1
    before = deepcopy(final)
    assert service.resolver_plan(tid, approved, plan_id=pending["plan_id"]) == before
    assert len(calls) == 1
    second = service.procesar_turno("Segundo pedido sintético", tid)
    assert second["plan_id"] != pending["plan_id"]
    assert second["specialist_results"]["documental"].data["request_id"] != result.data["request_id"]
    with pytest.raises(ValueError, match="PLAN_NOT_CURRENT"):
        service.resolver_plan(tid, True, plan_id=pending["plan_id"])
    other = service.nueva_conversacion()
    assert service.consultar_estado(other)["specialist_results"] == {}
    assert service.consultar_estado(other)["debug_trace"] == ["inicio de pedido"]
    assert len(calls) == 2


@pytest.mark.parametrize("observation,status,text", [
    ({"ok": False, "resultado": "", "fuentes": [], "abstained": False,
      "error": "Fallo RAG de prueba"}, "error", "Fallo RAG de prueba"),
    ({"ok": True, "resultado": "", "fuentes": [], "abstained": True,
      "error": None}, "abstained", "abstención"),
])
def test_mixed_errors_are_presented_honestly(monkeypatch, observation, status, text):
    import agentes.grafo_documental as gd
    import agentes.nodes.documental as nd
    monkeypatch.setattr(gd, "_grafo", None)
    monkeypatch.setitem(nd.REGISTRY, "rag", lambda consulta: observation)
    service = crear_servicio_real()
    state = service.procesar_turno("Prueba de error", service.nueva_conversacion())
    assert state["specialist_results"]["documental"].status == status
    assert text in state["final_answer"]
    assert state["pendiente_hitl"]


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
