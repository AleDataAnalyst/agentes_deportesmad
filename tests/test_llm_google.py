"""Historial de herramientas con tipos del SDK instalado y cliente sin red."""

from types import SimpleNamespace

import pytest
from google.genai import types

from agentes import llm
from agentes.especialista_llm import Herramienta, ejecutar_especialista
from agentes.llm_google import GoogleAdapter


@pytest.mark.parametrize("bucle", ["rag", "especialista"])
def test_google_segunda_llamada_con_resultado_de_herramienta(monkeypatch, bucle):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        "agentes.llm_google.genai.Client",
        lambda **_: pytest.fail("Debe usar el cliente doble sin credenciales ni red"),
    )
    argumentos = {"consulta": "precio del abono"}
    resultado = {
        "respuesta": "Abono: 45 €", "fuentes": ["tarifas.pdf"],
        "abstained": False, "error": None,
    }
    ejecuciones = []

    def herramienta(**args):
        ejecuciones.append(args)
        return resultado

    class ClienteDoble:
        def __init__(self):
            self.models = self
            self.llamadas = []

        def generate_content(self, **kwargs):
            self.llamadas.append(kwargs)
            assert len(self.llamadas) <= 2
            if len(self.llamadas) == 1:
                return SimpleNamespace(
                    text="",
                    candidates=[types.Candidate(content=types.Content(
                        role="model",
                        parts=[types.Part(function_call=types.FunctionCall(
                            name="rag_preguntar", args=argumentos,
                        ))],
                    ))],
                )
            return SimpleNamespace(text="Abono: 45 € [tarifas.pdf]", candidates=[])

    cliente = ClienteDoble()
    adapter = GoogleAdapter(client=cliente, model="modelo-doble")
    if bucle == "rag":
        monkeypatch.setitem(llm.TOOL_REGISTRY, "rag_preguntar", herramienta)
        texto, traza = llm.run_tool_rag("¿Cuánto cuesta el abono?", max_steps=2, adapter=adapter)
        assert texto == "Abono: 45 € [tarifas.pdf]"
        assert traza[0]["args"] == argumentos
    else:
        traza = ejecutar_especialista(
            prompt_sistema="Consulta las tarifas.", mensaje="¿Cuánto cuesta el abono?",
            herramientas=[Herramienta(
                "rag_preguntar", "Consulta tarifas.",
                {"type": "object", "properties": {"consulta": {"type": "string"}}},
                herramienta,
            )],
            max_steps=2, adapter=adapter,
        )
        assert traza[0]["status"] == "ok"
        assert traza[0]["resultado"] == resultado

    assert ejecuciones == [argumentos]
    assert len(cliente.llamadas) == 2
    primera, segunda = cliente.llamadas
    assert [c.role for c in primera["contents"]] == ["user"]
    assert primera["contents"][0].parts[0].text == "¿Cuánto cuesta el abono?"
    assert segunda["config"].system_instruction == primera["config"].system_instruction
    assert [c.role for c in segunda["contents"]] == ["user", "model", "user"]
    llamada = segunda["contents"][1].parts[0].function_call
    assert llamada.name == "rag_preguntar"
    assert llamada.args == argumentos
    respuesta = segunda["contents"][2].parts[0].function_response
    assert respuesta.name == "rag_preguntar"
    assert respuesta.response == resultado
