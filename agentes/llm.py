"""Adaptador del proveedor de modelos y prompts por responsabilidad.

Operaciones previstas: proponer ruta, proponer llamadas de tools, sintetizar
resultados y analizar imagen. El modelo propone; Python valida y ejecuta.
Entradas: pedido, contexto autorizado, historial acotado, herramientas
permitidas y resultados previos. Salidas: propuestas estructuradas validables.
Permitir inyección de un doble de prueba y manejar fallos sin inventar datos.
Definir timeouts y reintentos acotados. Para asyncio, decidir si usar cliente
nativo async o adaptar llamadas bloqueantes mediante to_thread.
"""
