# Coordinación de integración: supervisor, grafo y RAG

## Trabajo actual
Alejandra está preparando `contracts.py`, `state.py` y el supervisor para avanzar en la construcción del grafo. 

Las estructuras relacionadas con el RAG son provisionales y se revisarán cuando Héctor aporte el contrato del conector.

## Contrato RAG pendiente

Para recibir, mapear y verificar los contratos de ambos especialistas, seguir
la [especificación de integración](integracion_especialistas.md). Incluye la
ficha de entrega, los acuerdos previos al adaptador y los escenarios de aceptación.

Héctor aportará la interfaz del RAG a partir de su implementación real:

- Cómo se realiza una consulta.
- Qué devuelve y cómo incluye las fuentes.
- Cómo comunica la falta de evidencia.
- Cómo comunica los errores.
- Si la llamada es síncrona o asíncrona.

## Necesidades del supervisor y del grafo

Para integrar el especialista documental necesitamos poder:

- Enviarle una consulta.
- Incorporar su resultado al estado compartido.
- Conservar las fuentes disponibles.
- Distinguir una respuesta válida, falta de evidencia y fallo técnico.

Estas necesidades no fijan todavía la estructura de entrada y salida del conector.

## Contrato interno del grafo síncrono

`agentes/contracts.py` distingue los roles `documental` e `instalaciones` de
las decisiones `sintetizar` y `FINISH`. El supervisor y el grafo comparten los
nombres de roles derivados de esos tipos. `FINISH` conduce a síntesis si falta
un plan válido y, cuando está listo, a la pausa antes de `aplicar`.

`ToolResult`, `Evidence` y `PendingAction` siguen siendo propuestas internas,
no contratos confirmados de los especialistas. Se conservan los nombres y
campos para probar el montaje con dobles. Un adaptador incorporará las salidas
reales cuando se acuerden consulta, fuentes, abstención, errores y sincronía.
No se fija un rango de score ni se exige evidencia en resultados sin respuesta.

La presencia de un resultado en `specialist_results` cuenta como intento
completado, incluso con `status="abstained"` o `status="error"`. El contrato real
deberá concretar la actualización parcial que devuelve cada especialista.

`needs_approval` se conserva por compatibilidad y el grafo lo ignora. La decisión
humana es `approved` en el estado, escrita por el cliente al reanudar el mismo
checkpoint. `PendingAction` no activa la pausa ni representa una aprobación.

## API síncrona de clientes

`agentes.agent.AgentService` recibe los cuatro nodos por inyección:
`documental_node`, `instalaciones_node`, `sintetizar_node` y `aplicar_node`.
El proveedor de rutas es opcional; sin él se utilizan reglas deterministas.
Crear y conservar una instancia por servicio, compartida entre sus turnos.
No crear el servicio de nuevo por mensaje o por cada rerun de Streamlit.

- `nueva_conversacion() -> str`: devuelve un `thread_id` nuevo; el cliente
  reinicia sus burbujas y conserva ese identificador para las siguientes llamadas.
- `procesar_turno(mensaje, thread_id) -> dict`: limpia el pedido anterior y
  ejecuta hasta la pausa. Rechaza mensajes vacíos y pedidos con trabajo pendiente.
- `consultar_estado(thread_id) -> dict`: lee una copia del checkpoint, sin
  ejecutar nodos. Un hilo nuevo devuelve el estado vacío.
- `resolver_plan(thread_id, aprobado, *, plan_id) -> dict`: exige un booleano
  real y el identificador vigente; guarda la decisión y reanuda el mismo hilo.

El resultado incluye los campos de `AgentState` y dos campos de presentación:
`pendiente_hitl` se obtiene de `snapshot.next`; `plan_id` identifica la propuesta
actual. Estos dos campos no son actualizaciones que los especialistas deban
devolver. El cliente debe enviar el `plan_id` que recibió junto al plan.

Una resolución idéntica repetida no vuelve a ejecutar `aplicar`. Una resolución
contradictoria o con un plan anterior se rechaza. Un pedido nuevo después de
aprobar o rechazar reinicia `approved`, `done`, resultados, respuesta y plan.
El servicio serializa las operaciones del mismo hilo mediante un lock.

Los errores de validación e integración se propagan como excepciones para que
el cliente los presente. Una ejecución fallida con nodos pendientes no se
sobrescribe con otro pedido; se puede iniciar una conversación nueva.

La configuración mínima está en `agentes.settings`: `AgentSettings(max_iter=8)`
o `load_settings()` desde la variable de entorno `MAX_ITER`. Un valor vacío usa
8; uno no entero o no positivo falla al crear el servicio. Este módulo no carga
`.env` automáticamente; el punto de entrada puede cargarlo o inyectar settings.
No se requieren claves ni un proveedor LLM para trabajar con dobles.

Checkpoints, locks e identificadores de plan viven en el proceso del servicio.
No se promete recuperación de decisiones tras reinicios, incluso si se inyecta
otro checkpointer. La integración de imágenes y las tools reales sigue pendiente.

## LLM compartido

Queda pendiente acordar con Héctor cómo consumirá el supervisor la interfaz de `llm.py`.

## Siguiente paso

Cuando esté disponible el contrato RAG, revisaremos juntos su encaje con `contracts.py` y `state.py`, y ajustaremos la integración necesaria.


## Retrieval Augmented Generation (RAG)

### Generación de indexación 

#### IMPORTANTE:  

Primero es preciso tener la configuración local en el archivo `.env`.

#### Llamada a indexación:

