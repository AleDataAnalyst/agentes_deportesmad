# Grafo visual actualizado

Estado revisado el 20/10/2026. Los clientes consumen `AgentService`, no son nodos
del grafo. La ampliación local de CLI queda fuera de esta entrega del grafo.

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

- CLI: ampliación local pendiente de entrega separada; no se incluye aquí su
  implementación ni se acredita una CLI operativa con este commit.
- En la base actual de esta rama, `app.py` y `clientes/streamlit_app.py` son
  estructura base. Su integración corresponde a David. La revisión histórica
  `revision_compatibilidad_streamlit_c9a3d45.md` describe otro commit y no
  acredita una UI ejecutable en esta rama.
- Documental conectado por adaptador y puerta pública. El índice configurado
  sigue pendiente y no se acredita consulta RAG real.
- Instalaciones tiene ruta, pero runtime declara `abstained`, `available=False`
  y una limitación hasta recibir el especialista de Miguel.
- Supervisor por reglas con fallback y límites. El proveedor LLM es inyectable,
  pero no está conectado en runtime.
- Documental, instalaciones y síntesis vuelven al supervisor. No hay ejecución
  paralela. FINISH con plan válido alcanza la interrupción antes de aplicar;
  sin plan válido pasa por síntesis.
- Aprobar y rechazar reanudan el mismo hilo. Ambas decisiones pasan por aplicar
  y llegan a END; rechazar deja done=False y permite otro pedido.

Router, pausa y decisión son controles explicativos, no nodos registrados extra.
La permanencia del estado y los registros del servicio es de proceso.

El esquema refleja el montaje del grafo y distingue las integraciones pendientes.
No acredita ejecución real de RAG/HTTP ni de los clientes propuestos.
