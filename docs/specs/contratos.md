# Coordinación de integración: supervisor, grafo y RAG

## Estado revisado — 28/10/2026

El montaje síncrono está implementado: `agentes.runtime` conecta la puerta
`obtener_grafo_documental().invoke` mediante `crear_adaptador_documental`.
Las pruebas verifican traducción y aislamiento con dobles; la aceptación con
RAG, índice, visión y fuentes municipales reales permanece pendiente.
Véanse [el montaje documental](integracion_grafo_documental.md) y
[la configuración real](integracion_real.md).

## Contrato documental y traducción al grafo

El componente documental recibe `request_id`, `pedido`, `contexto_permitido`,
`image_id`, `presupuesto_tools` y `preparar_borrador`. Devuelve el sobre
`documental` con `request_id`, `resultado`, `fuentes`, `abstained`, `errores`,
`limitaciones` y `eventos`. No recibe directamente `AgentState`.

El adaptador crea el identificador por pedido, valida el sobre y su correlación,
y lo convierte en `specialist_results['documental']: ToolResult`. Conserva el
sobre en `data` y cada fuente como `Evidence(source=..., content='')`, sin
inventar fragmentos ni puntuaciones. Los errores tienen prioridad sobre la
abstención; una respuesta vacía sin error se trata como abstención. No muta
la entrada ni comparte el checkpoint/HITL con el componente documental.

## Contrato interno del grafo síncrono

`agentes/contracts.py` distingue los roles `documental` e `instalaciones` de
las decisiones `sintetizar` y `FINISH`. El supervisor y el grafo comparten los
nombres de roles derivados de esos tipos. `FINISH` conduce a síntesis si falta
un plan válido y, cuando está listo, a la pausa antes de `aplicar`.

`ToolResult`, `Evidence` y `PendingAction` son formatos internos; no sustituyen
la interfaz pública del especialista. El adaptador documental ya traduce su
sobre y el nodo público de instalaciones devuelve el formato del grafo.
No se fija un rango de score ni se exige evidencia en resultados sin respuesta.

La presencia de un resultado en `specialist_results` cuenta como intento
completado, incluso con `status="abstained"` o `status="error"`. Los nodos
devuelven actualizaciones parciales, sujetas a sus guardias de campos.

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
- `procesar_turno(mensaje, thread_id, *, image_id=None) -> dict`: limpia el pedido anterior y
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
otro checkpointer. El transporte de imagen por pedido está implementado;
visión real y aceptación conjunta con RAG siguen pendientes.

### Imagen del pedido

Firma tipada: `procesar_turno(self, mensaje: str, thread_id: str, *, image_id: str | None = None) -> dict[str, Any]`.
Las llamadas de dos argumentos conservan su comportamiento. El mensaje debe
ser texto no vacío, también cuando se aporta una imagen.

`image_id` es una referencia local de JPG/JPEG/PNG ya guardada, nunca bytes ni
base64. Se admite una ruta relativa a la raíz del repositorio o absoluta dentro
de `output/imagenes/`, y únicamente el asset demo `assets/imagen_demo.jpg`
(también su alias `imagen_demo`). Debe existir y ser un archivo. Se rechazan
traversal con `..`, rutas externas y enlaces resueltos fuera de esas ubicaciones.
El backend devuelve y transporta la ruta absoluta canónica. Los errores propios
de esta validación no incluyen la ruta personal.

La comprobación de extensión no acredita el contenido: este backend solo valida
referencia, autorización y existencia sin abrir ni codificar el archivo. Se
conservan los controles de contenido del guardado actual del cliente y de visión.
Se revalida antes del callable documental; no hay garantía de atomicidad si
otro proceso cambia archivos o enlaces después de esa comprobación.

`AgentState.image_id` pertenece al pedido actual, se reinicia a `None` al iniciar
otro sin imagen y no se añade al historial ni a `debug_trace`. Las guardias no
permiten escribir este campo a los nodos. El adaptador pasa `image_id` por el
contrato documental público existente, sin cambiar sus firmas ni el grafo.
Su opción de construcción se conserva solo para estados antiguos que omiten
la clave: si existe en el estado, prevalece incluso siendo `None`. Toda imagen
seleccionada se valida al ejecutar; construir el adaptador no inspecciona archivos.

Contrato y ejemplo para David: [imagen por pedido](../handoff_imagen_por_pedido.md).

## LLM compartido

`agentes.llm` define `LlmMessage`, `LlmResponse` y el protocolo `LlmAdapter`.
`generate(messages, tools, *, temperature, max_output_tokens, timeout)` devuelve
texto y llamadas estructuradas (`id`, `name`, `arguments`). El modelo propone;
Python valida la allowlist, ejecuta herramientas y añade su resultado al historial.

El supervisor consume esta interfaz mediante `crear_proveedor_supervisor_real`,
sin herramientas y con configuración `SUPERVISOR_*` independiente de `GEN_*`.
Los especialistas usan `ejecutar_especialista` al activar `ESPECIALISTAS_MODO=llm`;
el modo predeterminado sigue siendo `reglas`. El ejecutor conserva llamadas
parciales en `FalloPlanificacion` para que el nodo no reinicie el presupuesto.

