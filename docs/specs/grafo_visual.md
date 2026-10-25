# Grafo visual actualizado

Estado revisado el 25/10/2026, montaje de #22 con #23 integrada desde develop.
Los clientes consumen `AgentService` mediante runtime; no son nodos del grafo.

![Clientes, supervisor, especialistas y revisión humana](grafo_visual.svg)

## Archivos y regeneración

```powershell
.\.venv\Scripts\python.exe -m scripts.ver_grafo
```

- `grafo_visual.svg`: esquema explicativo para estudiar o presentar.
- `grafo_actual.mmd`: topología Mermaid exportada automáticamente por LangGraph.
- `grafo_actual.txt`: representación ASCII exportada por LangGraph.

El SVG es la única vista explicativa mantenida, para evitar dos imágenes que
puedan divergir.

El comando compila la demo que usa el mismo `build_graph`; no procesa pedidos,
no aprueba planes, no importa el RAG y no consulta servicios externos.

## Qué muestra el esquema

- CLI y Streamlit conectados mediante `crear_servicio(modo="real")`, con
  consultas, fuentes, diagnóstico y decisión humana sobre el plan vigente.
- Streamlit incluye avisos de respuesta, abstención, error y limitaciones.
  Guarda JPG/PNG, pero todavía no envía `image_id` al servicio.
- Documental conectado por adaptador y puerta pública diferida hasta la consulta.
  Las mejoras de #21 están pendientes de integración; el índice compatible y la
  aceptación RAG real siguen pendientes.
- Instalaciones conectado mediante su nodo público, con catálogo, avisos,
  fuentes y fallback histórico. La aceptación externa real sigue pendiente.
- Supervisor seleccionado en runtime: `SUPERVISOR_MODE=reglas` o `llm`, con
  Google/Ollama y modelo explícito en modo LLM. Se conserva inyección manual.
  Python valida las rutas, aplica fallback y limita las iteraciones.
- Documental, instalaciones y síntesis vuelven al supervisor. No hay ejecución
  paralela. FINISH con plan válido alcanza la interrupción antes de aplicar;
  sin plan válido pasa por síntesis.
- Aprobar y rechazar reanudan el mismo hilo. Ambas decisiones pasan por aplicar
  y llegan a END; rechazar deja done=False y permite otro pedido.

Router, pausa y decisión son controles explicativos, no nodos registrados extra.
La permanencia del estado y los registros del servicio es de proceso.

El esquema refleja el montaje del grafo y distingue las integraciones pendientes.
El montaje está probado con dobles; no acredita aceptación conjunta con modelo,
RAG, HTTP y clientes reales.

## Cómo quedaría al integrar el documental

La integración de #21 conserva el grafo principal y su puerta pública documental.
El especialista concentra RAG y la tool de imagen; visión no es una ruta
independiente del supervisor actual. En la versión revisada de #21, la imagen
requiere una respuesta documental válida y presupuesto disponible.

Para completar el recorrido multimodal falta acordar y conectar `image_id` desde
el cliente por el servicio y el adaptador. El README muestra ese recorrido con
flechas discontinuas, como objetivo pendiente. No se modifica esa interfaz en
esta actualización documental. `preparar_reporte` continúa no disponible.

La integración debe preservar la carga diferida del RAG y las correcciones del
adaptador Google de #22, junto con las mejoras válidas de Héctor. Los detalles
están en [integración real](integracion_real.md). El cierre requiere aceptación
con modelo disponible, índice compatible y fuentes externas reales.
