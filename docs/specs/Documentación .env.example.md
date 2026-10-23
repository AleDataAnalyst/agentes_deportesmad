# Documentación de .env.example

Este archivo define la configuración externa del agente documental y del pipeline RAG del proyecto. Debe copiarse a .env y completarse con valores reales; .env no debe versionarse en Git porque puede contener claves de API.

```bash
cp .env.example .env
``` 

```cmd
copy .env.example .env
```

## Convenciones

1. Los valores entre comillas dobles son cadenas de texto.
2. Los valores true / false son interruptores booleanos.
3. Una variable vacía normalmente indica que:
   - la funcionalidad asociada está desactivada, 
   - pendiente de configurar o 
   - debe inferirse en tiempo de ejecución.

Las claves (`GOOGLE_API_KEY`, `HF_TOKEN`) son secretos y no deben compartirse ni incluirse en commits. Esto incluye llevarlos hardcodeados al código fuente.

## Supervisor y grafo

| Variable     | Tipo   | Valor por defecto | Descripción                                                                                                                                                                                    |
| ------------ | ------ | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MAX_ITER     | Entero | 8                 | Número máximo de iteraciones permitidas al supervisor o grafo de agentes. Limita bucles excesivos y protege frente a ejecuciones no convergentes. agentes_deportesmad/.env.example             |
| RAG_CALLABLE | Cadena | Vacío             | Ruta importable del conector RAG, normalmente con formato modulo:funcion. El responsable del módulo debe confirmar el formato exacto y la función que expone. agentes_deportesmad/.env.example |
| MAX_STEPS    | Entero | Vacío             | Límite máximo de pasos de ejecución. Está declarado como pendiente de integración con su módulo correspondiente. agentes_deportesmad/.env.example                                              |
| MAX_TURNS    | Entero | Vacío             | Número máximo de turnos de conversación o interacción con el agente. También aparece como pendiente de integración. agentes_deportesmad/.env.example                                           |
| HTTP_TIMEOUT | Entero | Vacío             | Tiempo máximo de espera, en segundos, para peticiones HTTP. Pendiente de integración con el módulo que realice las llamadas de red. agentes_deportesmad/.env.example                           |

## Proveedores de IA

| Variable       | Tipo   | Valores admitidos           | Descripción                                                                                                                                                                                           |
| -------------- | ------ | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EMBED_PROVIDER | Cadena | ollama, huggingface, google | Proveedor utilizado para generar embeddings. ollama es la opción offline y sin coste; huggingface y google requieren conectividad y, en algunos casos, credenciales. agentes_deportesmad/.env.example |
| TAG_PROVIDER   | Cadena | ollama, huggingface, google | Proveedor empleado para la generación de etiquetas o metadatos semánticos. agentes_deportesmad/.env.example                                                                                           |
| GEN_PROVIDER   | Cadena | ollama, huggingface, google | Proveedor utilizado para generación de texto, incluida la creación del conjunto de evaluación. agentes_deportesmad/.env.example                                                                       |
| VISON_MODEL    | Cadena | Nombre de modelo Gemini     | Modelo multimodal de Google usado para tareas de visión. El ejemplo usa gemini-2.5-flash y depende de GOOGLE_API_KEY. agentes_deportesmad/.env.example                                                |

## Credenciales

| Variable       | Tipo   | Obligatoria                                   | Descripción                                                                                                                                                                                     |
| -------------- | ------ | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GOOGLE_API_KEY | Cadena | Sí para proveedores google y para VISON_MODEL | Clave de API de Google utilizada por los modelos Gemini de embeddings, etiquetado, generación y visión. Debe mantenerse secreta. agentes_deportesmad/.env.example                               |
| HF_TOKEN       | Cadena | Condicional                                   | Token de Hugging Face. Es necesario principalmente para acceder a modelos restringidos o gated; puede dejarse vacío si los modelos seleccionados son públicos. agentes_deportesmad/.env.example |

## Google

| Variable           | Valor de ejemplo   | Descripción                                                                                                       |
| ------------------ | ------------------ | ----------------------------------------------------------------------------------------------------------------- |
| GOOGLE_EMBED_MODEL | gemini-embedding-2 | Modelo de Google empleado para calcular embeddings cuando EMBED_PROVIDER=google. agentes_deportesmad/.env.example |
| GOOGLE_TAG_MODEL   | gemini-3.6-flash   | Modelo de Google empleado para etiquetado cuando TAG_PROVIDER=google. agentes_deportesmad/.env.example            |
| GOOGLE_GEN_MODEL   | gemini-3.6-flash   | Modelo de Google empleado para generación textual cuando GEN_PROVIDER=google. agentes_deportesmad/.env.example    |

