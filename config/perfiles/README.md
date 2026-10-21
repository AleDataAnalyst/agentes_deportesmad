# Perfiles y sonda pequeña de etiquetado RAG

Preparación del 20/10/2026, separada del cierre de supervisor/grafo. No modifica el RAG de Héctor, clientes, dependencias ni pruebas ajenas. Las únicas validaciones de esta entrega usan dobles explícitos, sin llamadas a Ollama, corpus completo, embeddings ni Chroma.

## Qué representa cada plantilla

| Selección | Modelo TAG | Ejecución de la sonda | Límites TAG |
| --- | --- | --- | --- |
| `ligero` | `qwen2.5:3b` | Código real `etiquetar` y `_chat_ollama`, aislado | Timeout fijo 120 s; contexto/salida/temperatura heredados de Ollama |
| `27b_acotado` | `smtek/Qwen3.8-27B:Q2_K_XL-16gb` | **Experimental**, solicitud independiente `/api/chat` | Contexto 4096, máximo 512 tokens, temperatura 0, timeout de prueba 300 s |
| `hector` | `smtek/Qwen3.8-27B:Q2_K_XL-16gb` | Código real `etiquetar` y `_chat_ollama`, aislado | Timeout fijo 120 s; parámetros heredados del modelo instalado |

`ligero` aligera únicamente TAG: **mantiene el generador 27B**. No es una configuración completa de bajo consumo. `27b_acotado` no es un perfil operativo del adaptador actual: sus límites solo los aplica esta sonda. `hector` es una proyección de `.env.example` sobre opciones con consumidor real en la rama Ollama; omite secretos, otros proveedores, supervisor y declaraciones sin uso. `EMBED_TIMEOUT=600` recoge el valor predeterminado del código, no una declaración adicional del ejemplo.

Los tres perfiles conservan el mismo generador, corpus de referencia `data/corpus`, embeddings `qwen3-embedding:0.6b`, dimensión 1024, lote 50, chunking 1000/120 y parámetros de scoring/deduplicación. El corpus no se carga: se usan los tres textos sintéticos existentes, copiados literalmente en [benchmark_rag_tag_casos.json](../../scripts/benchmark_rag_tag_casos.json). Ruta/colección de las plantillas son contexto de configuración, **no destinos que abra la sonda**.

## Selección y ejecución en PowerShell

Desde la raíz, con la `.venv` existente. No instalar paquetes, copiar plantillas a `.env` ni cambiar variables de entorno para estos comandos.

Validación local sin red ni mediciones reales de hardware/modelos:

```powershell
& .\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil ligero 27b_acotado hector --doble
```

Los siguientes comandos son para una fase posterior, **no se han ejecutado como parte de esta entrega**. Hacen tres llamadas reales de etiquetado por perfil; no indexan:

```powershell
& .\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil ligero
& .\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil 27b_acotado
& .\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil hector
```

Comparación posterior de los tres perfiles, secuencialmente y en ese orden:

```powershell
& .\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil ligero 27b_acotado hector
```

La selección es obligatoria; no hay perfil predeterminado ni opción implícita «todos». Cada perfil se ejecuta en un proceso nuevo y termina antes de iniciar el siguiente. Las constantes de configuración no se reutilizan. Se rechazan nombres/variables desconocidos y perfiles repetidos. El `.env` del usuario no se lee ni se escribe: la plantilla se carga explícitamente en el entorno exclusivo del hijo, sin heredar variables RAG, credenciales o proxies del padre. No se cambian variables globales del sistema.

Código de salida 0: los tres casos pasan (o pasan los dobles, si se usa `--doble`). Código 2: fallo, resultado pendiente de revisión humana o error de preflight. Los dobles no acreditan calidad ni velocidad de ningún modelo.

## Parámetros con efecto real

