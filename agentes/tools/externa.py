"""Consulta HTTP municipal y fallback local real fechado.

Entradas: filtros soportados y límites; endpoint configurado por desarrollador.
Salidas: catálogo normalizado, procedencia, fecha, uso de fallback y limitaciones.
Validar formato de respuesta y manejar timeout, error HTTP, esquema cambiado
y ausencia de resultados. El fallback debe ser una descarga documentada,
no datos ficticios. Sin fallback válido, devolver error explícito.
Catálogo no acredita plazas libres ni reservas. No dejar elegir URLs al LLM.
"""
