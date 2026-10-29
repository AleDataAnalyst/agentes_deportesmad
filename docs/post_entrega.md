# Mantenimiento posterior a la entrega

Inicio: **26/10/2026**. Rama: `fix/post-entrega-correcciones-tests-mejoras`.
Base: `main`, commit `18ca29d` (integración de la PR #28).

Este trabajo se realiza después de la entrega del 25/10/2026. Las evidencias y
resultados históricos de esa entrega se conservan con su fecha original. Este
registro centraliza la continuación para el conjunto del proyecto y distingue
las correcciones verificadas de los pendientes que necesitan recursos reales.

## Correcciones y mejoras implementadas

| Área | Problema | Resultado y pruebas |
| --- | --- | --- |
| Imports y montaje | El import de `rag` cargaba lógica, indexación y modelos al usar limpieza/carga. `llm.py` conservaba un import RAG redundante y runtime importaba visión al construir el servicio. | API pública RAG diferida, tool RAG diferida, eliminación del import redundante y carga diferida de visión en runtime. Regresiones en procesos nuevos en `test_import_boundaries.py`; se conserva la inyección de `responder`. |
| Contrato RAG | La normalización podía lanzar fuera del límite de errores; al fallar, diagnóstico omitía sus campos. | Normalización dentro del límite y diagnósticos presentes también ante error. Regresiones de observaciones malformadas y errores de proveedor en `test_rag_error_boundary.py`. |
| Especialista documental | Una tool fallida podía aportar respuesta como evidencia; las excepciones no generaban evento. El filtrado de fuentes podía dejar texto procedente de fuentes excluidas. | Solo se acepta observación exitosa, con texto, fuentes y sin abstención/error. Se registra cada llamada, incluidos fallos; una observación con fuentes mixtas se omite completa. Regresiones en `test_node_documental.py`. |
| Imagen por pedido | Visión se llamaba como función aunque es una tool con `.invoke`; una abstención documental impedía describir una imagen. | Visión usa `.invoke` y puede aportar evidencia independiente, identificada como visual y sin acreditar normativa. Se consulta primero la imagen válida y luego RAG, con presupuesto compartido. Pruebas de independencia y límite de llamadas. |
| Tool de visión | PNG/WebP se enviaban como JPEG; fuentes estructuradas incumplían `list[str]` y rompían el adaptador común. La clave quedaba capturada al importar. | MIME por extensión, fuentes como rutas de texto, clave leída al consultar, alias de demostración resuelto y error JSON controlado. Pruebas de payload y recorrido tool → nodo → adaptador con proveedor doble en `test_vision.py`. |
| PDF/OCR | El conversor solo retenía filas Markdown: descartaba OCR plano y bloques TAB sin tablas. | Se conserva el bloque completo cuando no contiene filas Markdown aprovechables, con procedencia y número de bloque. Regresiones de OCR, TAB y fallback directo. |
| Suite del proyecto | Un archivo ejecutaba consultas al importarse; otro abría Chroma durante colección. Algunos tests parcheaban un diccionario con `setattr`, usaban rutas inexistentes, omitían `Path` o invocaban una firma privada antigua. Un test escribía sobre un asset versionado. | Evaluación parametrizada con aserciones, imports reales dentro de tests de integración, activación explícita `--run-integration`, correcciones de fixtures/contratos y archivos temporales propios. |

La política de fuentes mixtas es conservadora: si una observación combina
fuentes autorizadas y excluidas, se descarta su texto completo porque no existe
atribución por fragmento. Una evidencia visual tampoco sustituye una fuente
normativa. No se modifica el requisito de decisión humana del plan vigente.

## Validación

Entorno local: Windows, Python 3.14. Las dependencias presentes permiten ejecutar
la suite local; no se ha reinstalado ni certificado un entorno limpio completo
de modelos RAG.

Comando de suite completa, con temporal dedicado por los permisos de Windows:

```console
python -m pytest -q -p no:cacheprovider --basetemp=tmp/pytest-post-entrega-final
```

Resultado: **863 pruebas superadas, 50 omitidas y 0 fallos**, en 36,46 segundos.
Las 50 omisiones corresponden a integración real desactivada por defecto.
Se observaron dos avisos de deprecación de dependencias (LangChain Community
y Google GenAI), registrados en el backlog. `git diff --check` también pasó.

Las pruebas de integración se activan con:

```console
python -m pytest -q -p no:cacheprovider --run-integration -m integration
```

Activarlas puede consultar modelos, consumir cuota y acceder al índice configurado.
No se ejecutaron durante este mantenimiento. La suite local incluye pruebas
de CLI, Streamlit, HITL, aislamiento de conversaciones, supervisor, instalaciones,
fallbacks, filtros de secretos, carga y limpieza documental y transporte de imagen.

## Pendientes del conjunto del proyecto

| Prioridad | Área | Pendiente y criterio de cierre |
| --- | --- | --- |
| P1 | RAG e índice | Preparar un índice poblado y compatible, con proveedor/modelo, dimensión, colección, versiones, ubicación y checksum documentados. Ejecutar aceptación con respuesta/fuente esperadas, abstención y fallo controlado. La configuración actual del entorno no acredita esto. |
| P1 | Supervisor LLM | Seleccionar proveedor/modelo disponible y ejecutar la aceptación real del router. Conservar fallback, límites de inferencia y rutas validadas; pruebas con dobles no cierran esta aceptación. |
| P1 | Instalaciones y avisos | Validar catálogo y avisos municipales reales, procedencia y fallback histórico fechado. Conservar error o abstención ante indisponibilidad. Las regresiones locales no acreditan actualidad municipal. |
| P1 | Visión y aceptación conjunta | Ejecutar imagen real con modelo configurado, fuentes visibles en CLI/Streamlit, RAG compatible y aprobación/rechazo del plan del mismo hilo. Las pruebas nuevas verifican transporte y contratos con proveedor doble. |
| P2 | Dependencias y automatización | Reproducir la instalación en un entorno limpio, revisar duplicados de requirements y fijar un conjunto compatible. Añadir CI de la suite local sobre ese entorno y registrar Python/SO. Revisar avisos de deprecación de LangChain Community y Google GenAI. |
| P2 | Ingesta documental | Ampliar evaluación a PDF/OCR reales, bloques que mezclan narrativa con tablas y caracteres escapados en Markdown; comprobar que se conserva el contenido y su atribución antes de reindexar. |
| P2 | Clientes | Ampliar aceptación manual con fallos reales, recuperación del hilo, imágenes y filtrado de diagnósticos. Actualizar capturas cuando cambie el comportamiento, conservando fechadas las evidencias históricas. |
| P2 | Perfiles y benchmark | Comparar los tres perfiles con modelos reales y el corpus acordado, registrando calidad, latencia y consumo. Los resultados con dobles no equivalen a rendimiento real. |
| P3 | Reportes y auxiliar | Definir el alcance de `preparar_reporte` y de la auxiliar determinista pendiente, su contrato, salida y tests antes de conectarlos. La indisponibilidad actual debe seguir siendo explícita. |
| P3 | Memoria y persistencia | Acordar historial conversacional y almacenamiento duradero. Si se incorporan, comprobar recuperación tras reinicio, aislamiento de sesiones y migración de checkpoints. Actualmente el servicio conserva estado en memoria del proceso. |
| P3 | Contratos y operaciones externas | Resolver el TODO de `SupervisorDecision` y el alcance de `PendingAction`. Reservas, pagos o envíos requieren autorización, persistencia e idempotencia de la operación externa. El cierre actual sigue siendo informativo. |

No se dan por resueltos los pendientes sin la evidencia indicada. Los handoffs
anteriores conservan el contexto de reparto y las instrucciones de aceptación;
sus hallazgos de imports, tests y presupuesto pueden describir estados anteriores.
Cada continuación debe actualizar esta tabla con la prueba y el resultado de cierre.

## Integración

La rama se revisa contra `develop`. El workflow existente solo admite PR de
`develop` hacia `main`; no debe eludirse para integrar este mantenimiento.
La creación de la rama y los cambios locales no publican ni despliegan el proyecto.
