# Handoff: Especialista documental y multimodal

- **Fecha:** 2026-10-28
- **Autor/a:** Héctor González Lebredo
- **Rama / PR:** `feature/especialista-documental` a `develop`
- **Estado:** listo para revisión
- 
## 1. Objetivo

Implementar el especialista documental con capacidades de recuperación sobre documentación municipal y descripción multimodal de imágenes.

El módulo responde consultas relacionadas con el Deporte Municipal del Ayuntamiento de Madrid a partir de documentación curada: centros deportivos, horarios, características, competiciones, instalaciones, estación estival y otros contenidos oficiales.

El objetivo principal no es únicamente generar texto, sino devolver información **trazable, verificable y segura**:

- Cada respuesta debe incluir fuentes recuperadas del corpus documental.
- Si no hay evidencia suficiente, el sistema debe declarar abstención.
- Si falla la recuperación, la indexación o la consulta, el sistema debe devolver un error controlado.
- El agente no debe confundir un fallo técnico con una respuesta válida o una abstención.

Flujo general:

```text
pedido
  → supervisor
  → especialista documental / RAG
  → síntesis
  → HITL
  → aplicar
```

## 2. Alcance implementado

| Componente | Estado | Archivos principales | Comprobado con |
|---|---|---|---|
| Nodo documental | Implementado | `agentes/nodes/documental` | pytest, demo y prueba manual |
| Tool RAG | Implementada | `rag/`, `tests/test_tool_rag.py` | pytest y evaluación con índice cuando está disponible |
| Indexación del catálogo | Implementada | `rag/pipeline` | pytest, demo y prueba manual |
| Adaptador documental | Implementado | `tests/test_documental_adapter.py` | pytest |
| Frontera de errores RAG | Implementada | `tests/test_rag_error_boundary.py` | pytest |
| Transporte de imagen por pedido | Implementado en backend | `AgentService`, adaptador documental | `tests/test_image_por_pedido.py` con dobles |
| Visión multimodal | Pendiente de aceptación real | Módulo de visión / nodo documental | Caso de imagen no disponible cubierto en tests |
| Suite específica de visión | Pendiente | `tests/test_tool_vision.py` | No implementada |
| Índice RAG reproducible | Pendiente | `rag/config.py`, `rag/pipeline` | Requiere índice real, configuración y checksum |

## 3. Contrato expuesto

### 3.1 Entrada

El especialista documental recibe una solicitud estructurada desde el grafo del agente.

Campos esperados:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `query` | `str` | Sí | Consulta del usuario o instrucción derivada por el supervisor |
| `request_id` | `str` | Sí | Identificador único de la petición para evitar respuestas desalineadas |
| `thread_id` | `str` | Sí | Identificador de conversación o hilo de ejecución |
| `plan_id` | `str` | Condicional | Identificador del plan cuando la ejecución está asociada a HITL |
| `options` | `dict` | No | Parámetros opcionales de recuperación, límites de fuentes o diagnóstico |
| `image_id` | `str \| None` | No | Referencia validada a una imagen asociada al pedido actual |

### 3.2 Contrato de imagen

El backend ya transporta `image_id` por pedido hasta la puerta pública documental. La visión no es una ruta independiente del grafo: la imagen entra a través del especialista documental.

`image_id` admite:

- `str`: ruta relativa a la raíz del repositorio o ruta absoluta a un archivo existente en `output/imagenes/`.
- Extensiones permitidas: `.jpg`, `.jpeg` o `.png`, sin distinguir mayúsculas.
- `assets/imagen_demo.jpg`, también accesible mediante el alias `imagen_demo`.
- `None`: indica que el pedido no incluye imagen.

No se aceptan URLs, bytes, base64, rutas arbitrarias ni otros archivos de `assets/`.

Un pedido posterior sin imagen debe reiniciar el campo a `None`. El cliente debe dejar de enviar la referencia anterior cuando no corresponda al pedido nuevo. El campo permanece en el checkpoint del pedido hasta su próximo reinicio; el historial y la traza no reciben la imagen.

