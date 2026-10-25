"""Pruebas offline para la integración del supervisor LLM."""

import subprocess
import sys


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

    assert decision.ruta == "documental"
    assert len(adapter.llamadas) == 1

    llamada = adapter.llamadas[0]
    assert llamada["tools"] == []
    assert llamada["temperature"] == 0
    assert llamada["max_output_tokens"] == 256
    assert llamada["timeout"] == 30
    assert [m.role for m in llamada["messages"]] == ["system", "user"]
