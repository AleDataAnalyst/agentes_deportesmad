"""Adaptador del proveedor de modelos y prompts por responsabilidad.

Operaciones previstas: proponer ruta, proponer llamadas de tools, sintetizar
resultados y analizar imagen. El modelo propone; Python valida y ejecuta.
Entradas: pedido, contexto autorizado, historial acotado, herramientas
permitidas y resultados previos. Salidas: propuestas estructuradas validables.
Permitir inyección de un doble de prueba y manejar fallos sin inventar datos.
Definir timeouts y reintentos acotados. Para asyncio, decidir si usar cliente
nativo async o adaptar llamadas bloqueantes mediante to_thread.
"""
"""Adaptador del proveedor de modelos y prompts por responsabilidad.

El modelo propone llamadas a tools; Python valida la allowlist y las ejecuta.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from google import genai
from google.genai import types

from agentes import config
from agentes.tools import rag_preguntar


INSTRUCCIONES_TOOLS = """
Eres un asistente técnico. Responde en español.

Puedes usar la herramienta `rag_preguntar` para consultar la base de conocimiento RAG.
Si la pregunta depende de documentos internos, llama a la herramienta antes de responder.
No inventes fuentes, datos ni respuestas. Si la herramienta indica abstención o error,
explica brevemente que no hay información suficiente.
"""

TOOL_DECLARATIONS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="rag_preguntar",
                description=(
                    "Consulta la base de conocimiento RAG y devuelve respuesta, "
                    "fuentes, indicador de abstención y error si lo hubiera."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "consulta": {
                            "type": "string",
                            "description": "Pregunta del usuario en lenguaje natural.",
                        },
                        "con_diagnostico": {
                            "type": "boolean",
                            "description": "Incluye campos adicionales de depuración.",
                        },
                    },
                    "required": ["consulta"],
                },
            )
        ]
    )
]

TOOL_REGISTRY: dict[str, Callable[..., Any]] = {
    "rag_preguntar": rag_preguntar,
}


def _preview(valor: Any, limite: int = 500) -> str:
    """Convierte el resultado de una tool en una cadena acotada para la traza."""
    if isinstance(valor, str):
        texto = valor
    else:
        try:
            texto = json.dumps(valor, ensure_ascii=False, default=str)
        except Exception:
            texto = str(valor)
    return texto[:limite]


def _gen_config_tools() -> types.GenerateContentConfig:
    """Configura la respuesta con acceso restringido a las tools registradas."""
    return types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=2048,
        tools=TOOL_DECLARATIONS,
    )


def _ejecutar_tool(nombre: str, args: dict[str, Any]) -> Any:
    """Ejecuta una tool autorizada; nunca propaga excepciones hacia el modelo."""
    funcion = TOOL_REGISTRY[nombre]
    try:
        return funcion(**args)
    except TypeError as exc:
        return {"error": f"Argumentos inválidos para '{nombre}': {exc}"}
    except Exception as exc:
        return {"error": f"Error ejecutando '{nombre}': {exc}"}


def run_tool_rag(
    mensaje_usuario: str,
    max_steps: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Ejecuta el bucle modelo -> tools -> modelo hasta obtener texto final.

    Devuelve una tupla con la respuesta final y una traza de las tools usadas.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GOOGLE_API_KEY")

    limit = max_steps if max_steps is not None else config.MAX_STEPS_DEFAULT
    client = genai.Client(api_key=api_key)
    gen_config = _gen_config_tools()
    traza: list[dict[str, Any]] = []

    historial: list[types.Content] = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=INSTRUCCIONES_TOOLS + "\n\nMENSAJE:\n"