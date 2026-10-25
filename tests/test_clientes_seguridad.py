"""Fallback marcado con origen y plan HITL sin credenciales ni mutar el estado."""

import copy

from agentes.secret_filter import sin_secretos
from clientes.debug import _origen, fuentes_de_estado
from clientes.hitl import mensaje_recuperacion


def test_origen_fallback():
    assert _origen({"data": {"origen": "fallback"}}) == "fallback"


def test_plan_filtrado_sin_mutar():
    estado = {"plan": ["Consultar API con api_key=sk-abcdef1234567890XYZ"]}
    original = copy.deepcopy(estado)
    salida = [sin_secretos(p) for p in estado["plan"]]
    assert "sk-abcdef" not in salida[0]
    assert "OCULT" in salida[0]
    assert estado == original


def test_fuentes_sin_repetir_y_sin_evidencias():
    estado = {"specialist_results": {
        "documental": {"evidence": [{"source": "a.pdf"}, {"source": "a.pdf"}, {"source": "b.pdf"}]},
        "instalaciones": {"evidence": []},
    }}
    assert fuentes_de_estado(estado) == ["a.pdf", "b.pdf"]
    assert fuentes_de_estado({}) == []


def test_mensaje_recuperacion_segun_estado():
    assert mensaje_recuperacion({"pendiente_hitl": True})[0] == "info"
    assert mensaje_recuperacion({"ejecucion_incompleta": True})[0] == "warning"
    assert mensaje_recuperacion({})[0] == "success"


def _app_estado_desconocido():
    """Servicio simulado: tras fallar un turno, consultar_estado falla hasta que se repara."""
    import streamlit as st
    import clientes.streamlit_app as m

    if "falso" not in st.session_state:
        class Falso:
            reparado = False
            llamadas = []

            def nueva_conversacion(self):
                return "deportes-abc123"

            def procesar_turno(self, mensaje, thread_id):
                raise RuntimeError("fallo simulado")

            def consultar_estado(self, thread_id):
                if not Falso.reparado:
                    raise RuntimeError("sin acceso al checkpoint")
                return {"thread_id": thread_id, "pendiente_hitl": True, "plan": ["Paso 1"],
                        "plan_id": "p1", "done": False, "iterations": 1,
                        "specialist_results": {}}

            def resolver_plan(self, thread_id, aprobado, plan_id):
                Falso.llamadas.append(aprobado)
                raise RuntimeError("no debería llamarse")

        st.session_state.falso = Falso
        st.session_state.service = Falso()
        st.session_state.thread_id = "deportes-abc123"
        st.session_state.messages = []
        st.session_state.estado = {"thread_id": "deportes-abc123", "pendiente_hitl": True,
                                   "plan": ["Paso viejo"], "plan_id": "viejo", "done": False,
                                   "iterations": 1, "specialist_results": {}}
        st.session_state.estado_desconocido = True
        m.validar_estado = lambda e, t: e
    m.render()


def test_no_se_decide_hasta_recuperar_el_estado():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_estado_desconocido, default_timeout=20).run()
    etiquetas = [b.label for b in at.sidebar.button]
    assert not any("Aprobar" in e or "Rechazar" in e for e in etiquetas)
    assert any("sin confirmar" in w.value.lower() for w in at.sidebar.warning)
    assert not at.sidebar.markdown or all("Paso viejo" not in m.value for m in at.sidebar.markdown)
    assert at.session_state.falso.llamadas == []

    at.session_state.falso.reparado = True
    at.run()
    etiquetas = [b.label for b in at.sidebar.button]
    assert any("Aprobar" in e for e in etiquetas) and any("Rechazar" in e for e in etiquetas)
