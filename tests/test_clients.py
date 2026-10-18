"""Pruebas previstas de contrato común en CLI y Streamlit.

Ejercitar pedido, pausa, aprobar, rechazar, nueva conversación y debug.
No asumir que una pantalla visible acredita el comportamiento del grafo.
"""

import pytest
from pathlib import Path

from clientes.cli import main


@pytest.fixture
def client_service(monkeypatch):
    """Montaje mixto explícito: orquestación real y tool documental doble."""
    import agentes.grafo_documental as gd
    import agentes.nodes.documental as nd
    from agentes.runtime import crear_servicio_real

    monkeypatch.setattr(gd, "_grafo", None)
    monkeypatch.setitem(nd.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "Respuesta simulada del cliente",
        "fuentes": ["test://cliente"], "abstained": False, "error": None})
    return crear_servicio_real()


def test_cli_uses_same_service_and_blocks_pending_orders(monkeypatch, capsys, client_service):
    import clientes.cli as cli
    constructions = []

    def factory(**kwargs):
        constructions.append(kwargs)
        return client_service

    monkeypatch.setattr(cli, "crear_servicio", factory)
    commands = iter(("Consulta sintética", "Bloqueado", "/aprobar", "Otra consulta",
                     "/rechazar", "/nueva", "/salir"))
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Plan pendiente" in output
    assert "test://cliente" in output
    assert "Instalaciones no disponibles" in output
    assert "Plan informativo aprobado" in output
    assert "Propuesta rechazada" in output
    assert constructions == [{"modo": "real"}]


def test_streamlit_session_hitl_and_isolation(monkeypatch, client_service):
    from streamlit.testing.v1 import AppTest
    import clientes.streamlit_app as ui

    monkeypatch.setattr(ui, "crear_servicio", lambda **kwargs: client_service)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    original_thread = app.session_state.thread_id
    assert app.session_state.service is client_service
    app.chat_input[0].set_value("Consulta sintética UI").run()
    assert not app.exception
    assert app.chat_input[0].disabled
    plan_id = app.session_state.estado["plan_id"]
    assert plan_id and app.session_state.estado["pendiente_hitl"]
    assert any("test://cliente" in m.value for m in app.markdown)
    # Orden de botones: nueva conversación, aprobar, rechazar.
    next(b for b in app.button if "Aprobar" in b.label).click().run()
    assert not app.exception
    assert not app.chat_input[0].disabled
    assert app.session_state.estado["done"]
    app.chat_input[0].set_value("Segundo pedido UI").run()
    assert app.session_state.estado["plan_id"] != plan_id
    next(b for b in app.button if "Rechazar" in b.label).click().run()
    assert not app.exception
    assert not app.session_state.estado["pendiente_hitl"]
    next(b for b in app.button if "Nueva conversación" in b.label).click().run()
    assert not app.exception
    assert app.session_state.thread_id != original_thread
    assert app.session_state.messages == [] and app.session_state.estado is None
    assert app.session_state.service is client_service


def test_streamlit_surfaces_error_without_fabricating_answer(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import clientes.streamlit_app as ui

    def fail(**kwargs):
        raise RuntimeError("Dependencia real ausente (prueba)")

    monkeypatch.setattr(ui, "crear_servicio", fail)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert any("Dependencia real ausente" in error.value for error in app.error)
    assert len(app.chat_message) == 0
