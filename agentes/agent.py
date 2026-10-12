"""API común para CLI y Streamlit y ciclo de vida de cada pedido.

Operaciones previstas: aprocesar_turno, aresolver_plan, consultar_estado,
nueva_conversacion y registrar_imagen. Adaptadores síncronos opcionales para
clientes que no usan await. No anidar asyncio.run en un loop activo.
Validar mensaje, thread_id, plan_id vigente y decisión humana.
Bloquear pedidos nuevos mientras haya aprobación pendiente; impedir operaciones
simultáneas sobre el mismo thread_id. Conversaciones distintas quedan aisladas.
Aprobar o rechazar reanuda el mismo checkpoint; decisión repetida debe ser
idempotente. Nueva conversación obtiene thread_id nuevo.
Dependencias: contratos, estado, grafo y configuración. No incluir widgets.
"""
