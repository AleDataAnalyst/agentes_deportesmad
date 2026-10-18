# Integración de especialistas reales

Revisión del 18/10/2026. Rama local `integration/especialistas-reales`, creada
desde `feature/supervisor-grafo` en `e36b563`. No se han hecho merges, pushes
ni cambios de ramas de compañeros.

## Estado de Git contrastado después del fetch

Se ejecutó `git fetch origin --prune`. El sandbox requirió permiso de escritura
para `FETCH_HEAD`; se repitió con permiso y terminó correctamente.

| Referencia | Estado observado |
|---|---|
| `origin/develop` y `develop` | `6e60890`, PR #4 documental integrada; coinciden, sin fast-forward pendiente |
| Rama inicial y su remoto | `e36b563`, sin divergencia, siete commits sobre develop |
| `origin/feature/especialista-documental` | `0420402`, ya ancestro de develop; no se repite su integración |
| `origin/feature/instalaciones-avisos` | `d8c168a`, herramienta privada CKAN y documentación, fuera de develop |
| `origin/feature/streamlit-ui` | `c6052b3`, presentación y callbacks provisionales, fuera de develop |
| PR #5 | Abierta y `merged=false`; base develop `6e60890`, head `e36b563` |

Los siete commits existentes de la rama inicial se conservan. Develop ya es
ancestro del HEAD inicial, por lo que incorporarlo otra vez no aportaría cambios.
No ha sido necesario un worktree ni mover archivos: no había integración Git
pendiente que entrase en conflicto con el árbol modificado.

Se conservan fuera de los commits de esta entrega los cambios previos de
`README.md`, `docs/specs/coordinacion_fase_integracion.md`,
`docs/specs/golden_graph.md`, `docs/specs/revision_entorno_rag.md`,
`output/debug_trace.diff`, `tests/data/` y `tests/test_golden_graph.py`.
La prueba golden local se incluye en la verificación cuando se ejecuta toda la
carpeta tests; esto no convierte ese trabajo previo en parte de esta entrega.
No se encontraron archivos `AGENTS.md` aplicables en el repositorio o sus ancestros.

## Montaje ejecutable y alcance

`agentes.runtime.crear_servicio_real()` construye un `AgentService` con:

- Documental: `obtener_grafo_documental()` de Héctor → método `invoke` →
  `crear_adaptador_documental` → `specialist_results['documental']`.
- Instalaciones: declaración explícita de capacidad no disponible, sin datos
  ficticios ni llamadas HTTP. No se presenta como especialista funcional.
- Síntesis: `sintetizar` determinista ya existente, con fuentes, restricciones,
  errores y abstenciones. Aplicación: `aplicar` real ya existente, cierre
  informativo; ninguna reserva, pago o acción externa.

Pasar `invoke` no lo ejecuta durante la construcción. El pipeline se carga al
consultar. El adaptador existente mantiene respuesta, fuentes, errores,
abstención, limitaciones, eventos y `request_id` nuevo por pedido. No escribe
decisiones del supervisor ni aprobación. No se copia el especialista ni el RAG.

El grafo supervisor continúa siendo el principal: supervisor, router,
especialistas, síntesis, FINISH, checkpointer y
`interrupt_before=['aplicar']`. `resolver_plan` escribe la decisión booleana
mediante `update_state` y reanuda con `invoke(None)`. Las guardias se aplican
una sola vez en `build_graph`; el montaje recibe las implementaciones concretas.

El supervisor conserva su política determinista actual; no se añade un LLM de
enrutamiento. El estado y los checkpoints viven en memoria del proceso.

### Instalaciones: bloqueo del contrato ejecutable

En develop y la rama inicial, `agentes/nodes/instalaciones.py` y
`agentes/tools/externa.py` eran documentación sin implementación ejecutable.
La rama de Miguel añade `_consultar_catalogo_ckan()` y su normalización privada,
pero no publica una función de consulta ni implementa el nodo. Los avisos HTML
y fallback fechado figuran en contratos y documentación, sin ejecución vigente.
`scripts/probar_api_municipal.py` es un diagnóstico separado de ocupación; no
constituye la interfaz pública del catálogo o del especialista.

Por la restricción de consumir exclusivamente operaciones públicas ya
implementadas, no se importa su función privada ni se copia la herramienta.
Se necesita que Miguel publique la operación/contrato. Hasta entonces el nodo
devuelve `status='abstained'`, `available=False` y una limitación explícita.
No elige un centro ni inventa filtros. No hay integración HTTP certificada.

### Clientes y procedencia

CLI y Streamlit usan `crear_servicio(modo='real'|'demo')`. Solo una petición
explícita selecciona la demo. Los errores del montaje real no cambian de modo.

La UI conserva el diseño de David de `origin/feature/streamlit-ui@c6052b3`:
sidebar, chat, componentes HITL y debug. Se incorporan sus componentes
identificando el origen en comentarios; se reemplazan el hilo fijo
`demo-simulado` y los toast de simulación por llamadas al servicio. Se añaden
los imports de componentes que faltaban. Su rama no se modifica ni se mergea.