### Historial de herramientas de Google

| Mensaje interno | Representación Google |
| --- | --- |
| `system` | `GenerateContentConfig.system_instruction`, fuera de `contents` |
| `user` | `Content(role='user')` con texto |
| `assistant` con `tool_calls` | `Content(role='model')`, una `Part.from_function_call(name=..., args=...)` por llamada |
| `tool` | `Content(role='user')`, `Part.from_function_response(name=..., response=...)` con el resultado JSON decodificado |
| `assistant` con texto | `Content(role='model')` con texto |

La fábrica `Part.from_function_call` exige argumentos por nombre en el SDK
instalado durante la validación (`google-genai 2.22.0`). Pasarle un `FunctionCall`
posicional causaba un `TypeError` antes de enviar la segunda petición al cliente.
La corrección conserva nombre, argumentos, respuesta y roles. Los identificadores
internos se generan como `call_<índice>` al parsear la respuesta; esta corrección
no añade su transporte al SDK ni cambia esa política.

Regresión en `tests/test_llm_google.py`: primera respuesta con tool call,
ejecución de herramienta y segunda llamada al cliente doble para los bucles RAG
y de especialistas. Usa tipos reales del SDK, sin API key ni red. Evidencia,
comandos y commit probado en [el registro del arreglo](../google_adapter_tool_calls.md).

## Aceptación pendiente

El montaje y sus regresiones con dobles están comprobados. Falta ejecutar la
aceptación con un modelo Google disponible, herramientas y fuentes verificables,
además del índice compatible y la visión real. Una suite offline o una inferencia
sin herramientas no cierra la aceptación del recorrido de dos turnos.

## Retrieval Augmented Generation (RAG)

### Generación de indexación

#### IMPORTANTE:

Primero es preciso tener la configuración local en el archivo `.env`.

El OCR de PDFs requiere Tesseract. En Windows, si se procesan PDFs escaneados,
también puede requerir Poppler si su ejecutable no está en `PATH`.

##### En Windows PowerShell

```powershell
winget install tesseract-ocr.tesseract

# Persistente para el usuario actual
[Environment]::SetEnvironmentVariable(
  "Path",
  "$env:Path;$env:ProgramFiles\Tesseract-OCR",
  "User"
)
```

Si `pdf2image` no encuentra Poppler, define su ruta en `.env`:

```env
POPPLER_PATH=C:\Program Files\poppler-24.08.0\Library\bin
```

##### En Ubuntu/Debian

```bash
sudo apt-get install tesseract-ocr
```

##### En macOS con Brew
```bash
brew install tesseract
```


Tras este primer paso, que se realiza una única vez por Sistema Operativo, es preciso tener un archivo `.env` con la variable `OCR_AGENT` fijada a `tesseract`:
```text
# OCR para PDF
OCR_AGENT=tesseract
```

Tras estos pasos de instalación y declaración ya se puede pasar a las fases indexación/re-indexación.

#### Llamada a indexación

Los datos a indexar residen en `data/corpus/`. Desde la raíz del proyecto:

```bash
python -c "from rag.pipeline import ejecutar_pipeline; ejecutar_pipeline('data/corpus')"
```

#### IMPORTANTE:

Si ya existe un índice, usa `recreate_index=True`. De lo contrario, pueden
producirse errores de dimensiones en ChromaDB:

```bash
python -c "from rag.pipeline import ejecutar_pipeline; ejecutar_pipeline('data/corpus', recreate_index=True)"
```

#### PDFs TAB y OCR

Los PDFs que requieren tratamiento especial se declaran en
`data/corpus/especiales.txt`:

```text
# nombre.pdf: TAB | OCR
documento-tabular.pdf: TAB
documento-escaneado.pdf: OCR
```

- `TAB`: extrae tablas con `pdfplumber`; cada fila se indexa junto a su cabecera,
  página y número de tabla.
- `OCR`: convierte el PDF a imágenes a 200 DPI y aplica Tesseract con `--psm 6`.
  Si el OCR falla, se intenta extracción directa como fallback.

El manifiesto se procesa una vez por indexación, no una vez por cada PDF.

### Comprobación de nodo y herramienta

Se han expuesto por una parte `nodo_documental` y por otro `rag_preguntar` como herramienta. Se puede verificar con la siguiente instrucción desde el raíz del proyecto:

```bash
python -c "from agentes.tools import rag_preguntar; from agentes.nodes import nodo_documental; print('ok: agentes.*')"
```

### Firmas públicas

| Función | Firma | Uso |
|---|---|---|
| `responder` | `(pregunta: str, top_k: int \| None = None) -> dict` | RAG completo, contrato principal |
| `rag_preguntar` | `(consulta: str, con_diagnostico: bool \| None = None) -> dict[str, Any]` | Tool: `respuesta`, `fuentes`, `abstained`, `error`; diagnóstico opcional |
| `recuperar` | `(pregunta: str, top_k: int = 5, persist_dir=None, collection_name=None) -> list[dict]` | Retrieval puro (depuración/evaluación) |

