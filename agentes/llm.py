"""Adaptador del proveedor de modelos y prompts por responsabilidad.

Operaciones previstas: proponer ruta, proponer llamadas de tools, sintetizar
resultados y analizar imagen. El modelo propone; Python valida y ejecuta.
Entradas: pedido, contexto autorizado, historial acotado, herramientas
permitidas y resultados previos. Salidas: propuestas estructuradas validables.
Permitir inyección de un doble de prueba y manejar fallos sin inventar datos.
Definir timeouts y reintentos acotados. Para asyncio, decidir si usar cliente
nativo async o adaptar llamadas bloqueantes mediante to_thread.
"""
import os


for llamada in llamadas:
    nombre = llamada.name
    args = dict(llamada.args or {})

    if nombre not in TOOL_REGISTRY:
        resultado = f"Error: tool '{nombre}' no está permitida."
        status = "blocked"
    else:
        resultado = ejecutar_tool(nombre, args)
        status = "error" if resultado.startswith("Error") else "ok"

    traza.append({
        "step": step,
        "tool": nombre,
        "args": args,
        "status": status,
        "preview": _preview(resultado),
    })
    respuestas_tools.append(
        types.Part.from_function_response(
            name=nombre,
            response={"result": resultado},
        )
    )
    
    def run_tool_rag(
        mensaje_usuario: str,
        max_steps: int | None = None,
) ->     tuple[str, list[dict[str, Any]]]:
        """Fase 1: LLM pide tools; Python ejecuta (allowlist) hasta texto o max_steps.
    
        Flujo por cadastep:
          1) generate_content -> ¿pide function_calls?
          2) Si no -Z devolvemos el texto final + traza.
          3) Si sí _> por cada llamada: allowlist / ejecutar_tool y status ok|error|blocked
          4) Devolvemos los resultados al modelo y repetimos (tope = max_steps).
        """
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Falta GEMINI_API_KEY")
    
        limit = max_steps if max_steps is not None else config.MAX_STEPS_DEFAULT
        client = genai.Client(api_key=api_key)
        gen_config = _gen_config_tools()
        traza = []
    
        # Historial de la conversación modelo↔tools (formato del SDK).
        historial: list[types.Content] = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=INSTRUCCIONES_TOOLS + "\n\nMENSAJE:\n" + mensaje_usuario
                    )
                ],
            )
        ]
    
        for step in range(1, limit + 1):
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=historial,
                config=gen_config,
            )
            # Si no pide tools, ya tenemos la respuesta en texto.
            llamadas = list(response.function_calls or [])
            if not llamadas:
                return (response.text or "").strip(), traza
    
            # Guardamos lo que dijo el modelo (incluye las function_calls).
            historial.append(response.candidates[0].content)
            respuestas_tools: list[types.Part] = []
            for llamada in llamadas:
                nombre = llamada.name
                args = dict(llamada.args or {})
    
                # ← AQUÍ va el TODO: compruebas la tool (allowlist) y la ejecutas.
                if nombre not in TOOL_REGISTRY:
                    resultado = f"Error: tool '{nombre}' no está permitida."
                    status = "blocked"
                else:
                    resultado = ejecutar_tool(nombre, args)
                    status = "error" if resultado.startswith("Error") else "ok"
    
                traza.append(
                    {
                        "step": step,
                        "tool": nombre,
                        "args": args,
                        "status": status,
                        "preview": _preview(resultado),
                    }
                )
                # El SDK espera function_response con el resultado de cada tool.
                respuestas_tools.append(
                    types.Part.from_function_response(
                        name=nombre,
                        response={"result": resultado},
                    )
                )
            historial.append(types.Content(role="tool", parts=respuestas_tools))
    
        return (
            f"He parado por max_steps={limit}. Esto es lo que pude avanzar con las tools.",
            traza,
    )