La instancia del servicio, hilo y mensajes permanecen en `session_state` entre
reruns. Una nueva conversación utiliza `nueva_conversacion`; no hay caché global.
La entrada de chat queda bloqueada durante HITL. Los botones resuelven el plan
vigente con `True`/`False`; los errores se muestran sin fabricar respuestas.
La síntesis presenta fuentes y limitaciones, y el componente HITL muestra el plan.
La CLI conserva igualmente una sola instancia y bloquea pedidos incompatibles.

## Entorno y arranque

Se reutiliza `.venv`, Python 3.14.2, inicialmente solo con pip. La resolución
completa de `requirements-dev.txt` terminó correctamente con ese intérprete:
no se cambió Python ni se rebajaron los mínimos del RAG. Streamlit y dotenv se
declaran para que el arranque sea reproducible; los paquetes se instalan dentro
de `.venv`, sin modificar el Python global.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe main.py --modo real
.\.venv\Scripts\python.exe -m streamlit run app.py
```

CLI: `/aprobar`, `/rechazar`, `/nueva`, `/salir`. Se lee la decisión humana,
sin autoaprobar. Demo explícita: `main.py --modo demo` o abrir Streamlit con
`?modo=demo` en una sesión nueva. El modo se fija durante la sesión para
evitar mezclar mensajes simulados y reales. `python -m agentes.demo` mantiene
la demostración histórica independiente.

La configuración del RAG sigue en `rag/config.py`: proveedores de embeddings
y generación, modelos, directorio Chroma y colección deben corresponder al
índice preparado por Héctor. No basta con copiar `.env.example`: algunos
valores de ese ejemplo difieren de los defaults del código.
Solo se inspecciona la presencia de claves; nunca se imprime `.env` ni tokens.
No se cambia silenciosamente proveedor ni modelo para superar las pruebas.

Se requiere un índice existente con `chroma.sqlite3` y colección poblada,
creado con el mismo modelo y dimensión de embeddings. La consulta usa
`get_collection`, no `get_or_create_collection`; si falta el almacenamiento,
devuelve `RAG_INDEX_MISSING` sin crearlo. No se ejecuta indexación en esta entrega.
Se actualiza también `rag/README.md`, que todavía describía un cascarón vacío;
el indexador implementado está en `rag/pipeline.py`. El responsable debe confirmar corpus,
modelo, dimensiones y rutas antes de ejecutar manualmente una ingesta.

## Correcciones acotadas verificadas

- `REGISTRY` es un diccionario: se reprodujo el `AttributeError` del
  `monkeypatch.setattr`; sus cinco pruebas usan ahora `setitem`.
- Se reprodujo sobre la función original que presupuesto cero generaba una
  llamada sin limitación; se conserva ahora cero, sin convertirlo al default.
- Constructor HuggingFace: se reprodujo `NameError: name 'modules' is not
  defined`; usa ahora el modelo seleccionado y los kwargs device/token ya
  preparados. Su regresión usa un constructor doble y no descarga modelos.
- Se confirmó que ambas suites RAG abrían Chroma durante colección. Ahora la
  evaluación requiere `--run-rag-eval`, y la fixture abre el índice al ejecutar,
  nunca al recoger. Las pruebas de forma usan un doble explícito.
- Las 22 evaluaciones siguen duplicadas entre `test_tools.py` y
  `test_tool_rag.py`; se conservan sus aserciones, incluidas fuentes esperadas,
  y ambas quedan opt-in. Consolidarlas queda para Héctor; no se ejecutaron.

No se han cambiado retrieval, BM25, chunking, embeddings o prompts para mejorar
calidad. El cambio de apertura del índice únicamente evita crearlo al consultar.

## Verificación reproducible

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-integracion tests
.\.venv\Scripts\python.exe -m scripts.smoke_real --output docs/specs/evidencia_integracion_real.json
```

La primera orden excluye por defecto las 44 evaluaciones de corpus, sin
eliminarlas. La segunda es una prueba explícita real, hasta cuatro llamadas
documentales con el mismo ejemplo sintético identificado: aislado y ciclo HITL.
No hace ingestas, no reemplaza funciones y no registra consultas privadas.
Un perfil cuenta entradas a las funciones originales de tool, pipeline y
retrieval. Código de salida 2 distingue una ejecución con error/abstención de
una recuperación y generación satisfactorias (salida 0).

Las pruebas de `test_runtime.py` y de clientes usan un montaje mixto explícito:
grafo documental, adaptación, supervisor, síntesis y aplicar reales; solo la
tool RAG es doble. Comprueban conservación del sobre, pausa antes de aplicar,
aprobación, rechazo, idempotencia, plan antiguo, nuevo pedido, aislamiento,
traza sin duplicaciones y errores/abstenciones visibles. No acreditan un RAG real.

