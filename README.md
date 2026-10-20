# agentes_deportesmad

Project Break 02 · Asistente de deporte municipal con agentes y LangGraph.

El proyecto integra el RAG existente mediante un especialista documental y un supervisor síncrono. El flujo conserva fuentes, errores y abstenciones, prepara un plan informativo y exige una decisión humana antes del cierre.

## Estado de esta entrega — 20/10/2026

Esta entrega incorpora la CLI sobre `AgentService` y las protecciones del backend compartido. Distingue implementación, pruebas con dobles y validación con servicios reales.

| Componente | Implementado y comprobado | Límite actual |
| --- | --- | --- |
| Supervisor y grafo | Rutas, fallback, límite de iteraciones y nodos inyectados | Supervisor por reglas; proveedor de rutas inyectable, sin router LLM conectado en runtime |
| Servicio común | `AgentService`, conversaciones, estado y planes identificados | Estado y decisiones en memoria del proceso; sin recuperación tras reiniciar |
| Montaje documental | Puerta pública documental conectada mediante adaptador en `runtime.py` | Recuperación y generación reales pendientes de un índice compatible |
| Síntesis y aplicar | Síntesis determinista, plan informativo y pausa antes de aplicar | No realiza reservas, pagos ni envíos |
| Revisión humana (HITL) | Aprobar/rechazar, mismo hilo, plan vigente e idempotencia | La aprobación no certifica la veracidad de la evidencia |
| Instalaciones | Ruta y declaración explícita de ausencia en runtime | Falta una operación pública ejecutable del especialista; `available=False` |
| CLI | Consultas, fuentes, plan, aprobación/rechazo manual, nueva conversación y debug acotado | Modo real pendiente de aceptación con un índice compatible; memoria limitada al proceso |
| Seguridad del backend | Validación de campos por nodo, aislamiento de entradas/salidas y registro explícito de tipos del checkpoint predeterminado | No añade autenticación, persistencia duradera ni aislamiento de efectos externos de código Python |
| Streamlit | Cliente demo sobre `AgentService`, chat y controles HITL | Pendiente de conectar a runtime real; después de decidir necesita un refresco adicional para recuperar el chat |
| Perfiles y benchmark TAG | Tres plantillas y sonda independiente; validación con dobles | Sin comparación completa real de estos perfiles ni validación del pipeline |
| Visualización | Exportación ASCII/Mermaid y esquema SVG | Describe topología y montaje; no acredita una consulta RAG real |

La conexión documental está implementada y sus pruebas de montaje están superadas. La aceptación documental real necesita un índice poblado, compatible con embeddings y una consulta cuya fuente esperada pueda verificarse. Son estados distintos; no se presenta el backend como un producto completo.

## Montaje y contratos

`agentes/runtime.py` conecta `obtener_grafo_documental().invoke` mediante `crear_adaptador_documental`. La construcción del servicio pasa el callable sin ejecutar una consulta. Un error del modo real nunca activa una demo.

El recorrido principal es:

```text
pedido → supervisor → documental → supervisor → instalaciones → supervisor
       → síntesis → supervisor → pausa antes de aplicar
       → decisión humana sobre el plan vigente → aplicar → END
```

El supervisor puede usar rutas alternativas, fallback y límites. La ausencia actual de instalaciones se comunica como abstención y limitación explícitas.

El adaptador conserva el sobre documental en `ToolResult.data` y las referencias confirmadas en `Evidence.source`, sin inventar fragmentos, puntuaciones ni fechas. Los errores no se convierten en evidencia útil; sus fuentes permanecen en los eventos correspondientes. La respuesta vacía sin error se trata como abstención. La tool pública expone respuesta, fuentes, abstención y error; no se afirma que propague todos los campos adicionales del RAG.

La pausa ocurre antes de `aplicar`. El cliente resuelve con el mismo `thread_id`, un booleano explícito y el `plan_id` vigente. Se rechazan planes antiguos y nuevos pedidos incompatibles con una decisión pendiente. Repetir la misma resolución es idempotente; rechazar limpia la propuesta y los resultados operativos y conserva la traza. Un nuevo pedido reinicia sus datos operativos.

El servicio, sus checkpoints y sus identificadores se conservan entre turnos durante la vida del proceso. No constituyen persistencia duradera.

Referencias: [cierre del montaje](docs/specs/cierre_montaje_documental_2026-10-20.md), [cierre del backend](docs/specs/cierre_backend_supervisor_grafo.md), [síntesis y aplicar](docs/specs/sintetizar_aplicar.md) y [contratos](docs/specs/contratos.md).

## Ejecutar la demo sin servicios externos

Desde la raíz del repositorio, con un entorno que tenga las dependencias del backend instaladas. Los siguientes comandos usan la `.venv` local existente; no instalan paquetes ni requieren modelos o un índice:

