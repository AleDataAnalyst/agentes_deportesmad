"""Especialistas con LLM: allowlist, max_steps, traza y caída a reglas."""

import re

import pytest

import agentes.especialista_llm as esp
import agentes.nodes.documental as nod
from agentes.especialista_llm import Herramienta, ejecutar_especialista
from agentes.llm import LlmResponse
from agentes.nodes import instalaciones
from agentes.tools.auxiliares import hora_actual


class AdapterFalso:
    """Devuelve las respuestas preparadas en orden y luego texto final."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = 0

    def generate(self, messages, tools, **_):
        self.llamadas += 1
        if self.respuestas:
            return self.respuestas.pop(0)
        return LlmResponse(text="listo")


def _call(nombre, **args):
    return LlmResponse(tool_calls=[{"id": nombre, "name": nombre, "arguments": args}])


def _eco(**args):
    return {"ok": True, "resultado": f"eco {args}", "fuentes": [], "abstained": False, "error": None}


ECO = Herramienta("eco", "Devuelve sus argumentos.", {"type": "object", "properties": {}}, _eco)


def test_tool_fuera_de_la_allowlist_se_bloquea():
    llamadas = ejecutar_especialista(
        prompt_sistema="p", mensaje="m", herramientas=[ECO], max_steps=3,
        adapter=AdapterFalso([_call("borrar_todo")]),
    )
    assert [(ll["tool"], ll["status"]) for ll in llamadas] == [("borrar_todo", "bloqueada")]


def test_max_steps_corta_el_bucle():
    adapter = AdapterFalso([_call("eco", x=i) for i in range(10)])
    llamadas = ejecutar_especialista(
        prompt_sistema="p", mensaje="m", herramientas=[ECO], max_steps=2, adapter=adapter,
    )
    assert len(llamadas) == 2
    assert adapter.llamadas == 2


def test_traza_con_nombre_args_estado_y_preview():
    llamadas = ejecutar_especialista(
        prompt_sistema="p", mensaje="m", herramientas=[ECO], max_steps=2,
        adapter=AdapterFalso([_call("eco", x=1)]),
    )
    assert set(llamadas[0]) >= {"paso", "tool", "args", "status", "preview"}
    assert llamadas[0]["args"] == {"x": 1}
    assert "eco" in llamadas[0]["preview"]


def test_hora_actual_es_iso_con_zona():
    out = hora_actual()
    assert out["ok"] is True
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$", out["resultado"]["iso"],)


def test_documental_llm_usa_la_consulta_propuesta(monkeypatch):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "llm")
    vistas = []

    def rag(consulta):
        vistas.append(consulta)
        return {"ok": True, "resultado": "Abono: 45 €", "fuentes": ["tarifas.pdf"], "abstained": False, "error": None}

    monkeypatch.setitem(nod.REGISTRY, "rag", rag)
    monkeypatch.setattr(esp, "crear_adapter", lambda: AdapterFalso([_call("rag", consulta="precio abono")]))
    out = nod.nodo_documental({"request_id": "r", "pedido": "¿Cuánto cuesta el abono?"})["documental"]
    assert vistas == ["precio abono"]
    assert out["fuentes"] == ["tarifas.pdf"]
    assert out["eventos"][0]["args"] == {"consulta": "precio abono"}


def test_documental_cae_a_reglas_si_falla_el_llm(monkeypatch):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "llm")
    monkeypatch.setitem(nod.REGISTRY, "rag", lambda consulta: {
        "ok": True, "resultado": "r", "fuentes": ["f"], "abstained": False, "error": None})

    def sin_modelo():
        raise RuntimeError("sin modelo")

    monkeypatch.setattr(esp, "crear_adapter", sin_modelo)
    out = nod.nodo_documental({"request_id": "r", "pedido": "consulta"})["documental"]
    assert [e["tool"] for e in out["eventos"]] == ["rag"]
    assert any("planificación LLM no disponible" in x for x in out["limitaciones"])


def test_instalaciones_usa_hora_actual_por_reglas(monkeypatch):
    monkeypatch.delenv("ESPECIALISTAS_MODO", raising=False)
    monkeypatch.setattr(instalaciones, "consultar_instalaciones", lambda **_: {
        "ok": True, "modo": "catalogo", "datos": [], "fuente": "", "origen": "api",
        "fecha_consulta": "2026-10-27T10:00:00+01:00", "fecha_captura_fallback": None,
        "advertencias": [], "error": None, "requiere_aclaracion": False})
    out = instalaciones.nodo_instalaciones({"user_message": "¿qué centros hay abiertos hoy?"})
    assert any("hora_actual" in linea for linea in out["debug_trace"])
    assert "hora_actual" in out["specialist_results"]["instalaciones"].data


def test_modo_invalido(monkeypatch):
    monkeypatch.setenv("ESPECIALISTAS_MODO", "magia")
    with pytest.raises(ValueError):
        esp.modo_especialistas()