Resultado completo: **317 passed, 44 skipped**, en 43,55 s. Las 44 omisiones
son las dos baterías de 22 evaluaciones opt-in; no se ejecutaron consultas de
corpus en pytest. Hubo tres avisos de deprecación de dependencias, sin fallos.
`pip check`: `No broken requirements found`. La compilación Python también pasó.
Las ejecuciones transitorias mientras pip todavía copiaba paquetes fallaron
por módulos aún ausentes; la verificación final se hizo con la instalación
completa. Se corrigieron en las nuevas pruebas de cliente la ruta absoluta de
AppTest y el punto de monkeypatch; no se debilitaron sus aserciones.

| Categoría | Evidencia y límite |
|---|---|
| a) Unitarias sin modelos/red | Contratos, estado, supervisor, adaptador y regresiones de compatibilidad; incluidas en los 317 éxitos |
| b) Integración con dobles | Grafo supervisor y componente documental reales, tool RAG doble explícita; fuentes no vacías, errores, abstención y ciclo HITL verificados |
| c) RAG real aislado e integrado | Cuatro entradas a `rag.logic.responder`, `recuperar_hibrido` y `obtener_coleccion`; sin dobles. Las cuatro devuelven `RAG_INDEX_MISSING` |
| d) HTTP municipal real | No ejecutado: no hay operación pública del especialista integrada; no se atribuye el diagnóstico separado de Miguel al servicio |
| e) Clientes | AppTest verifica reruns, HITL y errores con montaje mixto explícito; CLI verificada con ese montaje y además con un pedido real, error del índice visible y aprobación informativa |

El [informe JSON](evidencia_integracion_real.json) registra las entradas a
funciones originales mediante `sys.setprofile`, sin monkeypatch. La consulta
aislada, aprobación y rechazo en pedidos separados, siguiente pedido,
rechazo de plan antiguo, idempotencia, traza e aislamiento se ejecutaron con
el servicio real. El error queda en `specialist_results` y la síntesis lo
presenta; la CLI real lo confirmó. Los callbacks de síntesis/aplicar no usan dobles.

**Bloqueo exacto:** `Error recuperando contexto: RAG_INDEX_MISSING: falta el
índice Chroma configurado`. Falta `output/chroma_db/chroma.sqlite3` con los
defaults actuales. No existe `.env` local y la configuración efectiva conserva
embeddings y generación `ollama`; las claves GOOGLE_API_KEY y HF_TOKEN no están
presentes. No se cambió al modelo/proveedor del ejemplo ni se consultó otro índice.
No se ejecutaron embeddings ni generación: el retrieval se detuvo antes.
La presencia de fuentes reales y la calidad de las respuestas siguen sin
certificar. El ciclo HITL funciona también con el resultado de error; aprobar
solo cierra un plan informativo, no convierte el error en evidencia útil.

Versiones directas instaladas y contrastadas:

```text
Python 3.14.2; langgraph 1.2.11; pytest 8.4.2; streamlit 1.66.0;
python-dotenv 1.2.4; google-genai 2.31.0; numpy 2.5.4; chromadb 1.5.9;
sentence-transformers 6.1.0; torch 2.14.1; langchain-core 1.6.12;
langchain-text-splitters 1.1.3; langchain-community 0.4.2; nltk 3.10.3;
rank-bm25 0.2.2; faiss-cpu 1.15.1; requests 2.34.2; pypdf 6.21.1;
langchain-ollama 1.1.0.
```

LangGraph emitió además avisos sobre tipos dataclass del checkpoint y su
compatibilidad futura. La deserialización y el ciclo HITL funcionan con la
versión instalada; no se ha modificado el serializador en esta integración.

## Commits preparados

1. Compatibilidad: `agentes/nodes/documental.py`, `agentes/tools/rag.py`,
   `rag/embed.py`, `rag/retrieve.py`, `tests/test_node_documental.py`,
   `tests/test_tool_rag.py`, `tests/test_tools.py`, `tests/conftest.py`,
   `tests/test_rag_compatibility.py`.
2. Montaje y clientes: `agentes/runtime.py`, `agentes/documental_adapter.py`, `agentes/nodes/instalaciones.py`,
   `clientes/cli.py`, `clientes/streamlit_app.py`, `clientes/hitl.py`,
   `clientes/debug.py`, `app.py`, `main.py`, `requirements.txt`.
3. Pruebas y documentación: `tests/test_runtime.py`, `tests/test_clients.py`, `tests/test_import_boundaries.py`,
   `scripts/smoke_real.py`, este documento, evidencia JSON, actualización de
   `integracion_grafo_documental.md`, `handoff_backend_integracion.md` y borrador
   de PR y `rag/README.md`. Los archivos locales previos se dejan fuera.

Se propone actualizar la PR #5 al llevar estos commits a su rama de origen,
o abrir una nueva hacia develop desde esta rama si se mantiene separada.
El texto está en [borrador de PR](pr_integracion_real.md); no se publica
ni modifica ninguna PR automáticamente.
