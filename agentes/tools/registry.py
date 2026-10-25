"""Registro de tools, allowlist por rol y ejecución controlada.

Entradas: rol, nombre, argumentos, presupuesto y contexto autorizado.
Salidas: ToolResult validado y datos de traza acotados.
Validar permisos y argumentos antes de ejecutar; propuestas inválidas consumen
presupuesto. Acotar pasos, detectar repeticiones y tratar fallos explícitamente.
No evaluar código, funciones ni URLs arbitrarias propuestas por el modelo.
Prever adaptación async de herramientas bloqueantes; presupuesto independiente
por especialista. No incluir lógica de Streamlit ni prompts de síntesis.
"""