## Ollama

| Variable           | Valor de ejemplo               | Descripción                                                                                                                          |
| ------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| OLLAMA_BASE_URL    | http://127.0.0.1:11434         | URL base del servidor Ollama. Por defecto apunta a una instancia local en el puerto estándar 11434. agentes_deportesmad/.env.example |
| OLLAMA_EMBED_MODEL | qwen3-embedding:0.6b           | Modelo de embeddings descargado y servido por Ollama. agentes_deportesmad/.env.example                                               |
| OLLAMA_TAG_MODEL   | smtek/Qwen3.8-27B:Q2_K_XL-16gb | Modelo local usado para etiquetado. agentes_deportesmad/.env.example                                                                 |
| OLLAMA_GEN_MODEL   | smtek/Qwen3.8-27B:Q2_K_XL-16gb | Modelo local usado para generación textual. agentes_deportesmad/.env.example                                                         |


## Hugging Face

| Variable       | Valor de ejemplo                                            | Descripción                                                                                                                                                                          |
| -------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| HF_EMBED_MODEL | sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | Modelo de embeddings de Hugging Face. agentes_deportesmad/.env.example                                                                                                               |
| HF_TAG_MODEL   | meta-llama/Llama-3.2-3B-Instruct                            | Modelo usado para etiquetado mediante Hugging Face. agentes_deportesmad/.env.example                                                                                                 |
| HF_GEN_MODEL   | meta-llama/Llama-3.2-3B-Instruct                            | Modelo usado para generación textual mediante Hugging Face. agentes_deportesmad/.env.example                                                                                         |
| HF_DEVICE      | cpu o cuda                                                  | Dispositivo de inferencia para modelos de embeddings y generación de Hugging Face. cuda requiere GPU NVIDIA con drivers y entorno CUDA configurado. agentes_deportesmad/.env.example |


## Ingesta y chunking

| Variable      | Tipo   | Valor por defecto | Descripción                                                                                                                                                                   |
| ------------- | ------ | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CHUNK_SIZE    | Entero | 1000              | Tamaño objetivo de cada fragmento de texto, habitualmente en caracteres. Determina cuánto contenido se agrupa antes de generar un embedding. agentes_deportesmad/.env.example |
| CHUNK_OVERLAP | Entero | 120               | Número de caracteres solapados entre fragmentos consecutivos. Ayuda a preservar contexto en fronteras de corte. agentes_deportesmad/.env.example                              |


## Recuperación

| Variable           | Tipo   | Valores admitidos  | Descripción                                                                                                                                                                                              |
| ------------------ | ------ | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RAG_RETRIEVAL_MODE | Cadena | vectorial, hibrido | Modo de recuperación. vectorial usa búsqueda por similitud de embeddings; hibrido combina búsqueda vectorial con señales adicionales. Ante duda, se recomienda hibrido. agentes_deportesmad/.env.example |
| TOP_K              | Entero | 5                  | Número de fragmentos más relevantes que la búsqueda inicial devuelve. agentes_deportesmad/.env.example                                                                                                   |
| MAX_CHUNKS         | Entero | 5                  | Límite final de fragmentos que se incorporan al contexto del modelo. agentes_deportesmad/.env.example                                                                                                    |


## Embeddings e indexado

| Variable                 | Tipo     | Valor por defecto | Descripción                                                                                                                                                                                           |
| ------------------------ | -------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EMBED_DIM                | Entero   | 1024              | Dimensión máxima del índice. La dimensión final se calcula como min(dimensión del modelo, EMBED_DIM). Debe ser compatible con la configuración de la base vectorial. agentes_deportesmad/.env.example |
| EMBED_BATCH_SIZE         | Entero   | 50                | Cantidad de textos procesados por lote al generar embeddings. Un valor mayor puede acelerar el indexado, pero aumenta el consumo de memoria. agentes_deportesmad/.env.example                         |
| EXPORT_EMBEDDINGS        | Booleano | true              | Exporta los embeddings generados durante el proceso de indexado. agentes_deportesmad/.env.example                                                                                                     |
| EMBED_CHECKPOINT_ENABLED | Booleano | true              | Activa puntos de control durante la generación de embeddings, permitiendo reanudar o evitar recalcular trabajo ya completado. agentes_deportesmad/.env.example                                        |
| EMBED_DIM_MAX_OLLAMA     | Entero   | Vacío             | Dimensión nativa máxima declarada del modelo de embeddings de Ollama. Vacío significa que no se declara. Ejemplo: 2560 para qwen3-embedding:4b. agentes_deportesmad/.env.example                      |
| EMBED_DIM_MAX_HF         | Entero   | Vacío             | Dimensión nativa máxima declarada del modelo de embeddings de Hugging Face. Ejemplo: 384 para all-MiniLM-L6-v2. agentes_deportesmad/.env.example                                                      |
| EMBED_DIM_MAX_GOOGLE     | Entero   | Vacío             | Dimensión nativa máxima declarada del modelo de embeddings de Google. agentes_deportesmad/.env.example                                                                                                |

