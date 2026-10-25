# Guion de aceptación de los clientes (CLI y Streamlit)

Desarrolla los criterios de [aceptacion.md](aceptacion.md) en escenarios verificables. Se ejecuta a mano, en modo real y con los dos clientes.

## 1. Reglas de la aceptación

- **Nunca autoaprobar.** En los casos A1–A9, toda aprobación o rechazo la hace una persona con `/aprobar`, `/rechazar` o los botones de Streamlit.
- **`smoke_real` no es un caso de este guion.** Es una sonda automática que sí toma decisiones por su cuenta (por ejemplo, aprueba y rechaza para comprobar el contrato del backend). Sirve para verificar la preparación y el backend, pero no sustituye ni acredita ningún caso A1–A9, que se hacen a mano y con una decisión humana.
- **Comparar el contrato, no el texto.** La respuesta generada puede variar entre ejecuciones y entre clientes. Lo que tiene que coincidir son el estado (`status`), las fuentes, el origen de los datos y la fase HITL.
- **Un caso sin evidencia no está aceptado.** Tener el código conectado no equivale a haber aceptado una consulta real.
- **Registrar siempre** el sha del commit, el sistema operativo, el comando, si hubo red y si se usó algún doble.
- **Modo real.** Las pruebas se hacen en modo real, nunca en `modo demo`.

## 2. Requisitos previos

| Requisito | Responsable | Casos afectados |
|---|---|---|
| Índice RAG compatible y reproducible | Héctor | A1–A4 |
| Consulta con fuente esperada y pregunta fuera del corpus | Héctor | A1, A4 |
| Instalaciones conectado al runtime | Miguel y Alejandra | A5, A6 |
| Herramienta auxiliar determinista | Miguel | A8 |
| Vía de entrada de la imagen en el recorrido | Por acordar | A7 |

## 3. Preparación (una vez por equipo)

```console
git switch develop
git pull
git rev-parse --short HEAD          # anotar sha
python -m scripts.smoke_real        # comprueba índice y claves sin ingesta
```

La sonda `smoke_real` es automática y toma decisiones por su cuenta; aquí solo se usa para comprobar la preparación. Debe informar `index_file_present: true` y las claves presentes. Si informa `RAG_INDEX_MISSING`, falta el índice y no se debe continuar con A1–A4.

> `index_file_present` solo comprueba que existe `chroma.sqlite3`. Antes de dar por bueno el índice, comprobar además que una búsqueda devuelve el número de resultados pedido.

- CLI: `python -B main.py --modo real --debug`
- Streamlit: `python -m streamlit run app.py`. Abrir el panel "Debug — estado del agente".
- En cada caso, empezar con una conversación nueva: `/nueva` en CLI, botón "Nueva conversación" en Streamlit.

## 4. Casos

En todos los casos, "contrato esperado" se refiere al estado que devuelve `AgentService` y a `specialist_results[rol]`, que es un `ToolResult` con los campos `status`, `answer`, `evidence`, `error` y `data`.

### A1. Consulta documental con fuente esperada

**Entrada:** la consulta que facilite Héctor, con su documento fuente esperado.

- **CLI:** enviar la consulta y, con `/debug`, revisar el resultado del especialista documental.
- **Streamlit:** enviar la consulta, comprobar que las fuentes aparecen bajo la respuesta y revisar el resultado documental en el panel de debug.

**Contrato esperado:**
- `specialist_results["documental"].status == "ok"`
- `evidence` no vacío y que incluya la fuente esperada (`evidence[].source` coincide con `data["fuentes"]`)
- `answer == data["resultado"]`
- el origen que muestra el debug es real, no simulado
- en Streamlit, las fuentes del chat coinciden con las del debug

**Evidencia:** consulta, fuente esperada, fuentes devueltas y captura del debug en ambos clientes.

### A2. HITL aprobado y siguiente pedido

**Entrada:** la misma consulta de A1.

**Pasos:**
1. Enviar la consulta y comprobar que el sistema se detiene antes de aplicar.
2. Anotar el `thread_id` y el `plan_id` mostrados.
3. Aprobar: `/aprobar` en CLI, botón Aprobar en Streamlit.
4. Enviar un segundo pedido en el mismo hilo.

**Contrato esperado:**
- Tras el paso 1: `pendiente_hitl == True`, `approved is None`, `done == False`, `plan_id` no vacío, y el chat no acepta mensajes nuevos en Streamlit.
- Tras aprobar: `pendiente_hitl == False`, `approved == True`, y la pantalla se refresca sin repetir la respuesta.
- El segundo pedido se procesa en el mismo `thread_id` y genera un `plan_id` nuevo.

