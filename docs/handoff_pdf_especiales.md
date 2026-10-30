# Handoff — Corrección de ingesta de PDF especiales

## 1. Estado al cierre de la sesión

| Documento | Estado | Continuación |
|---|---|---|
| `PiscinasAireLibre2026.pdf` | Se da por resuelto el trabajo de extracción tabular de esta sesión. | No reabrir salvo que aparezca un fallo concreto de integración. |
| `PreciosPublicos2026.pdf` | Pendiente. No se ha conseguido una extracción tabular fiable. | Detener aquí y retomarlo en una tarea separada, sin bloquear el resto del proyecto. |

Distinción importante: el extractor de piscinas se probó dentro de la ejecución completa del pipeline, se ha probado mínimamente su respuesta correcta, pero no ha sido probado intensivamente.

## 2. Contexto del problema

La investigación comenzó al observar descartes de deduplicación que eliminaban contenido distinto: instalaciones de distritos diferentes, páginas de normativa y fragmentos relacionados, pero no necesariamente equivalentes.

Para los PDF especiales se identificó un problema anterior a la deduplicación: la estructura de las tablas no estaba llegando correctamente a los documentos usados para generar embeddings.

Los dos archivos están registrados en `data/corpus/especiales.txt`:

```text
PiscinasAireLibre2026.pdf: TAB
PreciosPublicos2026.pdf: TAB
```

El manifiesto describe un tratamiento tabular directo como `key-value`, pero la implementación examinada pasa por Markdown y posteriormente vuelve a interpretar sus filas.

## 3. Archivos examinados

| Archivo | Papel en el flujo |
|---|---|
| `pdf_tabular.py` | Extracción tabular y OCR de PDF especiales. |
| `load.py` | Enrutamiento de archivos y creación de `Document`. |
| `dedup.py` | Deduplicación por políticas exactas o por similitud semántica. |
| `scoring.py` | Cálculo de `semantic_score`, centralidad y redundancia. |
| `logic.py` | Pipeline de consultas; no requiere cambios para esta corrección de ingesta. |
| `especiales.txt` | Declaración de los PDF que necesitan tratamiento especial. |

## 4. Piscinas: problema identificado y solución

### Defectos observados

La extracción predeterminada de `pdfplumber` produjo:

- Página 1: 54 filas y 6 columnas.
- Página 2: 27 filas y 6 columnas.

La tabla real tiene cuatro columnas:

```text
Distrito
Centro Deportivo Municipal
Dirección
Fechas
```

Además:

- El código tomaba la primera fila como cabecera, aunque contenía el título del documento.
- La extracción separaba algunos distritos de las celdas correspondientes a centro, dirección y fechas.
- Los saltos de línea internos de las celdas podían romper el Markdown intermedio.
- Los documentos tabulares se creaban sin `dedup_policy` ni `row`, por lo que terminaban en la deduplicación semántica.

### Extractor específico implementado

Se proporciona `extraer_piscinas()` para añadir a `pdf_tabular.py`, con esta configuración:

```python
{
    "vertical_strategy": "explicit",
    "explicit_vertical_lines": [22.2, 142, 312, 455, 573.7],
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
}
```

El extractor:

1. Busca la cabecera real.
2. Ignora el título y subtítulo como filas de datos.
3. Normaliza espacios y saltos de línea dentro de cada celda.
4. Valida que cada registro contenga cuatro valores no vacíos.
5. Devuelve filas estructuradas, sin Markdown intermedio.

Estas coordenadas corresponden al diseño de piscinas; no deben reutilizarse como configuración genérica para otros PDF.

### Conexión facilitada para `load.py`

Se proporcionaron los cambios necesarios para:

1. Importar `extraer_piscinas`.
2. Añadir `_load_piscinas_tabular()`.
3. Invocarlo desde `_load_pdf()` antes del tratamiento genérico y fuera de su fallback.

Metadata propuesta:

```python
{
    "content_type": "table_row",
    "dedup_policy": "exact_only",
    "page": numero_pagina,
    "table": numero_tabla,
    "row": indice_fila,
    "extracted_row": posicion_en_tabla_extraida,
}
```