Errores presentables:

| Código | Significado |
|---|---|
| `IMAGE_ID_INVALID` | Se recibió algo distinto de texto no vacío o `None` |
| `IMAGE_PATH_FORBIDDEN` | Ubicación no autorizada, traversal o enlace externo |
| `IMAGE_UNSUPPORTED` | Extensión distinta de JPG/JPEG/PNG |
| `IMAGE_NOT_FOUND` | La referencia autorizada no es un archivo existente |
| `IMAGE_UNAVAILABLE` | No se pudo resolver o comprobar el archivo |

La validación autoriza la referencia, pero no acredita el contenido completo de la imagen. No se abre ni codifican bytes en `AgentService`.

### 3.3 Salida

La tool RAG devuelve un diccionario controlado:

```python
{
    "respuesta": "...",
    "fuentes": [...],
    "abstained": False,
    "error": None
}
```

El adaptador documental convierte ese resultado en un `ToolResult` compatible con el grafo:

```python
ToolResult(
    ok=True,
    data={
        "respuesta": "...",
        "fuentes": [...]
    },
    sources=[...],
    abstained=False,
    error=None
)
```

### 3.4 Semántica de los campos

| Campo | Significado |
|---|---|
| `ok` | Indica si la operación se completó correctamente |
| `data` | Contenido útil devuelto por la tool |
| `respuesta` | Texto o estructura generada a partir de la evidencia recuperada |
| `fuentes` | Documentos, fragmentos o metadatos que sustentan la respuesta |
| `abstained` | Indica que no hay evidencia suficiente para responder |
| `error` | Describe un fallo técnico controlado |
| `sources` | Fuentes normalizadas para trazabilidad en el `ToolResult` |

### 3.5 Reglas de comportamiento

- Una consulta sin resultados suficientes debe devolver `abstained=True`.
- Un timeout o fallo de conexión debe devolver `error`, nunca una respuesta inventada ni una abstención.
- Un error interno de la tool debe normalizarse como `error`, sin lanzar excepción hacia el grafo.
- El nodo documental debe preservar fuentes, abstención, limitaciones y eventos.
- El adaptador debe validar el `request_id` antes de aceptar la respuesta.
- El sistema no debe usar la demo como fallback automático del modo real.
- Una entrada de imagen inválida no debe ejecutar especialistas ni modificar el checkpoint.

## 4. Arquitectura y decisiones de diseño

### 4.1 Pipeline documental

```text
Documentos municipales
  - limpieza y normalización
  - chunking
  - embeddings
  - índice vectorial
  - recuperación semántica
  - validación de fuentes
  - respuesta estructurada
```

La recuperación actual es semántica sobre el índice vectorial. Si se introduce recuperación híbrida con BM25 y RRF, deberá documentarse como un cambio de diseño y validarse con pruebas específicas.

### 4.2 Decisiones de diseño

| Decisión | Valor actual | Justificación |
|---|---|---|
| Corpus | Documentación municipal curada | Reduce ruido y mejora trazabilidad |
| Chunking | Configurable en `rag/config.py` | Permite adaptar tamaño y solapamiento al tipo de documento |
| Embeddings | Configurables mediante entorno | Permite sustituir el modelo sin cambiar el contrato |
| Vector store | Chroma / índice compatible | Almacena embeddings y metadatos de fuentes |
| Recuperación | Búsqueda semántica sobre el índice | Devuelve fragmentos relevantes con fuente |
| Imagen | `image_id` validado por pedido | Evita arrastre de imágenes entre conversaciones |
| Salida | Contrato estructurado | Facilita integración segura con el agente |

### 4.3 Trazabilidad

Cada respuesta debe poder relacionarse con:

- Consulta original.
- Fragmentos recuperados.
- Documento o fuente de origen.
- Estado de abstención o error.
- Identificador de petición.
- Referencia de imagen, cuando aplique.

Esto permite auditar por qué el agente respondió de una determinada manera.

## 5. Puntos de conexión