| Parámetro/consumidor | Efecto actual | Cobertura de la sonda |
| --- | --- | --- |
| `TAG_PROVIDER`, `OLLAMA_TAG_MODEL` | Selección del adaptador y modelo | Sí; proveedor Ollama y modelo instalado obligatorios |
| `OLLAMA_BASE_URL` | Endpoint común de Ollama | Sí; se restringe a `http://127.0.0.1:11434`, sin credenciales |
| Timeout TAG | Literal `120` en `_chat_ollama`; no tiene variable `.env` | Sí, sin alterarlo en `ligero`/`hector` |
| `BENCH_TAG_TIMEOUT=300` | Solo lo lee la sonda | Experimental; no cambia TAG ni `GEN_TIMEOUT` |
| `BENCH_TAG_NUM_CTX=4096`, `BENCH_TAG_NUM_PREDICT=512`, `BENCH_TAG_TEMPERATURE=0` | Solo los lee la sonda y envía `options` | Experimental; el adaptador TAG actual no envía esas opciones |
| `BENCH_MODE` | Selección de vía de la sonda | Solo sonda; no lo consume `rag.config` |
| `GEN_TIMEOUT`, `GEN_TEMPERATURE` | Generador Ollama: timeout y `options.temperature` | No se hace generación RAG; temperatura conserva el default 0.2 del código |
| `GEN_MAX_TOKENS`, `TAG_MAX_TOKENS` | Ollama no los aplica en los adaptadores actuales | **Omitidos de las plantillas**; declararlos no impondría límite alguno |
| `EMBED_PROVIDER`, `OLLAMA_EMBED_MODEL`, `EMBED_DIM`, `EMBED_BATCH_SIZE`, `EMBED_TIMEOUT` | Embeddings: modelo, dimensión, lotes y timeout; recorte/renormalización cliente | Se registran y se comprueba instalación del modelo; no se generan embeddings |
| Chunking, `TAG_SCORING_DEDUP`, `DEDUP_UMBRAL`, auditoría, exportación, recuperación y destino Chroma | Consumidores reales en `chunk`, `pipeline`, `scoring`, `dedup`, `retrieve`, `index` | Mismos valores de referencia en los perfiles; no se ejercitan ni se abre almacenamiento |

`HF_DEVICE=cuda` no controla Ollama. Se omiten opciones HF/Google y claves. `EVAL_SET*` no tiene consumidor en el código revisado; `QUESTION_SET*` y `MAX_QUESTIONS` solo aparecen declarados en `rag.config`, sin ejecución que los use en el pipeline presente. También se omiten. El texto `data/corpus` es una referencia documentada; no se inventa una variable `CORPUS_DIR` que el RAG no consume.

`load_dotenv()` en `rag.config` carga el `.env` encontrado y no sobrescribe variables del proceso; sus constantes se fijan al importar. Los adaptadores importan esas constantes por valor. Por eso editar variables después de importar no basta para comparar perfiles.

La importación normal de `rag` ejecuta su `__init__` y arrastra `logic`, `pipeline`, `index` y Chroma. Para evitarlo, la sonda carga **el mismo archivo fuente** `rag/tsd/tag.py` bajo un paquete de módulos aislado, con su `config.py` y desactivando la carga automática de dotenv únicamente durante esa importación. No se cambian esos archivos. Las vías `adapter` llaman a sus funciones originales; solo se observa el transporte HTTP para conservar respuestas y parámetros. Esto valida TAG aislado, no la importación pública ni el pipeline entero. La vía experimental comparte prompt/parser/taxonomía pero no se presenta como validación del adaptador.

## Calidad y evidencias

Las categorías y etiquetas de referencia están definidas manualmente en el JSON de casos. Los grupos de etiquetas justificables, claramente injustificadas y para revisión son disjuntos y cubren la taxonomía actual; una modificación de taxonomía obliga a revisar los casos. `horario` para un plazo de cancelación queda en **revisión humana**; `empadronado` para el catálogo de instalaciones es claramente injustificado.

Cada resultado separa JSON estricto válido, aceptación del parser real, esquema/relevancia, taxonomía, categoría, respaldo semántico, necesidad/uso de valores de respaldo, truncamiento y completitud de respuesta. Los defaults silenciosos por campos ausentes también se detectan. Una etiqueta ambigua produce `human_review`; no se acepta automáticamente. JSON malformado, prosa alrededor del JSON, salida truncada, fallback, categoría errónea o etiqueta injustificada impiden aprobar el caso, incluso si el adaptador termina sin excepción.

Se conserva el contenido original y el razonamiento que devuelva Ollama, el objeto interpretado, metadatos del adaptador y métricas numéricas. Los errores se guardan por tipo/estado HTTP, sin cuerpos ni mensajes que puedan incluir rutas o credenciales. Las constantes no JSON (`NaN`, infinitos) se rechazan; si aparecen en un resultado interpretado se serializan como marcadores explícitos, conservando el texto original.

Cada ejecución crea `tmp/benchmark_rag_tag/<fecha-UTC>_<identificador>/` con creación exclusiva, sin sobrescribir evidencias. Contiene un JSON por llamada, uno por perfil y `resumen.json`. Los tiempos UTC pueden corresponder al día anterior al de Madrid. Se registran:

- Perfil, modo experimental/real, parámetros enviados y timeout efectivo; hashes de plantilla, casos, prompt y fuentes de TAG/configuración.
- Modelo/digest/tamaño/cuantización del inventario, versión de Ollama, parámetros declarados de TAG mediante `/api/show` cuando se consulta en modo real, commit y estado de trabajo con cambios (sin rutas de archivos).
- GPU NVIDIA, VRAM total/usada/libre, RAM total/disponible cuando se pueden medir; si faltan herramientas, se registra `null`. No se guardan hostname, usuario, seriales ni UUID de GPU.
- Estado residente de los modelos antes de cada llamada (`/api/ps`); si no se puede comprobar, se marca desconocido. Primera llamada del perfil distinguida de las siguientes, sin asumir que es una carga fría.
- Tiempo observado por llamada, métricas de carga/evaluación/generación devueltas por Ollama en nanosegundos/tokens, total del trabajador y tiempo completo del subproceso en el resumen. El tiempo de llamada incluye la función/parseo; excluye el monitoreo previo de hardware/modelos. El total del trabajador excluye sus importaciones iniciales; `process_seconds` las incluye.