> Las variables `EMBED_DIM_MAX_*` alimentan la comprobación previa y los mensajes informativos sobre dimensiones. La validación online comprueba disponibilidad, no dimensión; por eso estas dimensiones deben declararse manualmente cuando se quiera validar o documentar la compatibilidad.

## Tagging, scoring y deduplicación

| Variable          | Tipo     | Valor por defecto        | Descripción                                                                                                                                       |
| ----------------- | -------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| TAG_SCORING_DEDUP | Booleano | true                     | Activa el pipeline combinado de etiquetado, puntuación y deduplicación de fragmentos. agentes_deportesmad/.env.example                            |
| DEDUP_UMBRAL      | Decimal  | 0.93                     | Umbral de similitud coseno a partir del cual dos fragmentos se consideran duplicados y se descarta uno de ellos. agentes_deportesmad/.env.example |
| DEDUP_AUDIT       | Booleano | true                     | Genera un registro de auditoría por cada par descartado durante la deduplicación. agentes_deportesmad/.env.example                                |
| DEDUP_AUDIT_RUTA  | Ruta     | output/dedup_audit.jsonl | Archivo JSONL donde se registra cada descarte: métrica de similitud, chunk afectado y fragmento vencedor. agentes_deportesmad/.env.example        |

> Las consultas que fallen durante la generación del eval set se omiten sin interrumpir el indexado completo.

## ChromaDB

| Variable          | Tipo     | Valor por defecto          | Descripción                                                                                                             |
| ----------------- | -------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| CHROMA_DIR        | Ruta     | ./output/chromadb          | Directorio persistente donde ChromaDB almacena la base de datos vectorial. agentes_deportesmad/.env.example             |
| COLLECTION_NAME   | Cadena   | deporte_municipal          | Nombre de la colección ChromaDB utilizada por el proyecto. agentes_deportesmad/.env.example                             |
| QUESTION_SET      | Booleano | true                       | Genera un conjunto de preguntas asociadas a los embeddings tras completar el indexado. agentes_deportesmad/.env.example |
| MAX_QUESTIONS     | Entero   | 2                          | Número máximo de preguntas generadas por embedding. agentes_deportesmad/.env.example                                    |
| QUESTION_SET_RUTA | Ruta     | ./output/question_set.json | Ruta del archivo JSON con el conjunto de preguntas generado. agentes_deportesmad/.env.example                           |

## Ejemplo de configuraciones

### Todo local con Ollama

```text
EMBED_PROVIDER="ollama"
TAG_PROVIDER="ollama"
GEN_PROVIDER="ollama"

OLLAMA_BASE_URL="http://127.0.0.1:11434"
OLLAMA_EMBED_MODEL="qwen3-embedding:0.6b"
OLLAMA_TAG_MODEL="qwen3:8b"
OLLAMA_GEN_MODEL="qwen3:8b"

RAG_RETRIEVAL_MODE="hibrido"
CHUNK_SIZE=1000
CHUNK_OVERLAP=120
TOP_K=5
MAX_CHUNKS=5
```

### Google Gemini como único provider

```text
EMBED_PROVIDER="google"
TAG_PROVIDER="google"
GEN_PROVIDER="google"

GOOGLE_API_KEY="TU_API_KEY"
GOOGLE_EMBED_MODEL="gemini-embedding-2"
GOOGLE_TAG_MODEL="gemini-3.6-flash"
GOOGLE_GEN_MODEL="gemini-3.6-flash"

VISON_MODEL="gemini-2.5-flash"
```

> Se pueden combinar providers sergún conveniencia, aunque se recomiendan Ollama y HuggingFace (en inferencia local) para desarrollo offline y pruebas.

## Recomendaciones operativas

- No subir .env al repositorio; mantener únicamente .env.example con valores no sensibles.
- Un cambio de modelo de embedding ha de ir acompañado de una reindexación de vectores.
- Verificar que EMBED_DIM no supere la dimensión nativa del modelo seleccionado.
- Ajustar CHUNK_SIZE, TOP_K y MAX_CHUNKS según la longitud típica de los documentos y la calidad de las respuestas observadas.
- Activar DEDUP_AUDIT y RAG_CON_DIAGNOSTICO durante las fases de validación; desactivarlos o moderarlos en producción si generan demasiado volumen de salida.