# Conectar el documental real al grafo supervisor

Borrador manual hacia `develop`. La PR #5 seguía abierta al consultar GitHub.
No se publica ni modifica automáticamente ninguna PR.

El grafo admitía especialistas inyectados, pero faltaba un montaje con el
documental real. `crear_servicio_real()` conecta
`obtener_grafo_documental().invoke` al adaptador existente y a `AgentService`.
Reutiliza supervisor, router, síntesis y aplicar, con la pausa HITL y resolución
del plan vigente. La construcción no lanza consultas y no hay fallback a demo.

Instalaciones se declara no disponible desde el montaje hasta que su responsable
publique el nodo o una operación pública consumible. No se implementa su
especialista ni se utilizan datos simulados. CLI y Streamlit quedan intactos.

La PR no modifica internamente los nodos, el pipeline RAG, sus dependencias ni
sus pruebas. Los fallos de esas implementaciones se trasladan a sus responsables.

La verificación del montaje usa una tool RAG doble explícita y comprueba rutas,
traducción de contratos, fuentes, errores, pausa, aprobación, rechazo,
idempotencia, plan antiguo y aislamiento. No certifica recuperación real.
El diagnóstico real queda bloqueado por ausencia del índice configurado y se
detiene antes de invocar el RAG, para no crear almacenamiento automáticamente.

Resultado: **299 pruebas del backend y montaje superadas**. Se excluyen
expresamente las tres suites de especialistas; permanecen intactas y sus fallos
internos siguen pendientes de sus responsables. No se afirma éxito de la suite
completa ni de consultas reales con recuperación documental.

Detalle de archivos, comandos y resultados en
[conexión del supervisor](integracion_real.md).
