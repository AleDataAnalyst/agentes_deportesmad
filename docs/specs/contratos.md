# Contratos mínimos por acordar

- Entradas/salidas de tools y nodos.
- Campos del estado y propietario de cada actualización.
- Estados de error, abstención y fallback.
- Contrato común de clientes.
- Semántica de aprobar/rechazar y nuevo pedido.

Estado: pendiente de definición y revisión.

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
