# SDD — Cierre posterior a la entrega y consolidación

Fecha de revisión: 27/10/2026 (Europe/Madrid). Estado: **propuesta para revisar**, sin autorización de implementación ni de publicación implícita.

## 1. Objetivo, alcance y referencias

Definir el cierre de los requisitos obligatorios del PB02 y la integración posterior, contrastando mantenimiento, `origin/develop` y la PR #30. Separar implementación, regresión offline y aceptación con recursos reales. Este documento no declara cerrado el PB02.

Esta fase crea únicamente este SDD. No modifica código, tests, configuración, modelos ni índices; no ejecuta inferencias, aceptación externa, commits, push, merges ni modificaciones de PR. No interviene en el principal ni en los worktrees de indexación o revisión de #21.

### 1.1 Fuente de requisitos

Se consultó mediante el conector GitHub el [enunciado PB02, README](https://github.com/AleDataAnalyst/NEWAlejandra_AIEngineeringBootcamp/blob/main/Project_Break/PB_02_Agentes_LangGraph/README.md), blob `defe8eb7ab0be0624ecaca6c0abb96f3a22c9a94`. La consulta actual no prueba que esta versión coincida exactamente con la vigente el día de entrega. La guía HTML enlazada desde [seguimiento_pb02.md](seguimiento_pb02.md) no se volvió a consultar; si hubiera discrepancia, debe aclararse antes del cierre.

Requisitos que gobiernan la matriz:

- R1: supervisor, al menos dos especialistas con prompt propio, síntesis y aplicar con HITL.
- R2: tools reales de cuatro categorías: RAG de magnitud PB1, fuente externa con fallback, auxiliar determinista y multimodal. El LLM propone y Python aplica allowlist y límites.
- R3: límites de iteraciones y llamadas en Python; el LLM no decide por sí solo el cierre.
- R4: MemorySaver y continuidad por `thread_id`; pausa antes de aplicar, aprobación y rechazo humanos en CLI y Streamlit.
- R5: traza visible de supervisor, herramientas y HITL, con diagnóstico comprensible.
- R6: código modular, configuración reproducible, README, ejemplo de entorno y dependencias.
- R7: informe, demostración/presentación conjunta y contribuciones/revisiones acreditadas en Git; PR hacia `develop`.

El enunciado requiere un RAG con corpus curado de al menos dos formatos, carga/chunk/embeddings/índice persistente, recuperación, generación anclada y abstención. No exige repetir toda la evaluación PB1 de 8–15 preguntas. Persistencia duradera entre procesos, paralelismo, reservas, pagos y envíos no se añaden como requisitos de este cierre. SDD es evidencia de metodología; no sustituye funcionalidad.

Referencias locales complementarias: [aceptacion.md](aceptacion.md), [guion_aceptacion_clientes.md](guion_aceptacion_clientes.md), [contratos.md](contratos.md), [registro postentrega](../post_entrega.md), [informe](../../entregables/informe_decisiones.md) y README del proyecto. Algunas describen estados históricos; sus pendientes deben contrastarse con los SHA de esta revisión.

## 2. Base y evidencias

### 2.1 Identidad y estado comprobados

Worktree inspeccionado: `C:/Users/AleEng/Documents/BootcampAIEngineering/RepositoriosTheBridge/agentes_deportesmad/tmp/backend_imagen_por_pedido`.

| Referencia | SHA | Estado y significado |
| --- | --- | --- |
| Entrega histórica, `main` | `18ca29dc22d634ad516ea811b026a93d238468e4` | Base de entrega, PR #28. Conservar como referencia original; no reetiquetar sus evidencias como posteriores. |
| Mantenimiento, `fix/post-entrega-correcciones-tests-mejoras` | `50d984513135700d7acc7bca6a9b41f8897c2d8c` | HEAD comprobado. Worktree limpio antes de crear este archivo. Commit de merge creado por la usuaria; padres `c31518b` y `8a3761d`. |
| Mantenimiento previo | `c31518be54f370c15796f68d6783503fd267fcda` | Correcciones locales posteriores a la entrega, conservadas en el merge. |
| `origin/develop` local | `8a3761dd492d62bbf0e6aa17c0f27499e47581c7` | Contiene #29 y `hora_actual` de Miguel (`6305e24`). `HEAD...origin/develop`: 2 commits exclusivos locales y 0 remotos. |
| [PR #30](https://github.com/AleDataAnalyst/agentes_deportesmad/pull/30), `fix/cierre-pb02 → develop` | head `957adc15cee8ee15f2013d6dbde05ffe3d04b307` | Abierta, no draft, no fusionada; GitHub informa `mergeable=false`. Referencia local `origin/fix/cierre-pb02` coincide con ese head. |
| [PR #31](https://github.com/AleDataAnalyst/agentes_deportesmad/pull/31), `develop → main` | head `8a3761dd492d62bbf0e6aa17c0f27499e47581c7`; base `18ca29dc22d634ad516ea811b026a93d238468e4` | Abierta, no draft, no fusionada; GitHub informa `mergeable=true`. El head confirma el SHA remoto de `develop` comunicado por la API. |

La API de #30 devuelve `base_sha=1f1b824699e573c7073fe9c79f87124e5a1158e6`; no debe confundirse con la punta actual de `develop`, confirmada por #31. La base común de mantenimiento y #30 es `d5ff3b42bf324fafd6031e0ef7b18c5a64f94646`; para revisar la aportación de #30 se usa comparación de tres puntos, no solo una diferencia entre árboles finales.

No se hizo fetch en esta fase. `git ls-remote origin ...` no pudo conectar con GitHub desde el shell; se contrastaron las referencias con las consultas de solo lectura del conector. Los indicadores de fusionabilidad son instantáneos, no una garantía de integración futura. El SHA de merge de prueba que GitHub pueda devolver para #31 no es un commit fusionado en `main`.

Comandos de inspección ejecutados (sin mutación; se usó `-c safe.directory=<ruta>` por la identidad del sandbox):

```console
git status --porcelain=v1 --branch
git rev-parse HEAD
git log -3 --oneline
git show-ref --verify refs/remotes/origin/develop
git show-ref --verify refs/remotes/origin/fix/cierre-pb02
git show 50d9845 --format=fuller --no-patch
git rev-list --left-right --count HEAD...origin/develop
git merge-base HEAD origin/fix/cierre-pb02
git diff --stat origin/develop HEAD
git diff --name-status origin/develop...origin/fix/cierre-pb02
git diff origin/develop...origin/fix/cierre-pb02 -- <archivos revisados>
git diff HEAD origin/fix/cierre-pb02 -- <archivos revisados>
```

Resultado: el mantenimiento difiere de `origin/develop` en 21 archivos; la aportación de #30 ocupa 28 archivos respecto de su base común con `develop`. No son 28 funcionalidades nuevas ni una enumeración de conflictos. Una diferencia entre árboles puede mostrar como eliminación en #30 una corrección local que esa rama nunca recibió.

### 2.2 Qué contiene mantenimiento

- Imports diferidos en API pública RAG, tool RAG y montaje de visión; mantiene inyección de dependencias y construcción sin consultas.
- Normalización RAG dentro del límite de errores; conserva campos de diagnóstico ante fallos.
- Documental valida observación, texto y lista de fuentes; exige éxito sin error ni abstención para admitir evidencia. Registra fallos y rechaza por completo texto con fuentes parcialmente excluidas.
- Imagen independiente del RAG, primero cuando está adjunta y disponible, con presupuesto compartido. `.invoke`, MIME correcto, fuentes de texto, alias demo y lectura de clave al consultar.
- PDF/OCR conserva bloques de texto sin tablas Markdown y procedencia; no sustituye estas regresiones por fixtures que solo tengan tablas.
- Integración real desactivada por defecto, colección sin consultas reales y tests con temporales propios.
- Merge de #29 y `hora_actual` de Miguel; dos regresiones adicionales de fuentes de visión como texto o diccionario `ruta` en el recorrido nodo/adaptador.

### 2.3 Registro de pruebas y límites de la evidencia

**En esta fase documental no se ejecuta pytest.** No se certifica de nuevo la suite ni el entorno de modelos. La validación de esta fase consiste en inspección de fuentes y referencias, revisión del Markdown y comprobación del único archivo creado.

| Evidencia | Comando / origen | Resultado comunicado | Alcance que acredita |
| --- | --- | --- | --- |
| Regresión inmediatamente anterior al commit `50d9845` | Selección reproducida debajo; árbol del merge preparado | 78 passed, 2 deselected, 13 avisos de deprecación, 10,42 s | Siete módulos seleccionados, incluidos tres tests de `hora_actual`; dos casos reales excluidos. No es suite completa, no valida aceptación real ni es una nueva ejecución sobre HEAD en esta fase. El último ajuste posterior fue de comentarios. |
| Primer intento de esa selección | Misma selección sin temporal dedicado | 63 passed, 13 errores de preparación y 2 deselected | Falló al crear temporales por permisos de Windows; no fue un resultado funcional satisfactorio. La repetición con ruta nueva resolvió ese impedimento. |
| Whitespace de la integración preparada | `git diff --check` y `git diff --cached --check` | Sin errores | Formato del diff; no comportamiento. |
| Registro previo de mantenimiento | `docs/post_entrega.md`: `python -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-post-entrega-final` | 863 superadas, 50 omitidas según ese registro | Evidencia histórica posterior a la entrega, anterior a esta consolidación; no reejecutada aquí ni atribuible automáticamente a `50d9845`. |
| Descripción de #30 | `python -B -m pytest -q -p no:cacheprovider --ignore=tests/test_rag_questions.py --ignore=tests/test_tool_rag.py` | Autor comunica 848 passed y prueba manual PNG/JPG en Streamlit | Declaración del autor, con exclusiones explícitas; no reproducida aquí. No acredita compatibilidad con mantenimiento ni es aceptación conjunta de ambos clientes. |
| Descripción de #31 | Cuatro módulos de instalaciones; baseline global comunicado | 26 passed y mismos 15 fallos según autor | Contexto de esa PR, no diagnóstico actual del mantenimiento ni validación del conjunto. |

Selección ejecutada en la fase anterior, desde este worktree, con Python 3.14.2 de `../../.venv/Scripts/python.exe`, pytest 8.4.2, bytecode/caché/plugins automáticos y carga dotenv desactivados. Se invocó `pytest.main` mediante un wrapper temporal por stdin que instalaba un audit hook contra `socket.connect` y `socket.getaddrinfo`; las pruebas de procesos nuevos aportan sus propios bloqueos/dobles. No se guardó un runner en el repositorio:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHON_DOTENV_DISABLED='1'
$testTemp=Join-Path $env:TEMP ('codex-merge-offline-'+[guid]::NewGuid().ToString('N'))
@'
import sys
import pytest
def offline(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo'}:
        raise AssertionError('Red bloqueada durante las regresiones offline')
sys.addaudithook(offline)
raise SystemExit(pytest.main(sys.argv[1:]))
'@ | & ../../.venv/Scripts/python.exe -B - -q -p no:cacheprovider -m 'not integration' --basetemp "$testTemp" --tb=short tests/test_node_documental.py tests/test_imagen_prevista.py tests/test_vision.py tests/test_documental_adapter.py tests/test_hora_actual.py tests/test_smoke_componentes.py tests/test_import_boundaries.py
```

No ejecutar aceptación real por copiar este documento: requiere una fase expresa, recursos preparados y registro propio. Ninguna cifra histórica sustituye una ejecución nueva sobre el SHA final consolidado.

## 3. Matriz de consolidación propuesta

Las pruebas indicadas son criterios futuros: su presencia en la matriz no significa que se hayan ejecutado. «Descartar» se refiere a una alternativa de implementación, no a borrar contribuciones o evidencias de sus autores.

| Requisito / comportamiento | Implementación local | Aportación de #30 | Solapamiento o incompatibilidad | Propuesta | Archivos afectados | Prueba necesaria para aceptar |
| --- | --- | --- | --- | --- | --- | --- |
| R2, imagen de #29 | `.invoke`, fuentes normalizadas, evidencia visual independiente; imagen → RAG | Repite #29 y añade planificación de tools | Reaplicar el arreglo duplica trabajo; reglas de #30 vuelven a RAG → imagen | **Conservar** #29 y orden local por defecto; **adaptar** selección LLM sin perder imagen válida con presupuesto 1 | `agentes/nodes/documental.py`, `tests/test_imagen_prevista.py`, `tests/test_vision.py` | Invocación observada, RAG absteniéndose e imagen útil; fuentes string/dict → adaptador; presupuesto 1 solo imagen, 0 ninguna llamada |
| R2, evidencia útil y fuentes mixtas | Rechaza `ok=False`, error, abstención, texto vacío/incorrecto y observación malformada; omite toda observación con fuentes excluidas | Agrega resultados por tool; filtra fuentes RAG, añade imagen si tiene texto | No conserva todas las validaciones; filtrar solo citas puede mantener texto excluido; imagen no aplica igual filtro | **Conservar** validador y política local, **adaptar** toda salida LLM al mismo límite; no tratar preview o texto libre del modelo como evidencia | `agentes/nodes/documental.py`, `agentes/documental_adapter.py`, tests de ambos | Observaciones malformadas no lanzan; evidencia fallida no aparece; mezcla permitida/privada omite todo texto; error prevalece en status del adaptador sin borrar respuesta parcial válida |
| R3, presupuesto total y fallback | Presupuesto único, decremento por llamada incluso fallida; reglas acotadas | Bucle `max_steps`, bloqueos allowlist y fallback a reglas | Si falla `adapter.generate` tras ejecutar tools, la lista parcial no retorna; el caller puede reiniciar con presupuesto completo. Instalaciones puede consultar fuera del bucle | **Adaptar** con contador y registro preservados durante toda la ejecución, incluido fallback; límites de inferencias separados de llamadas a tools | `agentes/especialista_llm.py` de #30, ambos nodos, `agentes/config.py` | Modelo falla antes/después de una tool; varias propuestas en una respuesta; ninguna duplicación ni llamadas por encima del presupuesto; agotamiento visible; límite 0 no ejecuta tools |
| R5, traza completa | Eventos documental `tool/ok/error/abstained`; debug del adaptador resume status, payload conserva eventos | `args/status/preview/paso` y traza de instalaciones | Documental descarta propuestas bloqueadas/args inválidos si decide fallback; excepción posterior pierde historial parcial; detalle no necesariamente visible en ambos clientes | **Adaptar** registro incremental; **incorporar** nombre, argumentos saneados, estado y preview limitado sin perder fallos/bloqueos | Bucle LLM, nodos, `agentes/documental_adapter.py`, `clientes/`, `app.py` | Bloqueo y fallo siguen visibles tras fallback; orden y número coinciden con intentos; no secretos; no duplicación por rerender o HITL |
| R1–R3, prompts propios y elección LLM | Nodos reales por reglas; existe adaptador LLM genérico/supervisor, pero no demuestra elección de tools por ambos especialistas | `PROMPT_DOCUMENTAL`, `PROMPT_INSTALACIONES`, `Herramienta`, bucle con allowlist y modo `ESPECIALISTAS_MODO` | No basta copiar el bucle: preservar validadores, ruta fijada por Python, restricciones y presupuestos. Default reglas no demuestra el requisito LLM | **Incorporar y adaptar** prompts/bucle de #30, manteniendo reglas como fallback explícito; documentar modo LLM de aceptación | `agentes/especialista_llm.py`, ambos nodos, `agentes/llm*.py`, tests de #30 | Adapter doble elige tools diferentes según escenario; tool no autorizada nunca corre; argumentos inválidos registrados; ruta manipulada no cambia adjunto; prompts y esquemas propios enviados al adapter |
| R2, contrato de `hora_actual` de Miguel | `hora_actual(zona='Europe/Madrid', ahora=None)`; `resultado={iso,fecha,hora,dia_semana,zona}`, `fuentes=['reloj_del_sistema']`; error con `resultado=None`; exportación perezosa y tres tests | Sustituye por `hora_actual()` con `resultado` cadena de `_fecha_actual_iso()` y fuente `reloj del sistema` | Contratos distintos, pérdida de zona explícita/reloj inyectado y nuevas dependencias hacia externa. Test regex de #30 espera cadena | **Conservar** contrato/export/tests locales; **descartar** sustitución de función; **adaptar** consumidores y test de #30 a `resultado.iso` | `agentes/tools/auxiliares.py`, `agentes/tools/__init__.py`, `tests/test_hora_actual.py`, tests LLM de #30 | Igual salida pública existente; hora fija y zona IANA, zona vacía/inválida; import sin red/modelos; ningún consumidor espera cadena en `resultado` |
| R2/R5, conexión de la auxiliar al especialista | Tool disponible pero `nodo_instalaciones` no la llama | Reglas por palabras temporales y tool en allowlist LLM; adjunta resultado a `data.hora_actual` y traza | Solapamiento directo en futura edición de `instalaciones.py`. El reloj no acredita apertura de un centro; el fallback de consulta puede exceder presupuesto LLM | **Adaptar** conexión acotada al contrato de Miguel; primero reglas, después reutilizar desde LLM; reloj y procedencia municipal separados | `agentes/nodes/instalaciones.py`, `tests/test_nodo_instalaciones.py`; después bucle/tests LLM | Pregunta temporal: una llamada con doble y resultado estructurado en data/traza; no temporal: cero llamadas al reloj; fallo no inventa hora ni borra consulta; conserva resultados ajenos y no afirma «abierto» sin horarios/evidencia |
| R6, imports y construcción sin efectos | API RAG y tool diferidas; runtime difiere visión, sin pipeline al construir | Elimina import redundante en `llm.py` y difiere tool dentro de `nodes/vision.py` | Primer arreglo ya local. #30 no incluye todo el aislamiento local; reemplazar archivos por sus versiones reintroduciría imports eager | **Conservar** aislamiento local; **incorporar** import interno de visión solo si suma sin alterar contrato | `rag/__init__.py`, `agentes/tools/rag.py`, `agentes/llm.py`, `agentes/runtime.py`, `agentes/nodes/vision.py` | Procesos nuevos bloquean RAG/Chroma/modelos/red durante imports y montaje; construcción no consulta; ejecución con callable inyectado sigue funcionando |
| R2, errores y diagnóstico RAG | Normalización dentro de try y diagnóstico aun con error | Corrige `requests.ChunkedEncodingError` a `requests.exceptions.ChunkedEncodingError` en dos reintentos de embed | Cambios complementarios; reemplazo global perdería normalización y carga diferida | **Conservar** límite local e **incorporar** corrección puntual de excepción | `agentes/tools/rag.py`, `rag/embed.py`, `tests/test_rag_error_boundary.py`, tests de reintento | Responder devuelve None/fuentes inválidas o lanza → contrato estable; errores de transporte provocados con dobles reintentan hasta tope sin AttributeError ni esperas reales |
| R2, visión | MIME PNG/JPEG/WebP, clave leída por llamada, alias demo, fuentes strings, errores controlados | MIME PNG/JPEG, validación previa a clave, alias; elimina WebP y conserva clave capturada al importar | Buena parte duplicada; tests de #30 parchean constante que ya no es interfaz local. Nodo documental admite JPG/JPEG/PNG, tool directa además WebP | **Conservar** comportamiento local; **adaptar** solo tests/nodo pendientes; no ampliar formatos de entrada en esta fase | `agentes/tools/vision.py`, `agentes/nodes/vision.py`, tests de visión/smoke/imagen | Payload/MIME con proveedor doble, clave cambiada entre llamadas, JSON inválido y proveedor fallido → error/abstención; no simulación exitosa; alias demo estable |
| R2, PDF/OCR y corpus | Conserva texto OCR/TAB sin tablas, bloque y procedencia | Corrige firma `directorio_raiz` y convierte fixtures OCR/TAB en tablas Markdown | Firma ya corregida localmente; fixtures solo de tablas dejan de detectar pérdida de texto plano; #30 no aporta fallback de contenido local | **Conservar** producción/regresiones locales; **incorporar** cobertura Markdown como casos adicionales, no sustitutos | `rag/load.py`, `tests/test_load_ocr.py`, `tests/test_load_pdf_tab.py` | Texto plano no vacío preservado íntegro; tablas producen filas; OCR vacío cae a loader nativo; source/pdf_source/block_index y metadatos esperados; evaluación de bloques mixtos separada |
| R3/R6, configuración y adapters | `MAX_STEPS` duplicado; `run_tool_rag` referencia `GEN_MAX_TOKENS` no definido en config; adapters existentes | Añade `GEN_MAX_TOKENS`, elimina duplicado, normaliza tools planas/anidadas Google/Ollama; documenta modo | Son aportaciones útiles, pero modos/límites deben cubrir fallback total. HuggingFace también existe localmente y requiere definir compatibilidad | **Incorporar** correcciones pequeñas con tests; **adaptar** settings/documentación y compatibilidad por proveedor sin prometer soporte no validado | `agentes/config.py`, `agentes/llm_google.py`, `agentes/llm_ollama.py`, `.env.example`, README | Dobles capturan payload/schema plano y anidado equivalentes, modelo/tokens/timeout y límites válidos; modo inválido diagnosticado; entorno de prueba no activa inferencia |
| R4–R6, tests y clientes | `--run-integration` explícito y marks; tests de recuperación, fuentes, HITL y aislamiento | Fixture autouse fuerza reglas, nuevos tests LLM y capturas manuales | Reemplazar conftest quitaría puerta de integración. Forzar reglas globalmente puede ocultar que modo LLM nunca se prueba | **Conservar** puerta offline; **adaptar** fixture con casos explícitos llm/reglas; **conservar** contrato común de clientes | `tests/conftest.py`, `pytest.ini`, `tests/test_especialistas_llm.py` de #30, tests CLI/Streamlit/backend | Colección sin abrir índice; suite offline con red bloqueada; cobertura de ambos modos; mismo thread/plan, rechazo/aprobación humanos, fuentes/debug visibles y recuperación sin repetir llamadas |
| R6/R7, documentación y evidencias | README, registro postentrega y guion con estados fechados | Ejemplo de entorno, cambios de guion y ocho capturas añadidas | Capturas y cifras corresponden a otras bases; A8 histórico pide reutilizar `_fecha_actual_iso`, distinto del contrato de Miguel ya integrado | **Adaptar** documentación futura y mapear evidencias a SHA/fecha/cliente; **conservar** originales | README, `.env.example`, `docs/specs/guion_aceptacion_clientes.md`, `docs/evidencias/`, informe | Instalación reproducible, comandos reales y contribuciones verificables; cada captura/caso identifica SHA y modo; revisión explícita de divergencia A8 sin cambiar retrospectivamente la entrega |

## 4. Criterios de aceptación observables

### 4.1 Offline con dobles

O1. En cada especialista, un adapter programado recibe su prompt/esquemas y propone tools permitidas. Intentos fuera de allowlist, argumentos no estructurados y excepciones producen eventos, no ejecución arbitraria. El texto final del LLM no sustituye evidencia validada.

O2. Con presupuesto B, el total de tools ejecutadas antes y después de fallback es como máximo B. Definir además tope de propuestas bloqueadas y llamadas a modelo, para que las rechazadas no creen un bucle ilimitado. Probar fallo del modelo antes de la primera tool y después de una tool exitosa; no repetir esa tool ni perder su resultado/traza. El orden por reglas sigue imagen → RAG; cualquier política LLM para imagen con presupuesto 1 debe quedar acordada y probada.

O3. RAG fallido/abstenido no impide imagen útil. Error, `ok=False`, resultado vacío/malformado o fuentes mixtas no autorizadas no se publican como evidencia. Los errores permanecen visibles: el adaptador puede devolver status error conservando respuesta parcial válida; no convertirlo artificialmente en éxito. Las fuentes del adaptador coinciden con las del sobre documental.

O4. `hora_actual` conserva exactamente el contrato de Miguel. La futura conexión almacena el dict estructurado, conserva la fuente del reloj y registra éxito/fallo. Una pregunta temporal no demuestra disponibilidad municipal. Un caso no temporal no llama al reloj en reglas; una llamada LLM debe ser propuesta y autorizada explícitamente.

O5. Importar utilidades, montar servicio o recoger tests no carga modelos ni abre índices. Fallos RAG/JSON/HTTP producen contratos controlados y diagnósticos; payloads de visión y tool schemas se verifican con dobles. OCR/TAB de texto plano sigue presente y atribuible; añadir tablas no elimina esos casos.

O6. CLI/Streamlit conservan fuentes, traza saneada y límites, y usan el mismo contrato del servicio. Antes de decisión: plan vigente, pausa, `approved=None`, `done=False`. Tras decisión humana: aprobación/rechazo coherentes; segundo pedido con mismo hilo y nuevo plan; plan antiguo rechazado; sesiones separadas no se contaminan.

Plan de regresión: selección por cada cambio más pruebas de sus consumidores, seguida de suite offline conjunta sobre SHA consolidado, con integración explícitamente excluida y red bloqueada. Registrar comando, entorno, SHA, selección, passed/skipped/deselected, avisos y causas. No fijar como objetivo conservar una cifra histórica de tests. El filtro `-m 'not integration'` no protege de efectos durante importación: mantener colección segura y bloqueos.

### 4.2 Aceptación con modelos, índice y servicios reales — pendiente

Se ejecutará en una fase posterior autorizada, después de O1–O6 y de preparar recursos; nada de lo siguiente se ejecuta al redactar el SDD:

| Caso | Preparación | Observación exigida |
| --- | --- | --- |
| Supervisor y dos especialistas LLM | Proveedor/modelo disponible y modo documentado | Ruta real, prompts por rol, propuestas y tools ejecutadas identificables, límites efectivos y fallback trazable ante fallo controlado |
| RAG completo | Corpus ≥2 formatos; manifest de fuente/fecha/hash, proveedor/modelo/dimensión/colección/versiones, comando/log de indexación y ubicación | Índice poblado y compatible; consulta in-corpus con respuesta y fuente esperadas; otra fuera de corpus se abstiene con el mismo índice previamente validado; fallo controlado no inventa texto |
| Instalaciones API/fallback | Consulta/centro acordado; fecha de captura y política de caducidad conocidas | Origen api/html y fecha; fallo provoca fallback fechado o limitación si caducado; reloj no se presenta como estado actual de apertura |
| Auxiliar | Consulta temporal acordada, zona declarada | Llamada real al reloj determinista visible en traza/data y resultado estructurado; no requiere inferencia para calcular hora |
| Visión | Imagen PNG/JPG identificada, modelo configurado | Texto visual real y ruta atribuida en ambos clientes; con RAG absteniéndose sigue evidencia visual; aviso de que no acredita normativa; fallo de proveedor visible |
| HITL y recuperación | CLI y Streamlit en modo real, humano presente | A1–A9 del guion contrastados por contrato; aprobación y rechazo manuales, thread/plan antes/después, recuperación sin duplicación ni autoaprobación |

La existencia de `chroma.sqlite3`, una sonda automática o una captura aislada no satisfacen estos casos. Registrar por caso: SHA exacto, fecha/zona, SO/Python/dependencias, comando/modo, proveedor/modelo, red, índice/corpus, entrada, esperado, observado, fuente, dobles (si existen), responsable y artefactos. Las claves se omiten. `smoke_real` no sustituye la decisión humana de A2/A3.

### 4.3 Historia y cierre posterior

Preservar `18ca29d`, informe y capturas originales de la entrega del 25/10/2026. Identificar evidencias posteriores como postentrega con su SHA y fecha, sin sobrescribir la historia. Las de #30 requieren revisar contenido y procedencia; no se validaron visualmente en esta fase. El título de #31 no representa por sí solo todo su diff actual. El cierre exige revisar informe/presentación, tres fallos conocidos, reproducibilidad y aportaciones individuales, además del software.

## 5. Orden de trabajo y dependencias

Cada tarea debe tener diff pequeño, pruebas de consumidores y revisión antes de ampliar alcance. No implementar #30 como un bloque ni mezclar mantenimiento con experimentos.

| Orden | Cambio propuesto | Depende de | Cierre de la tarea |
| --- | --- | --- | --- |
| T0 | Revisar este SDD y acordar contrato hora, presupuesto y evidencia | Ninguna | Decisiones/dudas resueltas o explícitamente pendientes; responsables coordinados |
| T1 | Conectar `hora_actual` existente a instalaciones por reglas, con data/traza y dobles | T0 | O4, tres tests originales intactos, casos temporal/no temporal/error y regresiones de instalaciones; sin introducir aún bucle LLM |
| T2a | Corregir excepción de transporte en dos reintentos de embed | T0 | Dobles de error, límites sin sleep real, preservación del error; independiente de T1 |
| T2b | Config y normalización de schemas de adapters | T0 | Payloads/proveedores validados con dobles; no inferencia; compatibilidad declarada; independiente de T1/T2a |
| T3 | Definir e implementar ejecutor LLM acotado con registro parcial y fallback | T2b | O1/O2/O5 con fallo tras ejecución parcial; sin conectar ambos nodos de golpe |
| T4 | Integrar ejecutor en documental manteniendo validación única | T3 | O3, imagen/presupuesto/contexto y adaptador; orden y traza conservados |
| T5 | Integrar ejecutor en instalaciones reutilizando T1 | T1, T3 | Allowlist catálogo/avisos/hora, sin consulta adicional fuera del presupuesto ni borrado de resultados previos |
| T6 | Consolidar imports, cobertura PDF/visión, clientes y modo de tests | T4, T5; T2a para reintentos | O5/O6, casos Markdown adicionales, puerta de integración y suite offline conjunta; ajustes independientes pueden revisarse antes |
| T7 | Preparar aceptación real y documentación final | T6 | Recursos y manifest listos; ejecutar casos autorizados, registrar evidencia nueva; README/informe/presentación coherentes |
| T8 | Revisión final de develop → main | Integración acordada y T7 | Diff, SHA, evidencias y bloqueantes revisados nuevamente antes del cierre |

**Primera tarea recomendada tras revisar el SDD: T1, conectar la auxiliar existente a instalaciones sin cambiar su contrato.** El solapamiento con #30 está comprobado en `agentes/nodes/instalaciones.py` y `agentes/tools/auxiliares.py`: reutilizar su intención de activación/traza, no su sustitución del reloj. Mantener T1 separada de prompts, ejecutor LLM, correcciones de configuración y aceptación real. T1 cierra conexión por reglas, no todo R1/R2: T5 y la aceptación LLM siguen pendientes.

Diseño propuesto para T1: resultado estructurado bajo `ToolResult.data['hora_actual']`, conservando la procedencia del reloj y un evento independiente. Acordar disparadores temporales (la lista de #30 es candidata, no especificación validada), zona y tratamiento de fallo. La herramienta no debe convertir por sí sola una consulta municipal fallida en éxito ni responder apertura sin horarios contrastados.

### 5.1 Implementación T1 para revisión — 27/10/2026

Continuación autorizada después de redactar el SDD; las restricciones y evidencias
de las secciones anteriores describen la fase documental original.

**Atribución y separación de aportaciones.** Miguel (`MiguelG0929`) entregó la
implementación de `hora_actual`, su contrato estructurado, la exportación
perezosa y sus tres pruebas en el commit
[`6305e243367d7c2b65ea839ab07d4b073a42cef1`](https://github.com/AleDataAnalyst/agentes_deportesmad/commit/6305e243367d7c2b65ea839ab07d4b073a42cef1).
Esta continuación reutiliza esa herramienta; no la duplica ni modifica
`agentes/tools/auxiliares.py`, `agentes/tools/__init__.py` o
`tests/test_hora_actual.py`. La conexión por reglas a instalaciones, su límite
de errores, traza y pruebas de consumidores son el trabajo nuevo de T1.

- Conexión únicamente por reglas en instalaciones, sin integrar #30 ni su bucle
  LLM. La llamada al reloj usa explícitamente `zona="Europe/Madrid"`.
- Disparadores: palabras completas `hoy` y `ahora`; expresiones `hora actual`,
  `fecha actual`, `día actual`, `qué hora es`, `qué fecha es` y `qué día es`.
  Se normalizan mayúsculas y tildes. No basta mencionar `horarios`, `abierto`,
  `mañana` ni coincidencias parciales dentro de un nombre.
- El alcance es el presente: no se interpretan fechas futuras/pasadas ni
  lenguaje temporal general. `Mañana` se excluye por su ambigüedad entre parte
  del día y fecha relativa. La detección es léxica, no interpreta negaciones
  o citas; una frase que contenga esos disparadores puede activar el reloj.
- Se conserva el sobre completo de Miguel en `ToolResult.data['hora_actual']`:
  resultado estructurado, fuentes, ok, abstained y error. Se copia para evitar
  alias con el proveedor. No se mezclan fuentes del reloj con las municipales.
- La consulta municipal y su evento preceden al reloj. Se añade solo el evento
  nuevo `instalaciones.tool: hora_actual zona=Europe/Madrid status=ok|error`;
  el reducer del grafo conserva la traza anterior. No se repiten eventos previos.
- Un fallo declarado o excepción del reloj añade una advertencia en
  `data.advertencias` y evento de error, sin alterar status, answer, evidence ni
  error de la consulta municipal. Ante excepción se guarda resultado nulo,
  fuentes vacías y diagnóstico genérico, sin inventar fecha/hora.
- La hora queda en data/debug; no se añade a la respuesta ni se usa para deducir
  apertura. Conocer la hora no sustituye horarios, avisos o evidencia municipal.
- `agentes/tools/auxiliares.py`, su exportación y los tres tests originales de
  Miguel permanecen intactos. Los nuevos casos están en
  `tests/test_instalaciones_hora.py`, con dobles municipales y de reloj.

Validación T1 sobre los cambios sin commit: **77 passed, 1 deselected**, 13 avisos
de deprecación de dependencias, 9,12 s. Incluye 20 casos nuevos, los tres tests
originales de Miguel, regresiones de instalaciones/avisos/parser, imports en
procesos nuevos e integración síncrona. Es una selección, no la suite completa.
Se usaron las mismas variables y wrapper de bloqueo de red de §2.3, con temporal
nuevo `codex-t1-confirmado-<UUID>` y estos argumentos de pytest:

```console
-q -p no:cacheprovider -m "not integration" --basetemp <temporal-nuevo> --tb=short -k "not test_palabras_aviso_sin_pk" tests/test_instalaciones_hora.py tests/test_hora_actual.py tests/test_nodo_instalaciones.py tests/test_consultar_instalaciones.py tests/test_consultar_aviso_centro.py tests/test_parser_avisos.py tests/test_import_boundaries.py tests/test_sync_integration.py
```

La primera selección ampliada incluyó también `tests/test_runtime.py`: terminó
con 77 passed, 1 failed y 19 errores de setup. El test antiguo
`test_palabras_aviso_sin_pk` carece de doble para resolver nombres y alcanza un
intento de red, bloqueado antes de DNS/conexión. Los errores de runtime proceden
del bloqueo de import RAG en su fixture al cargar visión/documental en esa
selección. Se reprodujeron el fallo y un setup representativo cargando en memoria
el nodo original de `HEAD` (`git show HEAD:agentes/nodes/instalaciones.py`), sin
reemplazar archivos: 1 failed y 1 error. Estos impedimentos ya existen sin T1;
no se corrigen en esta tarea. La repetición satisfactoria excluye explícitamente
ese test antiguo y el módulo runtime; no se presenta como regresión global verde.
No hubo consultas reales de red, modelos ni RAG. La aceptación real sigue pendiente.

#### Cierre de T1 para revisión, sin commit

Autorización posterior: completar únicamente esta conexión y sus correcciones.
Se mantienen los disparadores y Europe/Madrid descritos arriba. Se ha completado
la validación de observaciones del reloj en el consumidor: sobres malformados,
fuentes incompatibles o un supuesto éxito sin resultado estructurado se traducen
en una limitación genérica, sin romper la consulta municipal. La herramienta
original de Miguel no se modifica.

Los tests nuevos incluyen 28 casos: disparadores positivos/negativos, zona,
sobre y procedencia, copia independiente, excepción/fallo declarado, seis
observaciones malformadas, conservación de resultados ajenos y dos recorridos
por AgentService con checkpoint/síntesis. Estos últimos comprueban que la traza
del reloj se acumula una sola vez, que releer el estado no repite llamadas y que
un fallo se muestra como advertencia conservando la respuesta municipal válida.
El reloj exitoso tampoco convierte un fallo municipal en éxito.

Se corrigió únicamente el aislamiento del test antiguo
`test_palabras_aviso_sin_pk`: ahora sustituye también
`resolver_centro_por_nombre` y verifica su llamada. Esto permite incluir el
módulo completo de instalaciones sin intentar red; no cambia producción ni las
pruebas originales del reloj. Los problemas de setup del módulo runtime de la
selección anterior permanecen fuera de T1 y no se declaran corregidos.

Resultado nuevo sobre el árbol de trabajo de T1: **86 passed, 0 exclusiones,
13 avisos de deprecación, 13,69 s**. Selección de ocho módulos, no suite completa.
Comando (con las variables/wrapper offline de §2.3; temporal nuevo
`codex-t1-cierre-<UUID>`):

```console
-q -p no:cacheprovider -m "not integration" --basetemp <temporal-nuevo> --tb=short tests/test_instalaciones_hora.py tests/test_hora_actual.py tests/test_nodo_instalaciones.py tests/test_consultar_instalaciones.py tests/test_consultar_aviso_centro.py tests/test_parser_avisos.py tests/test_import_boundaries.py tests/test_sync_integration.py
```

Se verificaron además whitespace e igualdad de los tres archivos de Miguel
contra HEAD mediante `git diff --exit-code HEAD -- agentes/tools/auxiliares.py
agentes/tools/__init__.py tests/test_hora_actual.py`. T1 queda implementada y
validada offline para revisión humana. No implica aceptar T5, los recursos reales
ni la PR #30; no se incorpora bucle LLM. No se hace staging, commit o publicación.

## 6. Integración Git propuesta — no ejecutada

1. La usuaria decidirá cuándo publicar esta rama mediante PR **mantenimiento → develop**. Antes: estado limpio tras sus commits, diff contra el `develop` vigente, actualización de referencias, comprobaciones offline sobre SHA publicado y revisión del alcance. No se propone PR directa a main. La rama local no tiene upstream configurado en la revisión previa; verificar de nuevo al publicar.
2. La PR de mantenimiento debe separar lo ya integrado en develop (#29/hora) de sus correcciones exclusivas y explicar preservación de contratos. Conservar `c31518b` y `50d9845` como referencias de trabajo; no es necesario reescribirlos para abrir PR. El SDD y cualquier T1 posterior deben constar con sus propios commits decididos por la usuaria.
3. Coordinar con el autor/revisor de #30 una única ruta: integrar primero la base de mantenimiento y después actualizar/adaptar #30 contra el nuevo develop. Si se adelanta alguna aportación de #30 mediante tarea pequeña, anotarla por archivo/contrato y retirar o adaptar su duplicado antes de integrar el resto. Esta fase no comunica con terceros ni modifica esa PR.
4. Evitar cherry-pick masivo, reemplazos completos y resoluciones ours/theirs. La PR #30 mezcla aportaciones necesarias, correcciones ya locales y contratos divergentes. Resolver por comportamiento según la matriz; conservar pruebas locales de fuentes mixtas, presupuesto 1, texto OCR plano, errores e imports, junto con las nuevas pruebas de selección LLM. Añadir la fixture de modo sin quitar `--run-integration`.
5. Tras cualquier movimiento de ramas, volver a comparar diff real y ejecutar regresión sobre el SHA resultante. Un green histórico de #30 no valida el árbol combinado. Decidir merge o rebase al preparar la actualización de esa rama, con el responsable de su historial; no imponerlo desde este SDD.
6. **#31 es develop → main**: todo lo integrado posteriormente en develop aumentará su alcance. Revisar nuevamente título/descripción, diff, SHA, CI, aprobaciones y evidencias antes de fusionar; su estado fusionable actual no equivale a aprobación de cierre. El workflow `validar-origen-main.yml` solo valida origen develop del mismo repo, no ejecuta ni certifica la suite.
7. Preservar la entrega original: no mover ni reescribir `18ca29d` ni reemplazar evidencias originales. Usar enlaces al commit histórico y registros posteriores separados. Un tag de archivo, si se desea, será decisión posterior de la usuaria; no se crea en esta fase.

## 7. Dudas y decisiones pendientes

- Acordar con Miguel mantener el contrato estructurado ya integrado y actualizar en una tarea futura la antigua precondición A8 sobre `_fecha_actual_iso`; no cambiar silenciosamente el contrato ni la evidencia histórica.
- Acordar si `hora_actual` debe limitarse a contexto/debug o aparecer también en respuesta, los disparadores temporales y la zona; ninguna alternativa acredita apertura sin datos del centro.
- Precisar cómo contabilizar propuestas bloqueadas frente a llamadas ejecutadas e inferencias; el fallback siempre comparte el presupuesto restante y conserva el registro parcial.
- Fijar política de prioridad de imagen bajo selección LLM y formato/saneamiento de traza que mostrarán ambos clientes. No confundir `status=ok` del ejecutor con evidencia válida del especialista.
- Confirmar proveedores soportados (incluido el alcance de HuggingFace), versiones reproducibles y modelos disponibles antes de aceptación real.
- Acordar consulta/fuente RAG esperadas, manifest del índice y responsable de preparación; consultas de instalaciones y comportamiento de fallback caducado; alcance de bloques PDF mixtos.
- Coordinar quién adapta #30 y qué aportaciones se integran primero. Revalidar #31 al final; no cerrar requisitos solo por sus títulos o cifras históricas.
- Verificar informe, presentación y revisión/merge individual exigidos por el enunciado. Este SDD no audita aún todos esos entregables ni certifica equivalencia histórica del enunciado consultado.

El resultado de esta fase es una propuesta documental revisable. Implementación, ejecución real y publicación quedan para decisiones posteriores explícitas.
