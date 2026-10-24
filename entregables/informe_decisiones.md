## Informe de decisiones — Project Break 2: Agentes con LangGraph

**Equipo:** David Cruz, Héctor González, Alejandra García, Miguel López
**Dominio:** Deporte Municipal Madrid
**Fecha:** octubre 2026

---

## Diseño del grafo

Desde el principio teníamos claro que no queríamos un agente monolítico que lo hiciera todo. El dominio del deporte municipal tiene partes bien diferenciadas: por un lado toda la normativa y tarifas (PDFs del Ayuntamiento, precios públicos, reglamentos), y por otro los datos de instalaciones concretas (polideportivos, piscinas, áreas deportivas). Eso nos llevó naturalmente a dos especialistas.

El flujo que acordamos es: el supervisor recibe el mensaje y decide a quién enviar la consulta. El especialista documental tira del RAG para responder preguntas sobre tarifas, normativa y condiciones. El especialista de instalaciones consulta los CSVs del portal datos.madrid.es para localizar centros concretos. Después, el nodo sintetizar une los resultados en una respuesta coherente y genera un plan en viñetas. Antes de cerrar, el grafo se detiene en el nodo aplicar y espera que el humano apruebe o rechace.

Decidimos interrumpir justo antes de aplicar porque es el único punto donde el agente está a punto de confirmar información al usuario como válida. Hacerlo antes, en sintetizar, no tenía sentido: el humano necesita ver el plan completo para poder juzgarlo. Hacerlo después tampoco, porque entonces la decisión ya estaría tomada.

Para la persistencia usamos MemorySaver con un thread_id generado en cada nueva conversación. Eso nos permite que CLI y Streamlit compartan el mismo estado si usan el mismo thread_id, que era uno de los requisitos.

> **Corrección:** CLI y Streamlit comparten el mismo servicio y las mismas validaciones, pero no el estado. `MemorySaver` guarda los checkpoints en la memoria del proceso, y cada cliente se ejecuta en un proceso distinto, así que ninguno puede retomar la conversación del otro aunque use el mismo `thread_id`. Para compartirla haría falta persistir en disco (`SqliteSaver`, ver "Siguientes pasos").

El supervisor tiene un fallback determinista en Python para los casos en que el LLM devuelve un rol que no existe en el grafo. Sin eso, un fallo del modelo rompe el flujo entero.

> **@Alejandra** — ¿añades aquí algún detalle sobre las decisiones del grafo o el supervisor que no hayamos recogido?

---

## Tools

| Tool | Tipo | Responsable | Descripción |
|------|------|-------------|-------------|
| `rag_ask` | RAG completo | Héctor | Consulta el índice ChromaDB con PDFs de tarifas, reglamentos y precios públicos. Abstención explícita si no hay evidencia suficiente. |
| `consultar_instalaciones` | API / datos externos | Miguel | Consulta los CSVs de polideportivos, piscinas y áreas deportivas de datos.madrid.es. Fallback a archivo local si la red falla. |
| `hora_actual` | Auxiliar determinista | Miguel | Devuelve fecha y hora actual. Útil para razonar sobre horarios de apertura y temporadas de piscinas. |
| `describir_imagen` | Multimodal | Héctor | Recibe una imagen (cartel, folleto, mapa deportivo) y devuelve descripción textual usando el modelo de visión de Gemini. |

Todas las tools están registradas en una allowlist en Python. El LLM propone el nombre; el código solo ejecuta lo que está en el registro. Cualquier nombre fuera de la lista devuelve un error controlado sin romper el flujo.

El RAG del PB1 se expone como `rag_ask(consulta: str) -> str`, envuelto como `@tool` de LangGraph. El especialista documental la llama con la pregunta del usuario; el RAG recupera los chunks relevantes del índice y genera la respuesta anclada al contexto. Si no encuentra evidencia suficiente, declara abstención explícitamente en lugar de inventar.

> **@Héctor** — confirma el nombre exacto de la función pública del RAG y si el contrato es `rag_ask(consulta: str) -> str` o distinto.
> **@Miguel** — confirma el nombre de la tool de instalaciones y si el fallback local ya está implementado.

---

## HITL: lo que observamos en las pruebas

### Caso aprobado

Pregunta: *"¿Cuánto cuesta el abono de piscina?"*

El supervisor enrutó al especialista documental, que en modo demo devolvió abstención por no tener el índice real cargado. El especialista de instalaciones también abstención porque su nodo ejecutable no estaba conectado aún. El nodo sintetizar generó un plan informativo reconociendo esas limitaciones. El plan apareció en el sidebar con tres viñetas sobre qué faltaba para responder con fundamento.

Aprobamos el plan. El agente confirmó con "Plan informativo aprobado. No se ha ejecutado ninguna acción externa." y el chat quedó desbloqueado. El comportamiento fue el esperado: la aprobación no inventa datos, simplemente cierra el ciclo de manera limpia reconociendo las limitaciones actuales.

> **@Héctor** — cuando el RAG real esté conectado, actualiza este apartado con un caso real de aprobación con respuesta fundada en el corpus.

### Caso rechazado

Pregunta: *"¿Puedo reservar sin estar empadronado?"*

Misma situación de abstención en ambos especialistas. El plan reflejaba las limitaciones. Rechazamos. El agente respondió "Plan rechazado. Puedes enviar un nuevo mensaje." y el input volvió a estar disponible sin necesidad de abrir una nueva conversación.

Esto es exactamente el comportamiento que queríamos: el rechazo no mata la sesión, solo libera el estado para que el usuario pueda reformular o preguntar otra cosa con el mismo thread_id. El checkpointer mantiene la memoria de la conversación anterior.

---

## Cliente Streamlit