**Evidencia:** `thread_id`, los dos `plan_id` y una captura antes y después de la decisión.

### A3. HITL rechazado

**Entrada:** la misma consulta, en una conversación nueva.

**Pasos:** enviar la consulta, comprobar la pausa y rechazar.

**Contrato esperado:** `approved == False` y `pendiente_hitl == False`, sin respuesta aplicada como confirmada. Streamlit muestra "Plan rechazado. Puedes enviar un nuevo mensaje."

**Comprobación adicional (opcional):** intentar resolver con un `plan_id` antiguo debe devolver `PLAN_NOT_CURRENT`. `scripts/smoke_real.py` ya cubre este caso de forma automática; su salida se puede citar como apoyo, pero no sustituye al rechazo manual de A3, que lo decide una persona.

**Evidencia:** `plan_id` rechazado y captura del estado final.

### A4. Abstención fuera del corpus

**Entrada:** una pregunta que Héctor confirme que no está en el corpus.

**Contrato esperado:**
- `specialist_results["documental"].status == "abstained"`
- `evidence` vacío o sin fuentes inventadas; en Streamlit no se muestra ninguna fuente bajo la respuesta
- la respuesta final declara la limitación y no inventa normativa ni tarifas

**Evidencia:** pregunta, `status` y respuesta final en ambos clientes.

> Este caso solo es válido si A1 ha dado `status == "ok"` con el mismo índice; si no, cualquier pregunta se abstendría.

### A5. Instalaciones con red (origen online)

**Precondición:** instalaciones conectado al runtime.

**Entrada:** una consulta de catálogo o de avisos de un centro concreto, acordada con Miguel.

**Contrato esperado:**
- `specialist_results["instalaciones"].status == "ok"`
- `data.origen` en `api` (catálogo) o `html` (avisos)
- `fecha_consulta` presente
- el debug muestra origen real

**Evidencia:** consulta, origen, fecha de consulta y captura del debug.

### A6. Fallo de red y fallback fechado

**Precondición:** la misma de A5.

**Cómo provocar el fallo:** el método está por acordar con Miguel. La opción más limpia es bloquear solo `datos.madrid.es` y `madrid.es` (por ejemplo, en el archivo `hosts`), para que el LLM y el RAG sigan teniendo red. Anotar el método usado.

**Entrada:** la misma consulta de A5.

**Contrato esperado:**
- `data.origen == "fallback"` y `fecha_captura_fallback` presente
- el debug muestra origen fallback
- la respuesta no presenta la captura como estado actual del centro

**Atención:** las capturas de avisos caducan a los 3 días (`MAX_EDAD_FALLBACK_AVISOS_DIAS = 3`). La captura incluida es del 19/10, así que lo esperable es que el sistema declare la limitación en lugar de usarla. Hay que registrar el comportamiento observado tal cual.

**Evidencia:** método de corte, origen, fecha de la captura y respuesta final.

### A7. Imagen y texto devuelto por la tool de visión

**Vía de entrada:** la imagen demo `assets/imagen_demo.jpg` como tool del documental.

Si la imagen no pasa por el grafo, registrar una llamada directa a `imagen_preguntar` con la imagen demo como evidencia de la tool, indicando que es una llamada directa.

**Contrato de la tool:** `{"ok", "resultado", "fuentes", "abstained", "error"}`. Sin `GOOGLE_API_KEY` debe devolver `ok=False` y `abstained=True`.

**Evidencia:** imagen usada, pregunta, texto real devuelto y si la llamada fue directa o desde el flujo.

### A8. Herramienta auxiliar

**Precondición:** la auxiliar de Miguel implementada y expuesta como herramienta autorizada, reutilizando `_fecha_actual_iso()`.

**Entrada:** la consulta que la active, acordada con Miguel.

**Contrato esperado:** la llamada aparece en la traza o en los resultados del debug, con salida determinista y fecha ISO 8601 con zona horaria.

**Evidencia:** consulta, llamada registrada y salida.

### A9. Recuperación tras un error (Streamlit y CLI)

**Entrada:** una consulta durante la cual se provoque un fallo del servicio (por ejemplo, cortando la red o con una clave inválida). El método se anota igual que en A6.

**Pasos:**
1. Enviar la consulta y observar el error.
2. Comprobar el estado: la CLI exige `/estado`; Streamlit relee el estado solo al volver a pintar la página.
3. Intentar enviar otro mensaje y, si procede, decidir sobre el plan.