La normalización de fuente y el hash del archivo se realizan mediante `_normalizar_source()`. `cargar_archivos()` ya asigna `doc_id`.

Si posteriormente se valida la integración, comprobar:

- Que el chunking mantiene las filas completas.
- Que conserva `dedup_policy`, `row`, `page` y `table`.
- Que las filas no entran en deduplicación por coseno.
- Que se han sustituido los chunks antiguos en el índice.

Estas comprobaciones no quedaron ejecutadas durante la conversación.

## 5. Precios: trabajo detenido y limitación explícita

### Comprobaciones realizadas

`PreciosPublicos2026.pdf` contiene una página de gran formato, de aproximadamente 3401 × 4110 puntos, y 18 objetos de imagen.

Las pruebas con `pdfplumber` y `pypdf` recuperaron principalmente:

- El título.
- La descripción de los servicios.
- La referencia al acuerdo plenario y su modificación.

No recuperaron los conceptos e importes de las tarifas como texto nativo.

Se confirmó que las tarifas tampoco se pueden seleccionar y copiar desde el visor del PDF.

### Exploración realizada

Se exploraron ejemplos para:

- Renderizar y recortar una región.
- Extraer una imagen original incrustada sin redimensionarla.
- Pasarla a Tesseract desde el entorno local.

> Ejemplos y muestras adjuntos en [docs/investigación/diagnostico_pdf](./investigacion/diagnostico_pdf)

### Decisión de cierre

No continuar con precios ni piscinas en esta sesión.

Mantenerlo como tarea separada y no permitir que bloquee el resto del proyecto.

Hasta disponer de una solución validada:

- No considerarlo correctamente procesado.
- No indexar sólo su encabezado como sustituto de las tarifas.
- No presentar el OCR ni la extracción tabular como implementados.
- No aplicar el perfil geométrico de piscinas a este archivo.
- Si el pipeline actual lo procesa, identificar explícitamente su resultado como incompleto o excluirlo de la indexación, según se decida al implementar esa gestión.

Las alternativas para una futura tarea son OCR con reconstrucción tabular validada o una fuente alternativa estructurada.

## 6. Aclaraciones sobre deduplicación y scoring

Se corrigieron varios diagnósticos iniciales durante la investigación:

- El número inicial del par descartado procede del producto escalar calculado mediante `FAISS IndexFlatIP`.
- Sólo puede interpretarse como similitud coseno si los vectores están normalizados.
- El `score` mostrado junto a la pareja ganadora es su `semantic_score`, no la similitud entre ambos chunks.
- No se ha demostrado un fallo de caché, reutilización de vectores o desalineación entre documentos y embeddings.
- Los snippets del informe no permiten, por sí solos, conocer todo el contenido del chunk.

No aplicar como solución de este problema los primeros parches propuestos de longitud mínima y Jaccard: no corrigen la estructura tabular perdida y no quedaron validados como cambio integrado.

En particular, uno de los ejemplos iniciales de clasificación desviaba las políticas exactas a `passthrough`, saltándose su deduplicación por clave; no debe copiarse tal cual.

## 7. Observaciones técnicas para futuras tareas

Fuera del alcance del cierre actual:

- `load.py` puede degradar un PDF declarado TAB a extracción nativa tras un error. Conviene evitar que ese fallback oculte una extracción incompleta.
- Cuando `cargar_archivos()` recibe sólo rutas de archivos individuales, la implementación examinada no consulta el manifiesto mediante el mismo recorrido que usa para directorios.
- El procesamiento por lotes de especiales puede seguir ejecutando el extractor genérico sobre piscinas aunque su carga individual utilice el perfil específico.
- `scoring.py` calcula redundancia incluso para documentos con políticas exactas. Evitar su descarte semántico no elimina automáticamente esa penalización del score.
- Si la reindexación se decide sólo por el hash del PDF, un cambio de extractor puede requerir forzar el reprocesado aunque el archivo no haya cambiado.

## 8. Punto de continuidad

Dejar precios documentados como extracción no resuelta y trabajos detenidos, sin nuevas iteraciones exploratorias en esta tarea.