El cliente es una interfaz sobre `AgentService`: chat, revisión del plan y un panel de diagnóstico. No tiene lógica del grafo; solo consume el servicio común, igual que la CLI, y así la interfaz no acaba tomando decisiones que corresponden al grafo. Por eso lo separamos en tres piezas: `streamlit_app.py` para el chat, `hitl.py` para los botones de aprobar y rechazar, y `debug.py` para el diagnóstico.

El servicio y el `thread_id` viven en `st.session_state` y no en una caché global. Con caché global, dos personas usando la app a la vez compartirían conversación y plan. "Nueva conversación" crea un hilo nuevo.

Los botones de HITL salen en la barra lateral solo cuando hay un plan pendiente, y mientras tanto el chat queda bloqueado. La decisión se envía siempre con el mismo `thread_id` y el `plan_id` vigente, así que no se pueden mezclar preguntas nuevas con una decisión pendiente ni aprobar un plan antiguo.

Reutilizamos la validación de la CLI (`agentes.validation`): `validar_mensaje` antes de enviar, `validar_decision` y `validar_id` antes de decidir, y `validar_estado` sobre lo que devuelve el servicio, que evita enseñar el plan de otra conversación. El coste es que se bloquean los mensajes de varias líneas.

Errores, mensajes, debug y los pasos del plan pasan por `sin_secretos`. Los resultados de los especialistas se convierten antes a diccionario, porque el filtro solo entra en diccionarios y listas. El filtro es heurístico: no garantiza ocultar cualquier secreto y tampoco escapa Markdown, así que un paso del plan con un enlace se seguiría pintando como enlace.

El panel de debug enseña la fase HITL, las iteraciones, la traza y, de cada especialista, su estado, origen (real, simulado, fallback o no disponible), respuesta y fuentes. Todo va recortado y los datos técnicos completos solo salen si se piden. El origen está para no confundir un dato simulado, o un especialista caído, con uno real; el fallback se detecta con `fallback` y con `origen == "fallback"`, porque instalaciones usa la segunda forma.

Al aprobar solo añadimos el mensaje de cierre, porque el backend ya conserva la respuesta revisada. Y si el servicio no arranca, se muestra un error claro en lugar de caer en la demo, igual que en el backend.

Pruebas: a mano, aprobar, rechazar, nueva conversación y entrada no válida. Automáticas hay solo dos (`tests/test_clientes_seguridad.py`): que un resultado con `origen="fallback"` se muestra como fallback, y que una credencial en un paso del plan sale oculta sin modificar el estado original. Pendiente: mostrar las fuentes junto a la respuesta del chat y ampliar los tests.

---

## Multimodal

> **@Héctor** — rellena esta sección cuando tengas `describir_imagen` integrada y probada. Incluye: qué imagen usaste, qué devolvió la tool exactamente, y si el especialista documental pudo usar esa salida como contexto.

La tool `describir_imagen` usa el modelo de visión de Gemini para extraer texto e información de imágenes. La imagen demo prevista es la infografía oficial del Ayuntamiento de Madrid sobre cómo adquirir o renovar el Abono Deporte Madrid. El contrato acordado es imagen → texto descriptivo, que el especialista documental puede usar como contexto complementario al RAG.

---

## Tres fallos que encontramos

**Timeout en la indexación del RAG.** El modelo 27B en equipos con GPU limitada (RTX 3060, 6 GB VRAM) tardaba entre 121 y 196 segundos por documento, superando el timeout de 120 s configurado en el pipeline. Lo intentamos con `qwen2.5:3b` como alternativa más ligera, pero añadía etiquetas sin respaldo. La solución fue implementar checkpoints de recuperación para reanudar desde el último documento procesado, y migrar la indexación a Gemini.

**Bug de `monkeypatch` en los tests del nodo documental.** Cinco tests de `tests/test_node_documental.py` fallaban con `AttributeError` porque usaban `monkeypatch.setattr(nod.REGISTRY, "rag", ...)` sobre un diccionario. Los diccionarios en Python no tienen atributos asignables con `setattr`; la llamada correcta es `monkeypatch.setitem`. Los tests afectados: `test_salida_solo_campo_autorizado`, `test_imagen_prevista_no_disponible`, `test_presupuesto_agotado`, `test_contexto_permitido_filtra_fuentes` y `test_error_de_tool_no_lanza`. Ya está corregido: los cinco usan ahora `monkeypatch.setitem`.

**Stale closure en los callbacks de Streamlit.** Los callbacks `on_aprobar` y `on_rechazar` capturaban la variable `estado` en el momento de la definición, no en el de la ejecución, y al pulsar Aprobar se enviaba el `plan_id` de un estado anterior. Ahora los callbacks solo se crean mientras hay un plan pendiente y se redefinen en cada ejecución con el estado vigente. Antes de enviar la decisión se valida el `plan_id`, y al terminar se guarda el resultado en `st.session_state` y se relanza la página con `st.rerun()`, de modo que un plan viejo no puede volver a usarse.

---

## Siguientes pasos — MLOps

El paso más inmediato sería migrar de `MemorySaver` a `SqliteSaver`. Ahora mismo el estado desaparece al reiniciar el proceso; con SQLite los checkpoints persisten en disco.

Para monitorización necesitaríamos registrar al menos tres métricas: tasa de aprobación y rechazo HITL, latencia por nodo, y tasa de abstención del RAG.

El corpus de tarifas se actualiza cada año; habría que automatizar la re-indexación cuando cambien los PDFs fuente.

Para despliegue separaríamos el servicio de indexación del de inferencia, con el índice ChromaDB montado como volumen persistente.

> **@Alejandra** — ¿añades aquí algo sobre el grafo asíncrono o SqliteSaver que mencionaste en Slack?