| Consumidor | Punto de integración | Qué debe hacer |
|---|---|---|
| Alejandra / runtime | `crear_servicio(modo="real")` | Utilizar el montaje real del servicio y validar la aceptación conjunta con RAG |
| David / Streamlit | `AgentService.procesar_turno(..., image_id=...)` | Enviar `image_id` por pedido, conservar `thread_id` y `plan_id`, y mostrar fuentes, abstenciones y errores |
| Héctor / RAG | Adaptador documental e índice | Entregar un índice compatible, reproducible y una consulta de aceptación |
| Supervisor / grafo | Nodo documental | Invocar la tool y propagar `ToolResult` |
| HITL | Estado del grafo | Usar fuentes, abstención y errores como evidencia para revisión humana |

La aceptación con recursos reales debe realizarse de forma conjunta con Alejandra. No se considera aceptación real una respuesta generada por demo, un doble de prueba o un error controlado.

## 6. Instrucciones de ejecución

### 6.1 Preparación del entorno

```console
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completar las variables necesarias en `.env` sin subir valores sensibles al repositorio.

### 6.2 Ejecución de pruebas

```console
python -B -m pytest -q -p no:cacheprovider \
  tests/test_tool_rag.py \
  tests/test_rag_error_boundary.py \
  tests/test_node_documental.py \
  tests/test_documental_adapter.py \
  tests/test_image_por_pedido.py
```

Para ejecutar la batería completa contra un índice real, hacerlo de forma aislada y con una configuración explícita. No ejecutar toda la suite contra un índice real por accidente.

### 6.3 Variables de entorno

Referenciar únicamente `.env.example`. No incluir claves, tokens, rutas privadas ni índices generados.

| Variable | Uso |
|---|---|
| `RAG_*` | Configuración de embeddings, índice y recuperación |
| `LLM_*` | Configuración del modelo de generación, si aplica |
| `CHROMA_*` | Configuración del almacén vectorial |
| `LOG_LEVEL` | Nivel de logging |

## 7. Evidencias y límites

### 7.1 Evidencia de pruebas

Comandos ejecutados:

```console
python -B -m pytest -q -p no:cacheprovider \
  tests/test_tool_rag.py \
  tests/test_rag_error_boundary.py \
  tests/test_node_documental.py \
  tests/test_documental_adapter.py \
  tests/test_image_por_pedido.py
