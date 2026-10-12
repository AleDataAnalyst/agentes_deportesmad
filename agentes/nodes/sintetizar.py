"""Síntesis de evidencias y preparación del plan para HITL.

Entradas: pedido y resultados de especialistas del request_id vigente.
Salidas: answer, plan, plan_id, sources, limitations y fase awaiting_approval.
Conservar procedencia, abstenciones, errores y uso de fallback fechado.
Validar referencias; no inventar datos ausentes. Preparar una alternativa
basada en resultados cuando falle el modelo. done permanece falso.
Dependencias: modelo, contratos y resultados; no ejecuta reservas ni envíos.
"""