```powershell
.\.venv\Scripts\python.exe -m agentes.demo
.\.venv\Scripts\python.exe -m agentes.demo --interactivo
.\.venv\Scripts\python.exe -m agentes.demo --escenario abstained
.\.venv\Scripts\python.exe -m agentes.demo --escenario error
```

La salida identifica los datos como simulados. El comando sin decisión muestra el plan pendiente. El modo interactivo pide aprobar, rechazar o salir y no aprueba por defecto. `--decision aprobar` y `--decision rechazar` permiten recorridos automatizados de demostración; no representan una decisión humana capturada por una UI.

## Ejecutar la CLI

`main.py` delega en `clientes/cli.py`. Para probar el cliente sin servicios externos:

```powershell
.\.venv\Scripts\python.exe -B main.py --help
.\.venv\Scripts\python.exe -B main.py --modo demo
.\.venv\Scripts\python.exe -B main.py --modo demo --debug --mensaje "Consulta simulada"
.\.venv\Scripts\python.exe -B main.py --menu
```

`--help` no construye el servicio. `--menu` permite elegir demo o real sin selección automática y no se combina con `--modo`. Sin esas opciones, el modo predeterminado es `real`; un error real no activa una demo. Para usar el montaje documental, una vez preparado el entorno y recibido un índice compatible:

```powershell
.\.venv\Scripts\python.exe -B main.py --modo real
```

La selección de modo no cambia proveedores, modelos ni `.env`, ni descarga o genera índices. El montaje real mantiene instalaciones como no disponibles.

| Entrada interactiva | Operación |
| --- | --- |
| Texto | Consulta en la conversación actual |
| `/aprobar` o `/rechazar` | Decisión manual sobre el hilo y el plan mostrados |
| `/estado` | Consultar el estado actual |
| `/debug` | Mostrar diagnóstico acotado, sin volcar el estado completo |
| `/nueva` | Crear otro hilo con el mismo servicio, sin plan pendiente |
| `/ayuda` o `/salir` | Mostrar comandos o terminar la sesión |

Los comandos también funcionan sin barra; `nuevo` y `/nuevo` equivalen a `/nueva`. `--mensaje` siempre se interpreta como texto de consulta. Mientras haya un plan pendiente se bloquean nuevas consultas y el cambio de conversación. Tras un error se exige consultar `/estado` antes de volver a consultar o decidir; `/nueva` también comprueba el estado antes de cambiar de hilo. No hay reintentos ni decisiones automáticas. Salir, EOF o Ctrl+C terminan sin aprobar ni rechazar.

La CLI admite hasta 8.000 caracteres por entrada, rechaza controles y formato invisible, limpia secuencias de terminal y filtra credenciales reconocibles en la salida. El filtrado es heurístico y no garantiza ocultar cualquier secreto. Comprueba el hilo, el estado HITL y el plan antes de permitir una decisión.

Streamlit se inicia con `.\.venv\Scripts\python.exe -m streamlit run app.py` y actualmente usa el servicio demo. La integración del modo real y los ajustes de presentación pendientes pertenecen al trabajo de su cliente.

## Protecciones del backend compartido

Los especialistas reciben una copia del estado y solo pueden actualizar su resultado y eventos de traza. Los campos desconocidos, resultados incompatibles y cambios de otro rol se rechazan antes de fusionar el patch. Las salidas se copian para evitar referencias mutables compartidas con el nodo.

Síntesis y aplicar validan sus campos permitidos y conservan las guardias HITL. El cierre no puede sustituir el plan ni sus resultados por otros tras la decisión humana. El proveedor de rutas recibe una copia independiente del estado, incluso si falla. El checkpoint predeterminado registra explícitamente los cuatro tipos internos del contrato; los checkpoints inyectados conservan su configuración.

Estas comprobaciones validan contratos de código Python. No aíslan efectos externos de un callable ni certifican resistencia semántica a prompt injection. Los identificadores de hilo y plan coordinan el flujo; no autentican usuarios.

## Ver el grafo

```powershell
.\.venv\Scripts\python.exe -m scripts.ver_grafo
Start-Process .\docs\specs\grafo_visual.svg
```

El script muestra ASCII en terminal y genera:

- `docs/specs/grafo_actual.txt`: dibujo ASCII de la topología.
- `docs/specs/grafo_actual.mmd`: topología Mermaid.
- `docs/specs/grafo_visual.svg`: esquema del montaje y sus límites.

La exportación compila la demo con el mismo `build_graph`, sin ejecutar pedidos, consultar modelos ni importar el RAG. ASCII puede variar en disposición o trazos; Mermaid permite revisar las conexiones. `grandalf` figura en las dependencias de desarrollo. El SVG es la imagen explicativa mantenida.

Ver [explicación de la vista](docs/specs/grafo_visual.md) y [flujo de supervisor y grafo](docs/specs/flujo_supervisor_grafo.md).