```

Resultado esperado:

- Todas las suites seleccionadas deben pasar.
- La tool RAG debe devolver un diccionario controlado con `respuesta`, `fuentes`, `abstained` y `error`.
- Los fallos técnicos deben representarse como `error`.
- El nodo documental debe conservar fuentes, abstención, limitaciones y eventos.
- El adaptador debe validar el `request_id` y convertir el sobre documental en `ToolResult`.
- El transporte de `image_id` debe validarse sin ejecutar visión real.

### 7.2 Cobertura por capas

| Capa | Archivo de prueba | Alcance |
|---|---|---|
| Tool RAG | `tests/test_tool_rag.py` | Contrato público, consulta vacía, fallo interno, diagnóstico opcional y evaluación con índice |
| Frontera de errores RAG | `tests/test_rag_error_boundary.py` | Normalización de `TimeoutError` y `ConnectionError` como error controlado |
| Nodo documental | `tests/test_node_documental.py` | Contrato del nodo, fuentes, abstención, presupuesto de tools, contexto permitido y error de tool |
| Adaptador documental | `tests/test_documental_adapter.py` | Conversión del sobre documental a `ToolResult`, validación de `request_id`, aislamiento del estado y opciones |
| Imagen por pedido | `tests/test_image_por_pedido.py` | Validación de `image_id`, transporte hasta el documental, reinicio entre pedidos, aislamiento y ciclo HITL |
| Integración simulada | `tests/test_golden_graph.py`, `tests/test_export_evidence.py` | Recorridos completos con especialistas dobles; no validan RAG ni visión reales |

### 7.3 Limpieza de pruebas

Casos conservados:

- Contrato de salida de la tool RAG.
- Consulta vacía.
- Error interno.
- Diagnóstico opcional.
- Evaluación contra índice cuando está disponible.
- `TimeoutError` y `ConnectionError` en la frontera de errores.
- Contrato y aislamiento del nodo documental.
- Conversión y validación en el adaptador documental.
- Validación y transporte de `image_id`.
- Reinicio de imagen entre pedidos.
- Ciclo HITL con imagen mediante dobles.

### 7.4 Límites de la evidencia

Esta evidencia no acredita:

- Recuperación semántica real sobre el corpus municipal completo.
- Calidad de generación con un LLM real.
- Índice Chroma poblado y compatible con la configuración de embeddings empleada.
- Visión multimodal real.
- Rendimiento bajo carga o con documentos de gran volumen.
- Persistencia duradera del historial conversacional.
- `preparar_reporte`, que permanece en `None`.

## 8. Pendientes y criterio de cierre

| Pendiente | Responsable | Criterio de aceptación |
|---|---|---|
| Índice RAG reproducible | Héctor | Entregar modelo/proveedor efectivo, dimensión de embeddings, ruta, colección, versiones, URL de descarga y checksum |
| Validación con índice real | Héctor y Alejandra | Consulta con fuente esperada, consulta sin evidencia con abstención y fallo controlado verificados |
| Suite de visión multimodal | Héctor | `tests/test_tool_vision.py` cubre imagen válida, inexistente, formato no soportado e ilegible |
| Integración de visión real | Héctor y equipo | La imagen llega al documental mediante el contrato acordado y la evidencia visual no se confunde con normativa |
| Conexión cliente con imagen | David | Streamlit envía `image_id` por pedido y muestra fuentes, abstenciones y errores sin exponer secretos |
| Aceptación conjunta | Héctor, Alejandra y David | Recorrido real con RAG, fuentes, abstención, error controlado e HITL |

## 9. Decisiones abiertas

| Decisión | Opciones | Impacto | Responsable de decidir |
|---|---|---|---|
| Renombrar `specialist` a `next_node` | Mantener / renombrar | Contrato y consumidores del grafo | Equipo |
| Historial conversacional en estado | Cliente / estado común | CLI y Streamlit | Equipo |
| Modelo de embeddings definitivo | Local / remoto | Calidad de recuperación, coste y despliegue | Equipo RAG |
| Estrategia de reranking | Sin reranking / cross-encoder | Precisión de recuperación y latencia | Equipo RAG |
| Recuperación híbrida | Semántica / BM25 + RRF | Cobertura de consultas, complejidad y latencia | Equipo RAG |

## 10. Riesgos y para no hacer

- No aprobar automáticamente un plan HITL.
- No convertir un error técnico en evidencia.
- No convertir un error en abstención.
- No activar el modo demo como fallback del modo real.
- No aceptar URLs, bytes ni base64 como `image_id`.
- No arrastrar una imagen de un pedido anterior a un pedido nuevo.
- No subir `.env`, claves, índices ni volcados completos de estado.
- No cambiar el contrato de la tool sin revisión de los consumidores.
- No responder sin fuentes cuando la consulta requiere evidencia documental.

## 11. Checklist de aceptación

- [ ] El módulo se ejecuta con los comandos documentados.
- [ ] El contrato de entrada y salida está definido.
- [ ] La tool RAG devuelve `respuesta`, `fuentes`, `abstained` y `error`.
- [ ] Los errores técnicos se normalizan como `error`.
- [ ] Las abstenciones se distinguen de los errores.
- [ ] El nodo documental actualiza únicamente su campo autorizado del estado.
- [ ] El adaptador valida el `request_id`.
- [ ] El contrato de `image_id` está documentado y validado con pruebas.
- [ ] Hay pruebas específicas de la integración documental y de imagen.
- [ ] Se separan evidencias simuladas y reales.
- [ ] El índice RAG es reproducible e incluye metadatos de integridad.
- [ ] La visión multimodal tiene pruebas específicas o queda documentada como pendiente.
- [ ] El README y este handoff están actualizados.