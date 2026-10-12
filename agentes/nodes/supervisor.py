"""Supervisor de enrutado y finalización de la fase de consultas.

Entradas: pedido, roles pendientes, resultados actuales y contadores.
Salidas: siguiente rol o síntesis, razón de ruta, contador y evento de traza.
Validar propuesta del modelo y aplicar fallback determinista en Python.
No repetir indefinidamente especialistas ni permitir nombres desconocidos.
Puede autorizar consultas independientes en paralelo; no establece done por sí solo.
Dependencias: modelo, estado, contratos y límites de configuración.
"""