**Contrato esperado:**
- Streamlit muestra el error una sola vez y, a continuación, el estado real del hilo.
- Si quedó un plan pendiente, se puede aprobar o rechazar; si la ejecución quedó incompleta (`ejecucion_incompleta`), el chat se bloquea y hay que empezar una nueva conversación; si no hay nada pendiente, se puede continuar.
- Si no se puede leer el estado, Streamlit ofrece "Reintentar comprobación" y no deja consultar ni decidir.
- La CLI no permite consultar ni decidir hasta ejecutar `/estado` o `/nueva`.

**Evidencia:** método del fallo, mensaje de error, estado recuperado en cada cliente y captura.

## 5. Comparación CLI y Streamlit

Para cada caso, comprobar que coinciden estos campos (el texto puede variar):

| Campo | CLI | Streamlit | ¿Coincide? |
|---|---|---|---|
| `status` por especialista | | | |
| Fuentes (`evidence[].source`) | | | |
| Origen (real / fallback / simulado / no disponible) | | | |
| Fase HITL (`pendiente_hitl`, `approved`, `done`) | | | |
| Errores por código (`HITL_PENDING`, `PLAN_NOT_CURRENT`…) | | | |

CLI y Streamlit no comparten estado, porque `MemorySaver` vive en la memoria de cada proceso. Cada cliente se prueba con su propio hilo.

## 6. Registro de ejecución

Una fila por caso y cliente. Ejecutado el 25/10/2026 con el servicio real, sin dobles y con el supervisor por reglas (`origen=reglas` en la traza). La evidencia es la salida de consola o de Streamlit; no hay capturas guardadas todavía.