La sonda comprueba que los tres modelos seleccionados (embeddings, generación y TAG) están instalados antes de inferir. No descarga modelos. No envía `keep_alive`, órdenes de descarga de memoria, `think`, ni formato JSON forzado. Ollama puede gestionar por sí mismo la residencia al cargar un modelo: se registra el estado, no se fuerza una condición fría ni se promete no interferencia de recursos. Otras tareas, cachés, orden de perfiles y cargas limitan las comparaciones; no atribuir las diferencias exclusivamente al tamaño del modelo. Un timeout no confirma que el servidor haya liberado de inmediato la tarea.

## Equipo y antecedentes

El equipo de referencia tiene RTX 3060 de 6 GB y 64 GB RAM. No se deduce que el 27B quepa íntegramente en GPU ni que su nombre `16gb` garantice ajuste. El inventario anterior indicaba Q4_K_S pese al tag Q2_K_XL; se registra la cuantización real disponible, no se infiere del nombre.

Las evidencias anteriores mostraron que el 27B acotado a 4096/512 y temperatura 0 devolvió etiquetas respaldadas en tres casos, con 152.985, 120.619 y 196.163 s, pero usó timeout de prueba de **600 s**, distinto de los 300 s de esta plantilla. El 3B produjo categorías válidas pero una etiqueta injustificada y otra discutible. Estos antecedentes motivan el diseño, **no son resultados de estos nuevos perfiles**. No se ha ejecutado aún su comparación real ni probado recuperación/calidad sobre el corpus completo.

## Propuesta concreta para Héctor (pendiente de coordinación)

1. Hacer configurable un timeout específico de TAG, por ejemplo `TAG_TIMEOUT`, conservando 120 s como default compatible.
2. Añadir opciones específicas y opcionales de TAG, por ejemplo `OLLAMA_TAG_NUM_CTX` y `OLLAMA_TAG_NUM_PREDICT`, validadas como enteros positivos antes de enviarlas en `options`.
3. Aplicar de forma efectiva los límites declarados: traducir `TAG_MAX_TOKENS` y `GEN_MAX_TOKENS` a `num_predict` en Ollama, acordando precedencia si existe un override específico. Documentar que el razonamiento también puede consumir el presupuesto y detectar truncamiento/contenido vacío.
4. Acordar la temperatura de TAG, validación de esquema/taxonomía y tratamiento observable de fallbacks antes de considerar operativo un perfil acotado. Mantener los contratos públicos y validar con Héctor los cambios.

Esta entrega **no implementa** esa propuesta. Aumentar el timeout solo permite esperar más; no acelera el procesamiento. Cambiar TAG puede cambiar categorías, etiquetas, relevancia, scoring y los ganadores de deduplicación. No mezclar resultados como si fueran el mismo índice. Un índice se consulta con el mismo modelo, dimensión y configuración de embeddings con que se construyó; un cambio exige gestionar un índice compatible distinto.

## Validación de esta entrega

Pasaron tres procesos independientes con `--doble`, nueve respuestas principales simuladas y 15 comprobaciones de calidad/fallos por perfil, con sockets bloqueados. Se verificaron los payloads enviados, el timeout 120 frente a 300, la ausencia de opciones añadidas en la vía del adaptador, la distinción primera/siguientes llamadas, el estado residente simulado y la generación de evidencias nuevas. También se comprobó que omitir `--perfil` falla y que variables RAG/credenciales de prueba en el padre no se filtran al hijo. Los textos coinciden exactamente con las evidencias anteriores.

Se conservaron los hashes de los 146 archivos preexistentes comprobados, incluido `.env`. No se ejecutaron llamadas reales, la comparación completa de modelos ni indexación. El código de TAG se cargó sin importar Chroma. Las evidencias locales de validación están bajo `tmp/benchmark_rag_tag/` y `tmp/preparacion_benchmark_rag_20261020/`; no se proponen para el commit. Los tiempos y metadatos marcados `simulated=true` no describen hardware ni modelos reales.

## Archivos para un commit independiente (no realizado)

Solo estos seis archivos, sin incluir `.env`, `tmp/`, diagnósticos previos ni el cierre de supervisor/grafo:

```text
config/perfiles/rag_ligero.env.example
config/perfiles/rag_27b_acotado.env.example
config/perfiles/rag_hector.env.example
config/perfiles/README.md
scripts/benchmark_rag_tag.py
scripts/benchmark_rag_tag_casos.json
```
