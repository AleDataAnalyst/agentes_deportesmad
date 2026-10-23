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
                
def _validar_argumentos(nombre: str, args: Any) -> dict[str, Any]:
    """Valida que el modelo proponga argumentos tipo diccionario."""
    if not isinstance(args, dict):
        raise ValueError(f"La tool '{nombre}' recibió argumentos no estructurados")
    return args


def _ejecutar_tool(nombre: str, args: dict[str, Any]) -> Any:
    """Ejecuta solo una tool de la allowlist; nunca propaga excepciones al modelo."""
    funcion = TOOL_REGISTRY.get(nombre)
    if funcion is None:
        return {"error": f"Tool no autorizada o desconocida: '{nombre}'"}

    try:
        return funcion(**args)
    except TypeError as exc:
        return {"error": f"Argumentos inválidos para '{nombre}': {exc}"}
    except Exception as exc:
        return {"error": f"Error ejecutando '{nombre}': {exc}"}


def run_tool_rag(
    mensaje_usuario: str,
    max_steps: int | None = None,
    *,
    client: Any | None = None,
    model: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Ejecuta el bucle modelo -> tools -> modelo hasta obtener texto final.

    Devuelve una tupla con la respuesta final y la traza de tools usadas.
    `client` permite inyectar un doble en pruebas; si no, se crea el cliente Gemini.
    """
    if not isinstance(mensaje_usuario, str) or not mensaje_usuario.strip():
        raise ValueError("El mensaje del usuario debe ser texto no vacío")

    limit = max_steps if max_steps is not None else config.MAX_STEPS_DEFAULT
    if type(limit) is not int or limit < 1:
        raise ValueError("max_steps debe ser un entero positivo")

    api_key = os.getenv("GOOGLE_API_KEY")
    if client is None:
        if not api_key:
            raise RuntimeError("Falta GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)

    model_name = model or config.GEN_MODEL
    gen_config = _gen_config_tools()

    historial: list[types.Content] = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=(
                        f"{INSTRUCCIONES_TOOLS}\n\n"
                        f"MENSAJE:\n{mensaje_usuario}"
                    )
                )
            ],
        )
    ]

    traza: list[dict[str, Any]] = []

    for paso in range(limit):
        response = client.models.generate_content(
            model=model_name,
            contents=historial,
            config=gen_config,
        )

        candidato = response.candidates[0] if response.candidates else None
        partes = candidato.content.parts if candidato and candidato.content else []
        llamadas = [
            parte.function_call
            for parte in partes
            if getattr(parte, "function_call", None) is not None
        ]

        # Caso 1: el modelo devuelve texto final.
        texto_final = response.text
        if texto_final and texto_final.strip() and not llamadas:
            return texto_final.strip(), traza

        # Caso 2: el modelo pide una o varias tools.
        if llamadas:
            partes_respuesta: list[types.Part] = []

            for llamada in llamadas:
                nombre = llamada.name
                try:
                    args = _validar_argumentos(nombre, llamada.args)
                except ValueError as exc:
                    resultado = {"error": str(exc)}
                else:
                    resultado = _ejecutar_tool(nombre, args)

                traza.append(
                    {
                        "paso": paso + 1,
                        "tool": nombre,
                        "args": args if isinstance(args, dict) else {},
                        "resultado_preview": _preview(resultado),
                    }
                )

                partes_respuesta.append(
                    types.Part.from_function_response(
                        name=nombre,
                        response=resultado if isinstance(resultado, dict) else {"resultado": resultado},
                    )
                )

            historial.append(
                types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(call)
                        for call in llamadas
                    ],
                )
            )
            historial.append(
                types.Content(
                    role="user",
                    parts=partes_respuesta,
                )
            )
            continue

        # Caso 3: respuesta vacía o bloqueada.
        break

    return (
        "No he podido completar la consulta con la información disponible.",
        traza,
    )