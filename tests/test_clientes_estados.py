"""Los cuatro ejemplos del especialista documental llegan a la interfaz con la forma esperada."""

import json
from pathlib import Path

import pytest

from agentes.documental_adapter import crear_adaptador_documental
from clientes.estados import avisos_de_estado, vista_resultado

FIXTURES = Path(__file__).parent / "fixtures"


def _resultado(nombre: str):
    """Pasa el ejemplo por el adaptador real, como llega a la interfaz."""
    texto = (FIXTURES / f"{nombre}.json").read_text(encoding="utf-8")

    def ejecutar(entrada):
        return json.loads(texto.replace("{{request_id}}", entrada["request_id"]))

    nodo = crear_adaptador_documental(ejecutar_documental=ejecutar)
    return nodo({"user_message": "consulta de prueba"})["specialist_results"]["documental"]


def test_respuesta_con_fuentes():
    vista = vista_resultado(_resultado("rag_ok"))
    assert vista["tipo"] == "respuesta"
    assert vista["fuentes"] == ["data/corpus/abonos.csv", "data/corpus/normativa_instalaciones.pdf"]
    assert vista["limitaciones"] == []
    assert vista["error"] is None
    assert "45 euros" in vista["texto"]


def test_abstencion_sin_fuentes_y_con_limitacion():
    vista = vista_resultado(_resultado("rag_abstencion"))
    assert vista["tipo"] == "abstencion"
    assert vista["fuentes"] == []
    assert vista["texto"] == ""
    assert len(vista["limitaciones"]) == 1


def test_error_con_mensaje_y_sin_respuesta():
    vista = vista_resultado(_resultado("vision_error"))
    assert vista["tipo"] == "error"
    assert "no ha podido procesar la imagen" in vista["error"]
    assert vista["texto"] == ""
    assert len(vista["limitaciones"]) == 1


def test_respuesta_con_limitaciones():
    vista = vista_resultado(_resultado("vision_ok"))
    assert vista["tipo"] == "respuesta"
    assert vista["fuentes"] == ["assets/imagen_demo.jpg"]
    assert len(vista["limitaciones"]) == 1
    assert "vigencia" in vista["limitaciones"][0]


@pytest.mark.parametrize("data,esperado", [
    ({"advertencias": ["a"], "warnings": ["a", "b"]}, ["a", "b"]),
    ({"limitaciones": "una sola"}, ["una sola"]),
    ({}, []),
])
def test_limitaciones_de_varias_claves_sin_repetir(data, esperado):
    resultado = {"status": "ok", "answer": "x", "data": data}
    assert vista_resultado(resultado)["limitaciones"] == esperado


def _estado(nombre: str, rol: str = "documental") -> dict:
    return {"specialist_results": {rol: _resultado(nombre)}}


def test_avisos_de_los_cuatro_ejemplos():
    assert avisos_de_estado(_estado("rag_ok")) == []

    (nivel, texto), = avisos_de_estado(_estado("rag_abstencion"))
    assert nivel == "info" and "No se han recuperado fragmentos" in texto

    niveles = [n for n, _ in avisos_de_estado(_estado("vision_error"))]
    assert niveles == ["error", "warning"]

    (nivel, texto), = avisos_de_estado(_estado("vision_ok"))
    assert nivel == "warning" and "vigencia" in texto


def _app_avisos():
    import clientes.streamlit_app as m

    class Falso:
        def nueva_conversacion(self):
            return "deportes-abc123"

        def procesar_turno(self, mensaje, thread_id):
            return {
                "thread_id": thread_id, "pendiente_hitl": False, "done": False,
                "final_answer": "Respuesta parcial", "iterations": 1,
                "specialist_results": {
                    "documental": {"status": "abstained", "answer": "", "evidence": [],
                                   "error": None, "data": {"limitaciones": ["Sin evidencia"]}},
                    "instalaciones": {"status": "error", "answer": "", "evidence": [],
                                      "error": "api_key=secreto-1234567890abc", "data": {}},
                },
            }

    m.crear_servicio = lambda modo="real": Falso()
    m.validar_estado = lambda e, t: e
    m.render()


def test_streamlit_pinta_abstencion_y_error_sin_secretos():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app_avisos, default_timeout=20).run()
    at.chat_input[0].set_value("hola").run()
    assert not at.exception
    assert any("documental" in i.value and "Sin evidencia" in i.value for i in at.info)
    errores = [e.value for e in at.error]
    assert any("instalaciones" in e for e in errores)
    assert all("secreto-1234567890abc" not in e for e in errores)