## Pruebas y evidencias

| Comprobación | Resultado documentado | Alcance |
| --- | --- | --- |
| Selección conjunta de CLI y backend | 433 pruebas superadas en 9,72 s | CLI, seguridad, servicio, runtime, fronteras de importación, supervisor, síntesis, HITL, adaptación, golden, demo y exportación; con red y RAG/Chroma bloqueados por el ejecutor local |
| Terminal desde `main.py` | Cuatro recorridos con código de salida 0 | Help, demo con aprobación/rechazo y nueva conversación, menú demo y salida del menú |
| Compatibilidad de Streamlit en demo | Aprobación, rechazo y nueva conversación correctos | Conserva servicio, hilo y plan; persiste el refresco adicional de UI después de decidir |
| Selección histórica de backend y montaje | 276 pruebas superadas | Evidencia anterior a esta ampliación, con dobles donde corresponde; no se suma a las 433 |
| Golden del grafo | 12 escenarios y 24 pruebas | Incluido en la selección conjunta; datos y fuentes sintéticos, sin evaluación semántica de un LLM |
| Sonda adicional en la frontera RAG | 10 recorridos superados | Respuesta, abstención, vacío, error y timeout, con aprobación/rechazo; solo se sustituye `responder` |
| Perfiles TAG con `--doble` | Tres procesos independientes y 15 comprobaciones por perfil | Transporte/modelos simulados; no mide rendimiento ni calidad real |
| Revisión de la visualización | 24 pruebas golden superadas; SVG y topología verificados | Comprobación adicional, sin servicios externos; no se suma a las 276 como cobertura nueva |

La sonda histórica de diez recorridos fue inline. Esta entrega añade pruebas reproducibles de errores inmediatos de la tool RAG en `tests/test_rag_error_boundary.py`; no miden un timeout real ni sustituyen aquella sonda completa. Las cifras describen selecciones y ejecuciones locales concretas, no toda la suite ni un resultado de CI; no se suman como coberturas independientes.

Pruebas de CLI y guardias con especialistas dobles, sin índice ni modelos:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_cli.py tests/test_cli_security.py tests/test_node_guards.py tests/test_rag_error_boundary.py
```

Selección breve para comprobar el montaje y la regresión, con pytest instalado:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_runtime.py tests/test_documental_adapter.py tests/test_backend_cierre.py tests/test_golden_graph.py
```

La selección completa de 276 y los bloqueos adicionales de red/Chroma usados por su ejecutor están documentados en el [cierre del montaje](docs/specs/cierre_montaje_documental_2026-10-20.md). No ejecutar toda la suite como sustituto: algunos tests de herramientas/RAG intentan abrir Chroma durante la colección.

Para exportar diez escenarios identificados como simulados:

```powershell
.\.venv\Scripts\python.exe -m scripts.export_evidence --output output/evidencia_backend_simulado.json
```

Los contratos y el golden están versionados. Las evidencias temporales permanecen locales. La demo, los dobles y las pruebas de contratos no validan recuperación, generación, catálogo, imágenes ni calidad sobre el corpus municipal.

## Configuración efectiva y RAG

La configuración del supervisor y la del RAG tienen mecanismos distintos:

- `agentes/settings.py` lee `MAX_ITER` al crear el servicio; valor predeterminado 8. No carga `.env` automáticamente.
- `rag/config.py` carga dotenv sin sobrescribir variables del proceso y fija constantes al importar. Cambiar el entorno después de importar no basta para comparar configuraciones.
- Embeddings, etiquetado (TAG) y generación tienen proveedores/modelos separados. Declarar una variable no garantiza que un adaptador la consuma.

Las [specs de Héctor](docs/specs/contratos.md), en la sección de dependencias del RAG, citan `GEN_PROVIDER`, `GOOGLE_GEN_MODEL` y `GOOGLE_API_KEY` para generación de respuestas con un índice existente, además de las opciones de recuperación. Ese uso de Gemini no genera el índice ni sustituye el etiquetado previo. `GEMINI_MODEL` no tiene consumidor en el código revisado. Una propuesta Google para TAG debe tratarse como una configuración distinta, no como ese uso de GEN.

Para validar el RAG real se necesita un índice compatible con el modelo, dimensión y configuración de embeddings que lo construyeron, su ruta/colección y una consulta con fuente esperada. Cambiar `EMBED_*` o `CHUNK_*` exige gestionar la reindexación indicada en las specs. No subir `.env`, claves, entornos virtuales ni índices pesados. Los ejemplos no certifican disponibilidad de los modelos, cuotas o compatibilidad del entorno local.

### Perfiles y benchmark de etiquetado