## Interfaz oficial del RAG para el grafo

La interfaz que consumirá el especialista documental es:

```python
responder(pregunta: str, top_k: int | None = None) -> dict
```

La llamada es **síncrona y bloqueante**: el nodo documental espera a que `responder()` devuelva el resultado completo antes de continuar.

No es asíncrona y no devuelve un `Future`, coroutine ni promesa.

### Entrada

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `pregunta` | `str` | Sí | Consulta del usuario o consulta reformulada por el especialista |
| `top_k` | `int \| None` | No | Número máximo de chunks a recuperar; si es `None`, se usa la configuración por defecto |

### Salida

`responder()` devuelve siempre un diccionario controlado:

```python
{
    "respuesta": str,
    "chunks": list[dict],
    "fuentes": list[str],
    "contexto": str,
    "metrics": dict,
    "abstained": bool,
    "error": str | None,
}
```

### Fuentes

Las fuentes se devuelven en `fuentes` como lista de cadenas, únicas y en orden de aparición.

Cada chunk de `chunks` conserva además:

- `text`
- `source`
- `metadata`
- `distance`

### Falta de evidencia

La falta de evidencia se comunica con:

```python
"abstained": True
```

Puede producirse por:

- Guardrail de distancia: la mejor distancia coseno supera `UMBRAL_ABSTENCION`.
- El LLM determina que no hay evidencia suficiente.

En ambos casos, `error` debe ser `None`: una abstención no es un fallo técnico.

### Errores

Un fallo técnico se comunica con:

```python
"error": "<mensaje controlado>"
```

Por ejemplo, un fallo al recuperar contexto o al llamar al proveedor.

En ese caso:

- `abstained` permanece en `False`.
- `respuesta` puede quedar vacía.
- La excepción no se propaga hacia el grafo.

### Funciones auxiliares

- `recuperar()` es una función de depuración y evaluación; devuelve chunks, no el contrato completo del RAG.
- `rag_preguntar()` es un wrapper para agentes que devuelve únicamente `str`; no debe usarse como contrato principal para el grafo porque pierde fuentes, abstención y error estructurados.

### Esquema de retorno

El dict completo de responder() campo a campo, con tipo, contenido y cuándo está vacío:

`respuesta: str` - texto generado, siempre anclado al corpus.
`chunks: list[dict]` - {text, source, metadata, distance}, limitado a MAX_CHUNKS.
`fuentes: list[str]` - únicas, en orden de aparición.
`contexto: str` - texto plano de los chunks (depuración).
`metrics: dict` - `retrieval_mode`, tiempos `retrieval`/`generation`, `top_k`, `n_chunks` y `model`, según la fase alcanzada; vacío ante error.
`abstained: bool` - ver sección de abstención.
`error: str | None` - error de validación, recuperación o generación; no es evidencia útil.

La tool `rag_preguntar` conserva las cuatro claves `respuesta`, `fuentes`,
`abstained` y `error`. Con `con_diagnostico=True` o `RAG_CON_DIAGNOSTICO=1/true/yes`
añade `distancia_mejor`, `respuesta_llm` y `motivo`, también ante error.
El nodo normaliza esta salida a `ok/resultado/fuentes/abstained/error` antes
de validar la observación. Son capas distintas del resultado completo de `responder`.

### Comportamientos de grounding y abstención

- **Dos capas de abstención independientes:**
  - **Guardrail de distancia:** si la mejor distancia coseno > UMBRAL_ABSTENCION (0.65) → `abstained=True` sin llamar al LLM.
  - **Abstención del LLM:** se marca `abstained=True` si la respuesta contiene `ABSTENTION_MESSAGE`, sin distinguir mayúsculas. Esto comprueba la señal del generador; no certifica su calidad semántica.
- `rag_preguntar` captura errores de consulta y normalización: devuelve `respuesta=''`, `fuentes=[]`, `abstained=False` y el error como dato. El envoltorio de texto `rag_ask` es el que usa `ABSTENTION_MESSAGE` ante error.
- `recuperar` sí lanza `ValueError` (pregunta vacía, `top_k <= 0`) y devuelve `[]` si la colección está vacía.
- **Sin estado:** cada llamada es independiente (segura para llamarla varias veces en un ciclo de agente).

### Dependencias

- El indexado debe de existir
- Variables en .env correctamente configuradas: GEN_PROVIDER, GOOGLE_GEN_MODEL, GOOGLE_API_KEY, TOP_K, MAX_CHUNKS, GEN_TEMPERATURE, ABSTENTION_MESSAGE, CHROMA_DIR, COLLECTION_NAME.
- Necesidad de reindexación si se cambian: EMBED_* o CHUNK_*: hay que reindexar.

### Rendimiento y operación

- Latencia esperada (retrieval + generación; recordad que el primer batch en frío de Ollama puede tardar mucho).
- Reintentos automáticos ante 503/429 en generación (3 intentos, backoff exponencial).
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
