"""Utilidades deterministas, sin modelo, RAG ni consulta HTTP.

Tools previstas: hora_actual, comparar candidatos por criterios explícitos,
detectar conflictos con fechas ISO 8601 zonificadas y preparar reporte borrador.
Entradas y salidas siguen contratos de contracts.py. Validar duración, zona
horaria, límites y campos necesarios. Información desconocida se conserva como tal.
Preparar_reporte no envía nada; comparación no calcula rutas ni disponibilidad.
"""
