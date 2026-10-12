"""Contratos compartidos y validación de entradas y salidas.

Definir resultado de herramienta: tool, status (ok/abstained/error), data,
evidence, error y meta. Evidencia: id, source, text y fecha si se conoce.
Definir esquemas de argumentos de cada tool y propuestas del modelo.
Definir contrato de cliente: thread_id, request_id, phase, answer, plan,
plan_id, sources, limitations, done, error y trace.
Distinguir falta de evidencia de fallo técnico. Rechazar argumentos extra o
inválidos antes de ejecutar. Los contratos son acuerdos pendientes de revisión.
Dependencias: ninguna lógica de UI ni ejecución de herramientas.
"""