Se ha expuesto la herramienta para ejecutar el pipeline de ingesta. Los datos a indexar residen en `data/corpus/` y para realizar la indexación es preciso lanzar la instrucción siguiente desde el raíz del proyecto:

```bash  
python -c "from rag.pipeline import ejecutar_pipeline; ejecutar_pipeline('data/corpus')"
``` 

#### IMPORTANTE:  

Si lo que se quiere hacer es una reindexación (porque ya se ha hecho la indexación) es preciso indicarlo con el parámetro recreate_index=True en la llamada al final del comando, porque de lo contrario dará **error de dimensiones en ChromaDB**:

```bash  
python -c "from rag.pipeline import ejecutar_pipeline; ejecutar_pipeline('data/corpus', recreate_index=True)"
``` 

### Comprobación de nodo y herramienta

Se han expuesto por una parte `nodo_documental` y por otro `rag_preguntar` como herramienta. Se puede verificar con la siguiente instrucción desde el raíz del proyecto:

```bash  
python -c "from agentes.tools import rag_preguntar; from agentes.nodes import nodo_documental; print('ok: agentes.*')"
``` 

### Firmas públicas

| Función | Firma | Uso |
|---|---|---|
| `responder` | `(pregunta: str, top_k: int \| None = None) -> dict` | RAG completo, contrato principal |
| `rag_preguntar` | `(consulta: str) -> str` | Wrap para agentes: solo devuelve texto |
| `recuperar` | `(pregunta: str, top_k: int = 5, persist_dir=None, collection_name=None) -> list[dict]` | Retrieval puro (depuración/evaluación) |

### Esquema de retorno

El dict completo de responder() campo a campo, con tipo, contenido y cuándo está vacío:

`respuesta: str` - texto generado, siempre anclado al corpus.
`chunks: list[dict]` - {text, source, metadata, distance}, limitado a MAX_CHUNKS.
`fuentes: list[str]` - únicas, en orden de aparición.
`contexto: str` - texto plano de los chunks (depuración).
`metrics: dict` - top_k, n_chunks, model, t_retrieval, t_generation.
`abstained: bool` - ver sección de abstención.
`error: str | None` - solo si falla antes de llamar al LLM.

### COmportamientos de grounding y abstención

- **Dos capas de abstención independientes:**
  - **Guardrail de distancia:** si la mejor distancia coseno > UMBRAL_ABSTENCION (0.65) → `abstained=True` sin llamar al LLM.
  - **Abstención del LLM:** si no hay evidencia suficiente devuelve literalmente `ABSTENTION_MESSAGE` y se marca `abstained=True`.
- `rag_preguntar` nunca lanza: en error devuelve `ABSTENTION_MESSAGE` (no rompe la cadena del agente).
- `recuperar` sí lanza `ValueError` (pregunta vacía, `top_k <= 0`) y devuelve `[]` si la colección está vacía.
- **Sin estado:** cada llamada es independiente (segura para llamarla varias veces en un ciclo de agente).

### Dependencias

- El indexado debe de existir
- Variables en .env correctamente configuradas: GEN_PROVIDER, GOOGLE_GEN_MODEL, GOOGLE_API_KEY, TOP_K, MAX_CHUNKS, GEN_TEMPERATURE, ABSTENTION_MESSAGE, CHROMA_DIR, COLLECTION_NAME.
- Necesidad de reindexación si se cambian: EMBED_* o CHUNK_*: hay que reindexar.

### Rendimiento y operación

- Latencia esperada (retrieval + generación; recordad que el primer batch en frío de Ollama puede tardar mucho).
- Retreintidos automáticos ante 503/429 en generación (3 intentos, backoff exponencial).
- Registro estructurado por consulta (línea JSON con pregunta, top_k, n_chunks, modelo, abstained, tiempos).

### Ejemplos de respuesta

1. Respuesta normal:
```json 
{
  "respuesta": "El abono de piscina para temporada cuesta 90 € para empadronados; hay descuentos para menores, mayores y personas en paro.",
  "chunks": [
    {
      "text": "Texto del chunk recuperado del PDF de precios públicos...",
      "source": "PreciosPublicos2026.pdf",
      "metadata": {
        "source": "PreciosPublicos2026.pdf",
        "file_hash": "a1b2c3...",
        "doc_category": "tarifas",
        "semantic_score": 0.87
      },
      "distance": 0.48
    }
  ],
  "fuentes": ["PreciosPublicos2026.pdf"],
  "contexto": "Texto del chunk 1\n\nTexto del chunk 2",
  "metrics": {
    "retrieval": 0.42,
    "generation": 1.85,
    "top_k": 5,
    "n_chunks": 5,
    "model": "gemini-2.0-flash"
  },
  "abstained": false,
  "error": null
}
``` 

2. Abstención:
```json
{
  "respuesta": "No dispongo de esa información en los documentos proporcionados.",
  "chunks": [
    {
      "text": "Chunk más parecido, pero fuera del umbral de evidencia...",
      "source": "212504-0-agenda-actividades-deportes.csv",
      "metadata": { "source": "212504-0-agenda-actividades-deportes.csv" },
      "distance": 0.74
    }
  ],
  "fuentes": ["212504-0-agenda-actividades-deportes.csv"],
  "contexto": "",
  "metrics": {
    "retrieval": 0.38,
    "top_k": 5,
    "n_chunks": 0
  },
  "abstained": true,
  "error": null
}
```

3. Error (posible fallo antes o durante el pipeline RAG)
```json  
{
  "respuesta": "",
  "chunks": [],
  "fuentes": [],
  "contexto": "",
  "metrics": {},
  "abstained": false,
  "error": "Error recuperando contexto: <mensaje de la excepción>"
}
```  
