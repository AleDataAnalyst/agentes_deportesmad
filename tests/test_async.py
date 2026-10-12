"""Pruebas previstas de solapamiento y unión de resultados concurrentes.

Usar barrera o señal para acreditar que ambas ramas están activas, no solo
medir duración. Verificar ausencia de sobrescrituras y protección del mismo thread_id.
"""
