# Handoff del backend mientras se validan los especialistas

> Actualización 18/10/2026: el montaje compartido y los clientes ya están
> conectados. Ver [integración real](integracion_real.md) para comandos, alcance,
> procedencia de Streamlit y evidencia. Las notas siguientes son históricas.

17/10/2026. Rama `feature/supervisor-grafo`; implementación de síntesis/aplicar en commit `1b5c250`. Este avance queda local para revisión, sin publicar ni modificar la PR automáticamente.

## Qué puede probar David

La API de clientes y los grafos no cambian. `AgentService` recibe las funciones `sintetizar` y `aplicar` como implementaciones; el grafo ya incorpora sus guardias.
El [montaje documentado](sintetizar_aplicar.md) muestra la inyección de los dos especialistas. La traducción documental recibe un callable del contrato de Héctor; no conecta el nodo real por defecto ni exige el subgrafo.

Para revisar el comportamiento sin montar Streamlit:

```powershell
python -m scripts.export_evidence --scenario partial
python -m scripts.export_evidence --output output/evidencia_backend_simulado.json
```

El exportador utiliza `AgentService`, el grafo principal, síntesis y aplicar reales. Solo los especialistas y las decisiones están simulados. No importa el nodo documental ni el RAG, no consulta HTTP y no prepara índices. Es una prueba de integración del backend, no un cliente ni un fallback de producción.

El segundo comando guarda diez casos: éxito, respuesta parcial, abstención, error y fallback histórico, cada uno con aprobación/rechazo simulados. El JSON incluye los estados pendiente/final, fuentes ficticias, traza y comprobaciones del breakpoint, hilo, plan, cierre, idempotencia y evento HITL único. La captura
histórica usa una fecha ficticia explícita: no es evidencia municipal. Si una comprobación no se cumple, el comando falla en vez de declarar éxito.

David puede contrastar su cliente con este recorrido:

1. Conservar una instancia del servicio y el hilo entre reruns, por sesión.
2. Ejecutar `procesar_turno`, presentar respuesta, fuentes/limitaciones y plan.
3. Comprobar `pendiente_hitl=True`, `approved=None` y `done=False` antes de mostrar la decisión. No llamar a `resolver_plan` automáticamente al presentar el plan.
4. Enviar la decisión humana con el mismo hilo y `plan_id` vigente.
5. Mostrar cierre al aprobar o propuesta limpia al rechazar; permitir un pedido nuevo. Repetir la misma resolución no vuelve a aplicar.
6. Crear otra conversación y comprobar que los resultados no se mezclan.

Esta lista está preparada para revisión conjunta: no se ha ejecutado sobre Streamlit ni se ha implementado la UI de David.

## Qué confirmar con Héctor

La `.venv` revisada estaba incompleta. La dependencia ausente
`sentence_transformers` bloqueó la colección, pero eso no demuestra
incompatibilidad entre versiones ni un defecto de su RAG. No se han instalado dependencias ni cambiado versiones mientras esperamos una referencia conocida.

Solicitar versión de Python, dependencias efectivamente utilizadas, proveedor activo, configuración necesaria, comandos de indexado y una consulta/prueba reproducible. Confirmar si los requirements actuales reproducen ese entorno.
La conexión requiere acordar nodo directo frente a su grafo como puerta pública y ejemplos reales de éxito, abstención, error y respuesta parcial con fuentes.

Separar de esa preparación los hallazgos estáticos/aislados pendientes de revisión:

- `REGISTRY` es un diccionario, pero cinco tests lo parchean con `setattr`.
- El presupuesto cero toma el presupuesto predeterminado; se observó con un doble.
- `_embed_huggingface` referencia variables sin definir; el diagnóstico aislado produjo `NameError` para `modules`, no una ejecución del modelo real.
- Dos archivos de pruebas consultan/crean colección Chroma durante la colección.

No se corrigen aquí las pruebas ni el código del especialista. Antes de ejecutar la suite completa, acordar qué operaciones requieren índice o servicios. El diagnóstico previo completo sigue siendo trabajo local; este handoff contiene el resumen necesario sin exigir publicar aquel archivo.

## Verificación de este avance

```powershell
python -m pytest -q -p no:cacheprovider tests/test_export_evidence.py tests/test_sintetizar_aplicar.py tests/test_documental_adapter.py tests/test_infra_sintetizar_aplicar.py tests/test_import_boundaries.py tests/test_sync_integration.py tests/test_agent_service.py tests/test_state.py tests/test_supervisor.py tests/test_demo.py tests/test_contracts.py tests/test_async.py tests/test_graph_hitl.py tests/test_clients.py
```

Resultado final: **269 pruebas superadas**. La primera ejecución obtuvo 268 superadas y un error de preparación: el directorio temporal predeterminado de pytest no era accesible para este proceso. Se volvió a ejecutar con un `--basetemp` nuevo dentro del workspace y pasó completa. No se debilitó el test.
`-p no:cacheprovider` evita el aviso de caché que se observó en el entorno del usuario; no omite pruebas.

Si el directorio temporal predeterminado tampoco es accesible en otro entorno, añadir `--basetemp` apuntando a una carpeta nueva y dedicada a pytest. Pytest gestiona el contenido de esa carpeta; no usar una que contenga trabajo propio.

Estos resultados no validan RAG, API, disponibilidad municipal ni clientes.
El exportador usa datos ficticios y no sustituye la aprobación humana del flujo de producto. No se ha ejecutado ni enviado ningún mensaje a Slack.

## Archivos propios de esta continuación

- `scripts/export_evidence.py`: implementa el exportador antes vacío.
- `tests/test_export_evidence.py`: valida los escenarios y su aislamiento del RAG.
- `README.md` y `seguimiento_pb02.md`: corrigen el estado obsoleto del backend.
- Este documento: handoff y separación entre preparación local y fallos internos.