| Caso | Cliente | Fecha | sha | SO | Comando | Red | Dobles | Supervisor | Resultado | Evidencia |
|---|---|---|---|---|---|---|---|---|---|---|
| A1 | CLI | 2026-10-25 | `603f955` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | ACEPTADO | `servicios de centro deportivo CEA bermudez`: documental `ok` con fuentes reales (`reglamento_instalaciones.pdf`, `200186-0-polideportivos.csv`, `210227-0-piscinas-publicas.csv`, `DecretoAnulacionReservasConCoste.pdf`), `tool=rag ok=True abstained=False`, instalaciones `ok` y síntesis 2 de 2. Hilo `6463c898…`, plan `2e60c37b…`. Salida de consola; la consulta y la fuente esperadas siguen por confirmar con el responsable del RAG |
| A1 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | Consulta propia `servicios de centro deportivo CEA bermudez`: documental `ok`, origen real, con fuentes reales (CSV de polideportivos y piscinas, reglamento y decreto en PDF). La consulta y la fuente esperada siguen por confirmar con el responsable del RAG. Capturas: [respuesta](../evidencias/A1-streamlit-1-respuesta-documental.png), [traza](../evidencias/A1-streamlit-2-debug-trazas.png), [fuentes](../evidencias/A1-streamlit-3-debug-fuentes.png) |
| A2 | CLI | 2026-10-25 | `603f955` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | ACEPTADO | Con la consulta de A1, hilo `6463c898…`: plan `2e60c37b…` aprobado (`approved=True`, `done=True`); un segundo `/aprobar` responde "No hay un plan pendiente"; segundo pedido en el mismo hilo con plan nuevo `124f40a3…`. Salida de consola |
| A2 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | Hilo `6407e148…` con la consulta de A1: plan pendiente y chat bloqueado ([plan pendiente](../evidencias/A2-streamlit-1-plan-pendiente.png), [chat bloqueado](../evidencias/A2-streamlit-2-chat-bloqueado-y-fuentes.png)). Hilo `1da2ab8c…`: aprobación con `done=True` ([aprobado](../evidencias/A2-streamlit-3-aprobado.png)), segundo pedido en el mismo hilo ([segundo pedido](../evidencias/A2-streamlit-4-segundo-pedido.png)) y nuevo plan pendiente ([plan pendiente](../evidencias/A2-streamlit-5-segundo-plan-pendiente.png)). Las capturas son anteriores a que el debug de Streamlit mostrara el `plan_id` (ahora lo enseña, igual que la CLI): el segundo plan se acredita porque el hilo vuelve a quedar pendiente de decisión tras aprobar |
| A3 | CLI | 2026-10-25 | `603f955` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | ACEPTADO | Con la consulta de A1: rechazo del plan `124f40a3…` (`approved=False`) y, en conversación nueva `f45992b1…`, rechazo del plan `57215b6a…` (`approved=False`, `pendiente_hitl=False`); la consulta siguiente se acepta. Salida de consola |
| A3 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | Rechazo y nueva conversación (hilos `cba70cde…` y `2fd41616…`), con el chat disponible tras rechazar: [plan rechazado](../evidencias/A3-streamlit-1-plan-rechazado.png), [nueva conversación](../evidencias/A3-streamlit-2-nueva-conversacion.png), [rechazo en conversación nueva](../evidencias/A3-streamlit-3-rechazo-conversacion-nueva.png). Debug con `Fase HITL: rechazado` y `done=False`: [debug](../evidencias/A3-streamlit-4-debug-rechazado.png) |
| A4 | CLI | 2026-10-25 | `603f955` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | ACEPTADO | `¿quién ganó el último mundial de fútbol?`: documental `abstained` ("No dispongo de esa información en los documentos proporcionados") sin fuentes del documental; no se inventa la respuesta. Hilo `6463c898…`, plan `124f40a3…`. Salida de consola |
| A4 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | `¿quién ganó el último mundial de fútbol?`: el documental se abstiene ("No dispongo de esa información en los documentos proporcionados"), sin fuentes del documental y sin inventar la respuesta. Captura: [abstención](../evidencias/A4-streamlit-1-abstencion.png) |
| A5 | CLI | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | ACEPTADO | `centros deportivos en moncloa`: `status=ok`, `origen=api`, `n=82`, `fecha_consulta` 2026-10-25T13:35:12+01:00, con fuentes |
| A5 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | `status=ok`, `origen=api`, `fecha_consulta` 2026-10-25T19:15:12+01:00 en la respuesta, con fuentes |
| A6 | CLI | 2026-10-25 | `603f955` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | no | no | reglas | ACEPTADO | Corte: wifi apagado (corte total). `centros deportivos en moncloa`: instalaciones `ok` con `origen=fallback`, `fecha_captura_fallback` 2026-10-16, aviso de CKAN no disponible y "Fallback histórico: no acredita condiciones actuales". El documental falló con `ChunkedEncodingError` por la falta de red. Hilo `764b8def…`, plan `e27e08b8…`. Salida de consola |
| A6 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | no | no | reglas | ACEPTADO | Corte: wifi apagado (corte total, no solo `datos.madrid.es`). `origen=fallback`, captura histórica 2026-10-16, aviso "Fallback histórico: no acredita condiciones actuales". El documental también falló por la falta de red. Captura: [fallback sin red](../evidencias/A6-streamlit-1-fallback-sin-red.png) |
| A7 | CLI | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | BLOQUEADO | La imagen no está enrutada en el grafo |
| A7 | Streamlit | 2026-10-25 | `2c20660` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | ACEPTADO | Con el backend de la PR #25 integrado, Streamlit sube `assets/imagen_demo.jpg`, muestra "La imagen se enviará con tus mensajes mientras siga subida" y la envía como `image_id` relativo con la consulta, desde el flujo y no como llamada directa, sin errores. Captura de la subida: [subida de imagen](../evidencias/streamlit-subida-imagen.png). No se ha registrado el texto que devuelve la visión: anotar la pregunta y la respuesta para acreditar también el contenido |
| A8 | CLI | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | BLOQUEADO | Herramienta auxiliar sin implementar |
| A8 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | sí | no | reglas | BLOQUEADO | Ídem |
| A9 | CLI | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -B main.py --modo real --debug` | sí | no | reglas | PENDIENTE | Sin ejecutar |
| A9 | Streamlit | 2026-10-25 | `20fc64a` | macOS (Darwin 25.3.0) | `python -m streamlit run app.py` | no | no | reglas | NO REPRODUCIBLE | Sin red, el servicio no lanza excepciones: los fallos llegan como estados de error y avisos. La recuperación solo está verificada con un servicio simulado (`tests/test_clientes_seguridad.py`) |

Observaciones:

- Las filas de A1 a A4 de la CLI se ejecutaron con el RAG real y el catálogo, en una misma sesión y con la consulta de A1. A2, A3 y A5 se habían hecho antes con consultas de instalaciones, cuando el documental aún se abstenía por el índice.
- Sin red, el documental falló con `module 'requests' has no attribute 'ChunkedEncodingError'` (`rag/embed.py`, líneas 137 y 244: la clase está en `requests.exceptions`). Reproducido también en la CLI. Pendiente de corregir por el responsable del RAG.
- "PENDIENTE" significa que no se ha ejecutado o no se ha completado; no equivale a aceptado.

## 7. Qué no valida este guion

- La calidad semántica de las respuestas: solo se compara el contrato.
- Rendimiento, concurrencia ni persistencia entre reinicios del proceso.
- Cualquier ejecución con dobles o en modo demo.
