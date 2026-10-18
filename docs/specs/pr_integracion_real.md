# Conectar el documental real y los clientes al servicio síncrono

Borrador para revisión manual. Destino: `develop`. La PR #5 sigue abierta;
si se trasladan estos commits a `feature/supervisor-grafo`, este texto puede
sustituir su descripción. Si se conserva `integration/especialistas-reales`,
abrir una PR desde esa rama y coordinar el solapamiento con #5 antes del merge.
No se ha publicado ni actualizado ninguna PR.

## Problema y comportamiento resultante

El backend tenía síntesis y cierre informativos, pero su montaje solo ofrecía
especialistas simulados. CLI y Streamlit eran cascarones en develop; la rama
de UI mantenía callbacks de demostración sin conectar el servicio.

Se añade un montaje real reutilizable que conecta la puerta pública
`obtener_grafo_documental().invoke` con el adaptador documental y `AgentService`.
Reutiliza el supervisor, la síntesis y aplicar existentes. Construir el servicio
no consulta el RAG. CLI y Streamlit lo conservan entre pedidos y usan la pausa
HITL y la resolución con el plan vigente. La demo permanece como modo explícito,
sin sustituciones automáticas cuando falla el RAG.

El montaje declara instalaciones no disponibles: la rama inspeccionada contiene
la consulta CKAN privada, pero todavía no una operación pública ni el nodo
consumible. No se utiliza un centro arbitrario ni información simulada.

La presentación reutiliza el diseño de David de
`origin/feature/streamlit-ui@c6052b3`, identificando esa procedencia. Se conectan
sus controles con cambios mínimos y se elimina el hilo fijo de simulación.

## Compatibilidad

Se corrigen fallos pequeños reproducidos: monkeypatch de REGISTRY, presupuesto
cero y constructor HuggingFace con variables sin definir. La carga del pipeline
se retrasa hasta la consulta y los errores de dependencias viajan por la tool.
Consultar Chroma exige un índice y colección existentes; no crea almacenamiento.
La colección de pruebas no consulta Chroma y las evaluaciones con modelos son
opt-in, conservando sus aserciones.

No se han modificado la calidad de retrieval, prompts, chunking ni la política
de aprobación. El cierre continúa siendo informativo, sin acciones externas.

## Validación y límites

- Suite completa: **317 pruebas superadas, 44 evaluaciones con modelos opt-in
  omitidas**; `pip check` correcto en Python 3.14.2.
- RAG real: cuatro entradas observadas a tool, pipeline y retrieval híbrido,
  sin dobles. Todas devuelven `RAG_INDEX_MISSING`, sin fuentes recuperadas ni
  llamadas a embeddings/generación. No se afirma éxito de recuperación.
- Servicio real: pausa, aprobación, rechazo, siguiente pedido, plan antiguo,
  idempotencia e hilos aislados verificados con ese error real.
- CLI real: presenta el bloqueo y resuelve el plan informativo. Streamlit:
  reruns y controles verificados mediante AppTest con tool doble explícita.
- HTTP municipal: pendiente por falta de operación pública del especialista.

Los resultados exactos, comandos y evidencia de llamadas a funciones originales
están en [integración real](integracion_real.md) y
[evidencia real](evidencia_integracion_real.json). Las pruebas con tool doble
se identifican como montaje mixto y no certifican el RAG ni HTTP reales.

El entorno carece del índice configurado. La prueba real debe distinguir una
llamada efectiva al pipeline que devuelve error de una recuperación y generación
exitosas. No se ha generado ni reindexado un corpus para ocultar ese requisito.

## Arranque

```powershell
.\.venv\Scripts\python.exe main.py --modo real
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Los cambios locales anteriores del dataset golden y otros documentos se
mantienen fuera de los commits de esta integración.
