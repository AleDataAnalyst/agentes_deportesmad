"""Especialista documental: RAG, evidencias, imagen y borradores.

Entradas: pedido actual, contexto permitido, image_id y presupuesto de tools.
Ejecutar un bucle acotado de propuesta, validación, llamada y observación.
Salidas: resultados documentales del request_id vigente, fuentes, abstenciones,
errores, limitaciones y eventos de tool; actualizar solo campos autorizados.
No inventar condiciones ni tomar un cartel por normativa vigente.
Tools previstas: rag, imagen y preparar_reporte, mediante registry.
"""
