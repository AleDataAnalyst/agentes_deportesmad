# RAG documental

El pipeline está implementado en `rag.logic.responder(pregunta, top_k=None)`.
La tool pública `agentes.tools.rag.rag_preguntar` conserva respuesta, fuentes,
abstención y error. El servicio utiliza la puerta pública documental
`obtener_grafo_documental().invoke` mediante el adaptador existente.
Ver [montaje real, pruebas y bloqueos](../docs/specs/integracion_real.md).

Instalar desde la raíz en el entorno virtual del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py --modo real
```

La configuración está en `rag/config.py`, con carga opcional de `.env`.
`EMBED_PROVIDER`/modelo/dimensión deben corresponder al índice; `GEN_PROVIDER`
y su modelo controlan la generación. El ejemplo `.env.example` contiene
valores distintos de algunos defaults: revisarlos con el responsable.

Se requiere una colección existente en `CHROMA_DIR`/`COLLECTION_NAME`, con
`chroma.sqlite3` y documentos. La consulta no crea colecciones ni índices;
si falta almacenamiento devuelve `RAG_INDEX_MISSING`. No hay ingesta al arrancar.
El indexador offline está en `rag/pipeline.py`; su interfaz se consulta con
`python -m rag.pipeline --help`. Antes de una ingesta manual, confirmar corpus,
proveedor/modelo y dimensiones con el responsable; no se ha ejecutado aquí.

`python -m scripts.smoke_real` ejecuta hasta cuatro consultas sintéticas
documentales, sin dobles, y comprueba el ciclo HITL. La salida distingue una
llamada real con error de una respuesta recuperada y generada correctamente.
Las evaluaciones completas de corpus en pytest requieren `--run-rag-eval`;
la ejecución normal de tests no las lanza.
