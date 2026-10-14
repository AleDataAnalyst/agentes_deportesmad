# Análisis de viabilidad, utilidad y alternativas

**Proyecto:** agentes_deportesmad · PB02
**Fecha de corte de la evidencia municipal:** 13 de octubre de 2026
**Propósito:** conservar la investigación realizada para que el equipo pueda retomarla sin repetir las mismas búsquedas.

## Cómo leer este documento

Este es un registro de investigación y comparación. No asigna tareas ni convierte posibilidades analizadas en decisiones del equipo. El handoff operativo de Miguel está separado en [Handoff para Miguel: Especialista de Instalaciones y Avisos](../decisiones/Handoff_Miguel_Especialista_Instalaciones.md).

En el reparto actual, Miguel continúa el trabajo del especialista de **Instalaciones y avisos**. El MVP prioriza un grafo síncrono. La comparación con RAG, calendario, competiciones, rutas u otras opciones sirve para contextualizar la viabilidad y no significa que esas líneas estén aprobadas ni asignadas.

## Evidencia comprobada sobre instalaciones y avisos

- El conjunto municipal [Deportes. Centros deportivos municipales (polideportivos)](https://datos.madrid.es/dataset/200186-0-polideportivos) se consultó mediante su API CKAN. La respuesta registrada contenía 82 centros y los campos `PK`, `NOMBRE`, `DISTRITO` y `CONTENT-URL`.
- Se consultaron las 82 fichas oficiales enlazadas. En las consultas registradas el 13/10/2026, las 82 respondieron HTTP 200. En 12 se detectó el encabezado “Aviso a usuarios/as”, con 13 bloques de aviso en total.
- El catálogo tiene una API; los avisos observados están en el HTML de las fichas. En la investigación no se identificó una API independiente de avisos.
- Las publicaciones observadas incluían obras, cierres totales o parciales, suspensión de servicios, limitaciones y avisos técnicos. El detalle centro por centro, con IDs, URLs y resultados, está en el [handoff](../decisiones/Handoff_Miguel_Instalaciones_y_Avisos.md).

**Límites:** el HTTP 200 solo indica que la página respondió. La detección del encabezado no prueba que el aviso siga vigente ni que un centro sin encabezado esté operativo. Algunas publicaciones no expresaban fecha de fin, tenían fechas ambiguas o decían “hasta nuevo aviso”. No se ha validado un parser integrado, monitorización periódica ni fallback del proyecto.

## Comparación de temas investigados

Las valoraciones son cualitativas y reflejan la evidencia consultada a la fecha de corte; no son puntuaciones de evaluación ni acuerdos del equipo.

| Tema | Utilidad potencial | Viabilidad según lo comprobado | Límites y estado de investigación |
|---|---|---|---|
| Información documental con el RAG del PB01 | Alta como base: condiciones, normas, tarifas y procedimientos publicados. | Alta como reutilización, condicionada a la integración y al contrato real del RAG. | Responde sobre su corpus; no sustituye la comprobación de avisos recientes en una ficha municipal. Héctor lleva la conexión del RAG según el reparto actual. |
| Instalaciones y avisos | Alta para quien necesita saber si hay publicaciones que afectan al centro o servicio que quiere usar. | El catálogo CKAN y las fichas se pudieron consultar; viabilidad de una solución robusta aún condicionada por el HTML variable, fechas incompletas y extracción no integrada. | Línea que continuará Miguel. Complementa información documental, pero no confirma apertura, disponibilidad de plazas ni reservas. |
| Agenda personal y calendario | Media o alta para organizar actividades alrededor de horarios y compromisos que aporte la persona. | Alta para ordenar datos introducidos por la persona y generar un archivo de calendario; baja para afirmar tiempos de ruta o disponibilidad municipal sin fuentes adicionales. | Idea analizada, no asignada ni aprobada. No convierte el plan en una reserva. |
| Competiciones | Media para público interesado en partidos y clasificaciones; menos transversal para visitas a centros. | Pendiente de una comprobación completa de un recurso vigente, su temporada, actualización y condiciones de uso. | No se recomienda incorporarla por asumir que las fuentes preliminares bastan. Revalidar la fuente si el equipo retoma esta opción. |
| Recordatorio de vencimiento de abono | Media para evitar un vencimiento. | Alta si la persona aporta la fecha y el recordatorio es local; no comprobada para leer o renovar una tarjeta. | No se encontró en la investigación una integración pública validada para consultar cuentas, saldo o renovar. Idea, no tarea acordada. |
| Fisioterapia y servicios de salud deportiva | Alta para el subgrupo que busca información del servicio o cómo contactar. | Media para información publicada; no se validó una API pública de citas o disponibilidad. | Puede ser materia documental si el RAG contiene fuentes adecuadas. No hay base en esta investigación para un agente clínico o para reservar citas. |
| Mapas y rutas | Media para comparar ubicaciones o planificar desplazamientos. | La localización de centros puede apoyarse en datos del catálogo; rutas y tiempos reales requieren una fuente/proveedor de mapas que no se validó aquí. | Una distancia aproximada no equivale a duración de viaje. Idea no aprobada. |
| Sentimiento de reseñas | Complementaria para resumir opiniones. | Baja con la evidencia disponible: no quedó validada una fuente de reseñas suficiente, reutilizable y actualizable. | Las opiniones no certifican el estado técnico, la disponibilidad ni la calidad sanitaria. Idea no aprobada. |
| Consulta de huecos y reservas | Muy alta para usuarios de actividades con demanda. | Baja para el proyecto con lo investigado: no se verificó una API pública de consulta de plazas o inscripción. | Las gestiones pasan por los canales oficiales de deporte y Tarjeta Deporte Madrid. No afirmar que se consultan plazas ni que se puede reservar. |

## FODA de la línea de instalaciones y avisos

| Fortalezas | Debilidades |
|---|---|
| Fuente municipal identificable: catálogo estructurado y fichas oficiales enlazadas. | Los avisos se sirven como HTML; no se identificó una API específica y el formato puede cambiar. |
| Se observaron publicaciones concretas que afectan a centros, espacios y servicios. | Fechas de fin ausentes o ambiguas; la página puede conservar información antigua. |
| Aporta una consulta específica por centro que puede complementar el RAG documental. | La captura y respuesta HTTP no validan actualidad, parser, caché ni fallback en el proyecto. |

| Oportunidades | Amenazas |
|---|---|
| Presentar el texto publicado junto con centro, URL y hora de consulta. | Cambios de página, URL o estructura pueden romper una extracción basada en HTML. |
| Distinguir claramente aviso detectado, fallo de consulta y página consultada sin encabezado detectado. | La persona puede interpretar “sin aviso detectado” como garantía de apertura o servicio disponible. |
| Más adelante, investigar si otras fuentes oficiales documentan cambios con cobertura verificable. | Un aviso antiguo o una respuesta HTTP 200 pueden dar una impresión falsa de vigencia. |

## Qué está acordado y qué no

**Reparto conocido:** Miguel continuará el especialista de Instalaciones y avisos. Alejandra trabaja en supervisor y grafo; Héctor, en la conexión del RAG; David, en Streamlit. El grafo del MVP es síncrono.

**Este documento no decide:** el inventario final de especialistas del grafo, nombres o contratos de tools, estrategia de parsing o fallback, frecuencia de actualización, calendario, rutas, competiciones, recordatorios, reseñas, reservas ni otros trabajos. Esas posibilidades quedan como análisis para una conversación de equipo, no como compromisos de implementación.

## Registro para retomar la investigación

Antes de repetir el barrido general, consultar el inventario de las 82 fichas y los límites de la comprobación en el [handoff técnico](../decisiones/Handoff_Miguel_Especialista_Instalaciones.md). Si se decide implementar avisos, las comprobaciones nuevas deberían centrarse en lo que todavía no se validó: estabilidad del HTML, extracción reproducible de avisos, interpretación prudente de fechas y comportamiento cuando la red o el formato fallen.

Para retomar otra alternativa, empezar por sus vacíos concretos de la tabla. La información de esta comparación es una fotografía de investigación del 13/10/2026; una decisión posterior sobre competiciones, reservas, rutas u otra fuente exige verificar que el recurso siga disponible y sea apto para el uso previsto.

## Fuentes y documentos de referencia

- [Catálogo municipal de centros deportivos](https://datos.madrid.es/dataset/200186-0-polideportivos).
- [API CKAN consultada](https://datos.madrid.es/api/3/action/datastore_search?resource_id=200186-0-polideportivos-csv&limit=100).
- [Repositorio RAG PB01 del equipo](https://github.com/dcruzpuri/project-rag-hmd-deporte-municipal).
- [Handoff de Miguel con el inventario de fichas y resultados](../decisiones/Handoff_Miguel_Especialista_Instalaciones.md).
