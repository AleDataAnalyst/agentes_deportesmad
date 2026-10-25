"""Pruebas offline para la integración del supervisor LLM."""

import subprocess
import sys
import pytest


def test_importar_tipos_llm_no_carga_rag():
    codigo = """
import sys
from agentes.llm import LlmMessage, LlmResponse, LlmAdapter

assert "rag" not in sys.modules
assert "chromadb" not in sys.modules
"""

    resultado = subprocess.run(
        [sys.executable, "-B", "-c", codigo],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert resultado.returncode == 0, resultado.stderr


def test_google_supervisor_sin_tools_y_con_instruccion_system():
    from agentes.llm import LlmMessage
    from agentes.llm_google import GoogleAdapter

    class ClienteSimulado:
        def __init__(self):
            self.llamadas = []
            self.models = self

        def generate_content(self, **kwargs):
            self.llamadas.append(kwargs)

            class Respuesta:
                candidates = []
                text = ""

            return Respuesta()

    cliente = ClienteSimulado()
    adapter = GoogleAdapter(
        client=cliente,
        model="modelo-simulado",
    )

    adapter.generate(
        messages=[
            LlmMessage(
                role="system",
                content="Selecciona únicamente una ruta válida.",
            ),
            LlmMessage(
                role="user",
                content='{"user_message": "Quiero reservar una pista"}',
            ),
        ],
        tools=[],
        temperature=0,
        max_output_tokens=256,
        timeout=30,
    )

    assert len(cliente.llamadas) == 1

    llamada = cliente.llamadas[0]
    configuracion = llamada["config"]

    assert not configuracion.tools
    assert "Selecciona únicamente una ruta válida." in str(
        configuracion.system_instruction
    )

    assert len(llamada["contents"]) == 1
    assert llamada["contents"][0].role == "user"


def test_google_supervisor_configura_timeout_en_milisegundos():
    from agentes.llm import LlmMessage
    from agentes.llm_google import GoogleAdapter

    class ClienteSimulado:
        def __init__(self):
            self.models = self
            self.llamada = None

        def generate_content(self, **kwargs):
            self.llamada = kwargs

            class Respuesta:
                candidates = []
                text = ""

            return Respuesta()

    cliente = ClienteSimulado()
    adapter = GoogleAdapter(
        client=cliente,
        model="modelo-simulado",
    )

    adapter.generate(
        messages=[LlmMessage(role="user", content="Prueba")],
        tools=[],
        temperature=0,
        max_output_tokens=256,
        timeout=30,
    )

    config = cliente.llamada["config"]

    assert config.http_options is not None
    assert config.http_options.timeout == 30_000


def test_crear_proveedor_supervisor_no_ejecuta_inferencia():
    from agentes.llm import LlmResponse
    from agentes.supervisor_llm_real import crear_proveedor_supervisor_real

    class AdapterSimulado:
        def __init__(self):
            self.llamadas = []

        def generate(self, messages, tools, *, temperature, max_output_tokens, timeout):
            self.llamadas.append({
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "timeout": timeout,
            })
            return LlmResponse(text='{"ruta": "finalizar", "motivo": "Prueba"}')

    adapter = AdapterSimulado()

    proveedor = crear_proveedor_supervisor_real(
        adapter=adapter,
        timeout=30,
    )

    assert callable(proveedor)
    assert adapter.llamadas == []


def test_factoría_supervisor_transmite_decision_y_parametros():
    from agentes.llm import LlmResponse
    from agentes.state import initial_state
    from agentes.supervisor_llm_real import crear_proveedor_supervisor_real

    class AdapterSimulado:
        def __init__(self):
            self.llamadas = []

        def generate(
            self, messages, tools, *,
            temperature, max_output_tokens, timeout,
        ):
            self.llamadas.append({
                "messages": messages,
                "tools": tools,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
                "timeout": timeout,
            })
            return LlmResponse(
                text='{"ruta": "documental", "motivo": "Consultar normativa"}'
            )

    adapter = AdapterSimulado()
    proveedor = crear_proveedor_supervisor_real(
        adapter=adapter,
        temperature=0,
        max_output_tokens=256,
        timeout=30,
    )

    decision = proveedor(initial_state("¿Qué dice la normativa?"))

    assert decision.specialist == "documental"
    assert len(adapter.llamadas) == 1

    llamada = adapter.llamadas[0]
    assert llamada["tools"] == []
    assert llamada["temperature"] == 0
    assert llamada["max_output_tokens"] == 256
    assert llamada["timeout"] == 30
    assert [m.role for m in llamada["messages"]] == ["system", "user"]


@pytest.mark.parametrize("name,value", [
    ("SUPERVISOR_MODE", ""), ("SUPERVISOR_MODE", "otro"),
    ("SUPERVISOR_PROVIDER", "huggingface"), ("SUPERVISOR_PROVIDER", ""),
    ("SUPERVISOR_MODEL", " "), ("GOOGLE_API_KEY", ""),
    ("SUPERVISOR_TIMEOUT", "0"), ("SUPERVISOR_TIMEOUT", "241"),
    ("SUPERVISOR_TIMEOUT", "1.5"), ("SUPERVISOR_MAX_OUTPUT_TOKENS", "0"),
    ("SUPERVISOR_MAX_OUTPUT_TOKENS", "4097"),
    ("SUPERVISOR_TEMPERATURE", "nan"), ("SUPERVISOR_TEMPERATURE", "inf"),
    ("SUPERVISOR_TEMPERATURE", "-1"), ("SUPERVISOR_TEMPERATURE", "2.1"),
])
def test_invalid_config_fails_before_adapter(monkeypatch, name, value):
    from agentes.supervisor_llm_real import crear_proveedor_configurado
    import agentes.llm_google as google
    for key, val in {"SUPERVISOR_MODE": "llm", "SUPERVISOR_PROVIDER": "google",
                     "SUPERVISOR_MODEL": "modelo-doble", "GOOGLE_API_KEY": "doble"}.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(google, "GoogleAdapter", lambda **kw: pytest.fail("No debe construir"))
    with pytest.raises(ValueError, match=name):
        crear_proveedor_configurado()


@pytest.mark.parametrize("temperature,tokens,timeout", [("0", "1", "1"), ("2", "4096", "240")])
def test_config_limits_and_rag_independence(monkeypatch, temperature, tokens, timeout):
    from agentes import config
    from agentes.llm import LlmResponse
    import agentes.llm_ollama as ollama
    from agentes.supervisor_llm_real import crear_proveedor_configurado
    from agentes.state import initial_state
    before = (config.GEN_PROVIDER, config.GEN_MODEL)
    monkeypatch.setenv("SUPERVISOR_MODE", "llm")
    monkeypatch.setenv("SUPERVISOR_PROVIDER", "ollama")
    monkeypatch.setenv("SUPERVISOR_MODEL", "modelo-doble")
    for key, value in {"TEMPERATURE": temperature, "MAX_OUTPUT_TOKENS": tokens, "TIMEOUT": timeout}.items():
        monkeypatch.setenv("SUPERVISOR_" + key, value)
    calls = []
    class Adapter:
        def __init__(self, **kw):
            assert kw == {"model": "modelo-doble"}
        def generate(self, **kw):
            calls.append(kw)
            return LlmResponse(text='{"ruta":"documental","motivo":"Doble"}')
    monkeypatch.setattr(ollama, "OllamaAdapter", Adapter)
    provider = crear_proveedor_configurado()
    assert not calls
    provider(initial_state("Consulta"))
    assert calls[0]["temperature"] == float(temperature)
    assert calls[0]["max_output_tokens"] == int(tokens)
    assert calls[0]["timeout"] == int(timeout)
    assert (config.GEN_PROVIDER, config.GEN_MODEL) == before


def test_google_timeout_reaches_http_transport():
    """SDK real con transporte doble: comprueba opciones, no latencia real."""
    import httpx
    from google import genai
    from google.genai import types
    from agentes.llm import LlmMessage
    from agentes.llm_google import GoogleAdapter
    requests = []
    def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {
            "role": "model", "parts": [{"text": "doble"}]}}]})
    client = genai.Client(api_key="clave-doble", http_options=types.HttpOptions(
        client_args={"transport": httpx.MockTransport(transport)}))
    try:
        result = GoogleAdapter(client=client, model="modelo-doble").generate(
            messages=[LlmMessage(role="user", content="prueba")], tools=[],
            temperature=0, max_output_tokens=10, timeout=7)
        assert result.text == "doble"
        assert len(requests) == 1
        assert requests[0].extensions["timeout"] == {
            "connect": 7.0, "read": 7.0, "write": 7.0, "pool": 7.0}
    finally:
        client.close()
