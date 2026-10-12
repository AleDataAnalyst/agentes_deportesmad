"""Resolución de la decisión humana después de la pausa HITL.

Entradas: plan_id vigente y decisión validada por la capa del agente.
Aprobar: marcar plan aprobado y done verdadero. Rechazar: done falso y permitir
un nuevo pedido con reinicio de resultados. Actualizar historial y traza.
No ejecutar sin decisión válida. Aplicar significa cerrar un plan informativo
o borrador, no reservar, pagar ni enviar incidencias a un servicio externo.
"""
