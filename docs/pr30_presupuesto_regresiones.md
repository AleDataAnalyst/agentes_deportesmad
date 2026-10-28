# PR #30: presupuesto e historial de herramientas

Revisión local del 28/10/2026, desde `04fa05ea8981ed32c8a767f6cabf9ed9aaadf998`.
Rama de trabajo: `fix/pr30-presupuesto-regresiones`. Sin publicación ni commits.

## Correcciones reproducidas

- Instalaciones resolvía nombres contra el catálogo aunque el LLM ya hubiera
  consultado instalaciones o agotado el presupuesto. Ahora solo decide por reglas
  si no existe consulta municipal y quedan turnos.
- El fallback no contabilizaba la resolución por nombre: podía resolver y después
  consultar avisos cuando solo quedaba un turno. Ambas operaciones se contabilizan
  por separado, igual que el reloj. Las excepciones también consumen el turno.
- Varias consultas municipales sustituían silenciosamente el resultado anterior
  en la salida del nodo. Se conserva su historial y se advierte que la respuesta
  principal representa la última consulta, sin mezclar procedencias.
- Si una tool reutilizaba un diccionario mutable, el ejecutor podía devolver el
  último contenido también para llamadas anteriores. Se copia cada observación
  al registrarla, conservando las aportaciones del ejecutor original.

## Política de presupuesto

`MAX_STEPS_INSTALACIONES` limita el total de propuestas LLM y operaciones por
reglas en una ejecución del nodo. Una propuesta bloqueada o con argumentos
inválidos consume un turno. Cada llamada por reglas al reloj, al resolver de
nombres (que consulta el catálogo) o a la consulta municipal consume otro.
Las inferencias y los reintentos HTTP internos de una tool no se cuentan como
turnos adicionales de herramientas. Este límite no equivale a un límite de
peticiones HTTP individuales.

El fallback continúa con la lista y el presupuesto ya consumidos; no repite una
consulta municipal previa. No se ejecuta ninguna operación externa después de
agotar los turnos, incluido el caso límite cero. Si el resolver consume el último
turno, no se consulta después el aviso. El resultado declara esa limitación.

## Ampliación de diagnóstico, separada de la agregación de respuestas

En modo `llm`, `ToolResult.data['llamadas_tools']` contiene una copia de la lista
ordenada del ejecutor y de las operaciones del fallback. Cada entrada conserva
`paso`, `tool`, `args`, `status`, `preview` y `resultado`. Las operaciones por reglas
usan `preview` vacío; su resultado completo permanece en `resultado`. Ante una
excepción por reglas se guarda un error genérico, sin exponer su detalle interno.
Un fallo del modelo sigue visible en advertencias y debug; no es otra tool.

Es una clave adicional del diccionario de diagnóstico existente: no modifica
la dataclass ToolResult, los campos autorizados por las guardias ni el contrato
del reloj de Miguel. La lista incorpora también bloqueos, errores e intentos
inválidos, sin confundir su estado de ejecución con evidencia útil. La traza
LLM contiene un evento por entrada, con argumentos/resultado filtrados mediante
`sin_secretos` y vistas previas acotadas.

`answer`, `evidence` y los metadatos municipales principales conservan la última
consulta, incluso si esta falla. Si hay varias, una advertencia explícita explica
la selección y remite al historial. El historial conserva por separado fuente,
origen, fecha y captura histórica recibidos de cada herramienta. No se fusionan
catálogos, avisos, errores o capturas de fechas distintas. La síntesis actual no
consume automáticamente este historial. Una agregación de respuestas requeriría
acordar otra política y modificar sus consumidores por separado.

Impacto: más datos en el estado/checkpoint en modo LLM, acotados por el número de
llamadas (por defecto tres), pero no por el tamaño del resultado de cada tool.
No añade estado entre pedidos ni operaciones externas nuevas. Se mantiene la
salida por reglas del reloj y sus guardias de observación.

## Validación local

Windows, Python 3.14.2, pytest 8.4.2, entorno virtual ya instalado. Sin instalar
dependencias, copiar `.env`, modificar configuración persistente o usar recursos
reales. Runner temporal en `tmp/run_offline.py`: desactiva dotenv y autoload de
plugins, activa los modos reglas y los flags offline de Hugging Face, y bloquea
`socket.connect`/`socket.getaddrinfo` antes de ejecutar pytest. Solo se permite
la llamada de la biblioteca estándar que crea `socketpair` local para asyncio
en Windows; no se permite HTTP ni resolución DNS de servicios. Los tests que
necesitan modo LLM lo activan explícitamente y usan dobles.

| Fase | Resultado exacto |
| --- | --- |
| Línea base de seis módulos, antes de editar | 74 passed, 13 warnings, 1.34 s |
| Regresiones ampliadas, producción original | 9 failed, 14 passed, 13 warnings, 1.08 s |
| Primera corrección dirigida | 1 failed, 83 passed, 13 warnings, 1.32 s; diferencia de argumento posicional/nominado del resolver, corregida preservando la llamada original |
| Selección dirigida tras ese ajuste | 84 passed, 13 warnings, 1.24 s |
| Primera suite completa | 8 failed, 922 passed, 50 skipped, 17 warnings, 24.10 s; el runner bloqueaba socketpair de asyncio, corregido solo en el runner temporal |
| Prueba adicional de diccionario reutilizado y clientes | 1 failed, 64 passed, 13 warnings, 4.67 s; confirmó la pérdida por alias, corregida en el ejecutor |
| Selección final ampliada de 12 módulos | 228 passed, 13 warnings, 8.22 s |
| Suite completa final, sin --run-integration | 935 passed, 50 skipped, 15 warnings, 22.77 s |

La sintaxis se validó con `ast.parse` en los tres archivos Python afectados.
`git diff --check` pasó. Las omisiones son las pruebas de integración desactivadas
por defecto. Los avisos finales son deprecaciones de LangChain Community,
LangSmith y Google GenAI; no se alteraron dependencias para suprimirlos.

Se mantienen sin cambios la herramienta/exportación/tests originales de Miguel,
el nodo documental, runtime, las guardias, la puerta de integración de pytest y
las correcciones de OCR/visión incorporadas por #32.

## Pendientes y criterio de integración

Los defectos reproducidos aquí quedan corregidos y validados con dobles sobre
este árbol local. Antes de mergear #30, la usuaria debe publicar el diff acordado,
contrastar el nuevo head y ejecutar CI/revisión sobre ese mismo contenido.
Esta evidencia no certifica aceptación real de LLM, RAG, índice, visión ni fuentes
municipales. No se reabren hallazgos históricos sin una reproducción nueva.

Mejoras opcionales separadas: agregar respuestas de varias consultas, limitar
el tamaño de cada observación guardada y enriquecer la presentación del historial
en los clientes. Ninguna está implementada ni se exige para pasar las regresiones
de este alcance. El runner y los temporales de pruebas son artefactos ignorados
locales, no cambios de configuración del proyecto.