| Perfil | Modelo TAG | Parámetros aplicados |
| --- | --- | --- |
| `ligero` | `qwen2.5:3b` | Adaptador aislado, timeout fijo 120 s; opciones heredadas de Ollama |
| `hector` | `smtek/Qwen3.8-27B:Q2_K_XL-16gb` | Adaptador aislado, timeout fijo 120 s; opciones heredadas del modelo |
| `27b_acotado` | Modelo 27B anterior | Llamada experimental independiente: contexto 4096, máximo 512 tokens, temperatura 0 y timeout 300 s |

Los tres mantienen `qwen3-embedding:0.6b`, `EMBED_DIM=1024` y los mismos valores de referencia de corpus, chunking y deduplicación. `ligero` solo aligera TAG: mantiene el generador 27B. El adaptador TAG actual no admite los límites del perfil acotado mediante configuración; no es un perfil operativo completo.

Validación explícita de la sonda sin llamadas reales:

```powershell
.\.venv\Scripts\python.exe -B scripts/benchmark_rag_tag.py --perfil ligero 27b_acotado hector --doble
```

La sonda ejecuta cada perfil en un proceso independiente y en secuencia. No sobrescribe `.env`, descarga modelos ni abre colecciones Chroma. Conserva respuesta original, interpretación, parámetros, métricas y resultados de calidad. JSON válido, taxonomía, coherencia y fallback son comprobaciones diferentes; un fallback no cuenta como clasificación correcta.

La comparación completa real de estos perfiles no se ha ejecutado. Los antecedentes de pruebas aisladas se distinguen de esa validación en [config/perfiles/README.md](config/perfiles/README.md), que contiene comandos, parámetros efectivos, condiciones de medida y propuesta para Héctor.

Aumentar el timeout permite esperar más; no acelera el procesamiento. Cambiar TAG puede alterar metadatos, scoring y deduplicación. Esta entrega no implementa cambios internos del RAG para configurar timeout, `num_ctx`, `num_predict` o los límites de salida declarados.

## Responsabilidades y aceptación pendiente

El reparto parte del acuerdo del 13/10/2026. La siguiente tabla actualiza el estado de esta entrega sin convertir propuestas futuras en asignaciones aceptadas.

| Responsable | Trabajo y estado | Pendiente concreto |
| --- | --- | --- |
| Alejandra | Supervisor, grafo, servicio común, adaptación documental, síntesis, cierre HITL, CLI y protecciones del backend con sus pruebas | Coordinar la aceptación documental real y revisar la integración de los especialistas pendientes |
| Héctor | RAG y especialista documental; su puerta pública está conectada al supervisor | Índice compatible y reproducible, consulta/fuente esperadas y revisión de perfiles; coordinar configuración efectiva de límites TAG/generación |
| Miguel | Especialista de instalaciones y avisos, a partir de su handoff | Operación pública ejecutable y contrato de fuentes, errores, abstención y fallback fechado para integrarla |
| David | Cliente Streamlit demo conectado a `AgentService`, con chat y controles HITL | Integración con runtime real, refresco de UI, tratamiento de errores y presentación segura de fuentes/debug |

El backend de pausa, validación de la decisión y reanudación del grafo pertenece al trabajo de Alejandra y está implementado. Los botones y la presentación de Streamlit corresponden a David. Cada responsable mantiene pruebas y documentos de su bloque. La incorporación de nuevas tareas requiere coordinación explícita.

Para aceptar la integración documental real, Héctor debe facilitar el índice y su configuración reproducible. Después corresponde verificar respuesta con fuente, abstención, fallo y recorrido HITL contra ese recurso. No hace falta inventar otra puerta documental ni añadir código al montaje para simular la existencia del índice.

El cierre completo del PB02 sigue requiriendo dos especialistas reales, clientes ejecutables, herramientas externas/auxiliares y multimodal acordadas, evidencias y aceptación sobre recursos reales. La existencia de docstrings o archivos de estructura base no acredita esas capacidades. Paralelismo, asincronía y persistencia duradera no se presentan como alcance implementado aquí.

## Referencias y flujo Git

- [Handoff de conexiones pendientes y TODO en Python](docs/handoff_cli_backend.md).
- [Seguimiento del PB02](docs/specs/seguimiento_pb02.md).
- [API y handoff del backend](docs/specs/handoff_backend_integracion.md).
- [Contratos de integración](docs/specs/contratos.md).
- [Golden del grafo](docs/specs/golden_graph.md).
- [Handoff de instalaciones para Miguel](docs/decisiones/Handoff_Miguel_Especialista_Instalaciones.md).

`develop` es la rama de integración y `main` la de entrega estable. El trabajo se propone mediante PR con alcance, contrato, comprobaciones y limitaciones. Los cambios de contrato requieren revisión de sus consumidores. Las contribuciones y revisiones individuales se acreditan en Git; esta documentación no sustituye la revisión ni la aceptación de cada entrega.
