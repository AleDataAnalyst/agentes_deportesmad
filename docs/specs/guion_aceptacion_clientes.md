# Guion de aceptación de los clientes (CLI y Streamlit)

Desarrolla los criterios de [aceptacion.md](aceptacion.md) en escenarios verificables. Se ejecuta a mano, en modo real y con los dos clientes.

## 1. Reglas de la aceptación

- **Nunca autoaprobar.** Toda aprobación o rechazo la hace una persona con `/aprobar`, `/rechazar` o los botones de Streamlit.
- **Comparar el contrato, no el texto.** La respuesta generada puede variar entre ejecuciones y entre clientes. Lo que tiene que coincidir son el estado (`status`), las fuentes, el origen de los datos y la fase HITL.
- **Un caso sin evidencia no está aceptado.** Tener el código conectado no equivale a haber aceptado una consulta real.
- **Registrar siempre** el sha del commit, el sistema operativo, el comando, si hubo red y si se usó algún doble.
- **Modo real.** Las pruebas se hacen en modo real, nunca en `modo demo`.

## 2. Requisitos previos

| Requisito | Responsable | Casos afectados |
|---|---|---|
| Índice RAG compatible y reproducible | Héctor | A1–A4 |
| Consulta con fuente esperada y pregunta fuera del corpus | Héctor | A1, A4 |
| Instalaciones conectado al runtime | Alejandra | A5, A6 |
| Herramienta auxiliar determinista | Miguel | A8 |
| Vía de entrada de la imagen en el recorrido | Por acordar | A7 |

## 3. Preparación (una vez por equipo)

```console
git switch develop
git pull
git rev-parse --short HEAD          # anotar sha
python -m scripts.smoke_real        # comprueba índice y claves sin ingesta
```

`smoke_real` debe informar `index_file_present: true` y las claves presentes. Si informa `RAG_INDEX_MISSING`, falta el índice y no se debe continuar con A1–A4.

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

**Comprobación adicional (opcional):** intentar resolver con un `plan_id` antiguo debe devolver `PLAN_NOT_CURRENT`. `scripts/smoke_real.py` ya cubre este caso, así que basta con citar su salida.

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

Copiar una fila por caso y cliente:

| Caso | Cliente | Fecha | sha | SO | Comando | Red | Dobles | Resultado | Evidencia |
|---|---|---|---|---|---|---|---|---|---|
| A1 | CLI | | | | | sí/no | no | ACEPTADO / FALLA / BLOQUEADO | ruta captura |

## 7. Qué no valida este guion

- La calidad semántica de las respuestas: solo se compara el contrato.
- Rendimiento, concurrencia ni persistencia entre reinicios del proceso.
- Cualquier ejecución con dobles o en modo demo.
