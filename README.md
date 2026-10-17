# agentes_deportesmad

Project Break 02 · Asistente de deporte municipal con agentes y LangGraph.

El proyecto reutilizará el RAG del equipo como herramienta y añadirá supervisor, especialistas, herramientas controladas, aprobación humana, memoria y clientes CLI y Streamlit.

## Estado del proyecto

Inicio de desarrollo sobre una **estructura base**. Los módulos con docstrings indican responsabilidades previstas; no acreditan implementación ni pruebas.
El RAG se incorporará en `rag/` tras adaptar su integración.

La [base de infraestructura de síntesis y aplicar](docs/specs/infra_sintetizar_aplicar.md)
está separada del montaje del grafo: valida las implementaciones inyectadas
y conserva la pausa HITL. La lógica de esos nodos y la conexión de especialistas
reales siguen pendientes de confirmación; la demo continúa usando dobles.

Las capacidades descritas en este README son objetivos del PB02, no una
confirmación de que ya funcionan. Los comandos de ejecución, dependencias
operativas y evidencias se documentarán al integrar cada parte.

### Avance verificado — backend síncrono con dobles

Implementados estado, contratos internos provisionales, supervisor con fallback
y límite, grafo con nodos inyectados y `AgentService` compartido entre turnos.
Las pruebas usan especialistas, síntesis y aplicar simulados explícitamente:
comprueban pausa, aprobación/rechazo, reset, aislamiento de hilos e idempotencia.
Esto no acredita especialistas ni tools reales, CLI o Streamlit funcionales.
`MAX_ITER` se configura desde el entorno (default 8); `settings.py` no carga
`.env` automáticamente. Los contratos externos y el proveedor LLM siguen pendientes.

En un entorno virtual, instalar y comprobar este backend desde la raíz:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Versiones utilizadas en la comprobación: LangGraph 1.2.11 y pytest 8.4.2.
Los imports del backend también se comprobaron en Python 3.12. Estos comandos
ejecutan pruebas sin claves ni red; aún no arrancan el producto CLI/Streamlit.
El contrato de cliente está en [docs/specs/contratos.md](docs/specs/contratos.md)
y la correspondencia con el enunciado en
[docs/specs/seguimiento_pb02.md](docs/specs/seguimiento_pb02.md).

### Demostración del grafo sin servicios externos

Desde la raíz, con las dependencias del backend instaladas:

```powershell
python -m agentes.demo
python -m agentes.demo --decision aprobar
python -m agentes.demo --decision rechazar
python -m agentes.demo --escenario abstained
python -m agentes.demo --escenario error
python -m agentes.demo --interactivo
```

El comando sin decisión muestra el plan pendiente. La salida JSON identifica
todos los datos como **demo simulada**. El modo interactivo pide aprobar,
rechazar o salir; ninguna aprobación se toma por defecto. Estos comandos
demuestran el esqueleto y no sustituyen la CLI final ni el RAG/tools reales.
Los checkpoints se pierden al finalizar el proceso.

Para conectar un cliente de prueba, conservar el servicio entre turnos:

```python
from agentes.demo import crear_servicio_demo

servicio = crear_servicio_demo()  # conservar esta instancia en el cliente
hilo = servicio.nueva_conversacion()
estado = servicio.procesar_turno("Pedido de prueba", hilo)
# Después de que la persona decida; True aprueba y False rechaza:
estado = servicio.resolver_plan(hilo, True, plan_id=estado["plan_id"])
```

En Streamlit, conservar `servicio` e `hilo` entre reruns, mostrar el plan antes
de resolverlo y usar los botones para enviar la decisión. No ejecutar la línea
de resolución automáticamente al recibir el plan. David integra esa UI.
La [especificación de demo](docs/specs/demo.md) describe escenarios y aceptación.

## Visualización del grafo

La explicación del recorrido síncrono, el supervisor, el router y la pausa
de aprobación humana está en
[Flujo de supervisor y grafo](docs/specs/flujo_supervisor_grafo.md).

Para generar el dibujo ASCII del grafo con los nodos simulados:

```bash
python -m pip install -r requirements-dev.txt
python -m scripts.ver_grafo
```

El script muestra el dibujo en la terminal y lo guarda en
`docs/specs/grafo_actual.txt`. La visualización utiliza `grandalf`,
incluido en las dependencias de desarrollo.

Este dibujo representa las conexiones del grafo; no ejecuta consultas
al RAG ni a la API y no acredita su integración.

## Reparto acordado — 13 de octubre de 2026

Este reparto sustituye la propuesta anterior. Las responsabilidades pendientes no se consideran asignadas automáticamente a quien inicia el grafo.

| Responsable | Responsabilidad confirmada | Alcance inicial |
|---|---|---|
| Alejandra | Supervisor y esqueleto ejecutable del grafo | Definir rutas, límites y fallback; conectar nodos simulados para desbloquear el desarrollo. |
| Héctor | Especialista que conecta el RAG y adaptación del RAG existente | Preparar el especialista documental, el conector y los ajustes necesarios de imports, rutas, dependencias y contrato de consulta. |
| David | Streamlit | Construir el cliente del agente: chat, fuentes, imagen, aprobación/rechazo, nueva conversación y debug, conforme al contrato común. |
| Miguel | Especialista de Instalaciones y avisos | Continuar el especialista con el handoff del catálogo y las fichas oficiales; concretar módulos y contratos compartidos antes de integrar. |

Cuando Héctor termine la integración del especialista RAG, compartirá parte de las responsabilidades de la lógica del agente con quien inicia supervisor y grafo. Las tareas concretas de esa segunda etapa se acordarán y registrarán antes de empezar a editarlas.

Las tools restantes y otras tareas se repartirán progresivamente con Miguel y David conforme tengan capacidad. David mantiene Streamlit como responsabilidad confirmada; cualquier ampliación requiere un acuerdo explícito.

## Módulos del trabajo inicial

Los paths corresponden a la estructura base. Si cambia la organización,
actualizaremos esta tabla junto con los contratos de integración.

| Bloque | Módulos principales | Dependencias y coordinación |
|---|---|---|
| Supervisor y grafo síncrono | `agentes/nodes/supervisor.py`, `agentes/graph.py` | Alejandra avanza con `agentes/contracts.py` y `agentes/state.py`; revisar las interfaces que consumen Héctor y David. |
| Especialista documental y conexión RAG | `agentes/nodes/documental.py`, `agentes/tools/rag.py`, `rag/` | Héctor prepara la conexión contra el contrato compartido; conservar respuesta, fuentes, abstención y error. |
| Streamlit | `app.py`, `clientes/streamlit_app.py`, `clientes/hitl.py`, `clientes/debug.py` | David puede trabajar con resultados simulados del contrato de cliente mientras avanza el backend. |
| Handoff de Instalaciones y avisos | `docs/decisiones/Handoff_Miguel_Especialista_Instalaciones.md` | Inventario de la API del catálogo y las fichas municipales para Miguel. Los módulos de implementación y sus contratos se concretarán antes de integrar. |

La adaptación del RAG se centra primero en lo necesario para conectarlo. No
rehacer ingesta, chunking o embeddings salvo que se demuestre que hace falta.
Comprobar que sigue respondiendo después de ajustar imports, rutas y entorno.

## Responsabilidades aún por repartir

- Segundo especialista y sus instrucciones/herramientas.
- Fuente externa con fallback local real y fechado.
- Herramienta auxiliar determinista.
- Tool multimodal de imagen a texto.
- Registro de tools, allowlist y validación de argumentos.
- Síntesis del plan.
- Backend HITL, nodo aplicar y checkpointer.
- API común de clientes y CLI.
- Pruebas de integración del flujo síncrono del MVP.

Los **botones HITL de Streamlit** pertenecen al cliente de David. La pausa,
validación de la decisión y reanudación del grafo pertenecen al backend,
cuya asignación detallada queda pendiente.

Cada responsable incluye pruebas y documentación de su parte. El informe y la
presentación se construyen con aportaciones de todos; no se asigna todo el cierre
a una única persona.

## Primer hito compartido

1. Acordar estado mínimo, entradas/salidas de nodos y tools y contrato de clientes.
2. Montar supervisor y grafo con especialistas, síntesis y aplicar simulados.
3. Verificar el recorrido pedido → especialistas → plan → pausa antes de aplicar.
4. Sustituir el especialista documental simulado por el de Héctor cuando esté listo.
5. Conectar Streamlit y repartir la siguiente tanda de tareas concretas.

Las simulaciones se identifican explícitamente y cumplen los mismos contratos
que las implementaciones reales. No sustituyen las tools reales de la entrega
final. Deben existir al menos dos especialistas reales al cerrar el PB02.

## Contratos para avanzar con autonomía

Documentarlos en `docs/specs/contratos.md`:

La recepción e integración de las interfaces de Héctor y Miguel se prepara con
la [especificación de integración de especialistas](docs/specs/integracion_especialistas.md).
Completar su ficha y mapeo con el contrato real antes de implementar cada adaptador.

- Campos del estado, propietario de cada actualización y reset por pedido.
- Resultados de tools: datos, evidencias, abstención, error y metadatos.
- Actualización devuelta por cada nodo.
- Operaciones de cliente: enviar mensaje, registrar imagen, consultar estado,
  aprobar/rechazar y nueva conversación.
- Semántica de `thread_id`, `request_id`, `plan_id`, `done` y fase HITL.

No hace falta que otra persona termine su implementación para probar un módulo:
se trabaja contra ejemplos del contrato y se integra progresivamente.

## Estructura prevista

| Carpeta o módulo | Responsabilidad |
|---|---|
| `agentes/contracts.py`, `state.py` | Contratos y estado compartido |
| `agentes/settings.py`, `llm.py` | Configuración y proveedor de modelos |
| `agentes/graph.py`, `agent.py` | Grafo y API común |
| `agentes/nodes/` | Supervisor, especialistas, coordinador, síntesis y aplicar |
| `agentes/tools/` | Registro, conector RAG, externa, visión y auxiliares |
| `clientes/` | CLI, Streamlit y presentación de HITL/debug |
| `rag/` | RAG PB1 reutilizado |
| `scripts/` | Preparación y comprobaciones aisladas |
| `tests/` | Pruebas de contratos, tools, grafo y clientes |
| `docs/specs/` | Especificaciones y criterios de aceptación |
| `entregables/` | Informe y evidencias |

El MVP prioriza un grafo síncrono. La asincronía y el paralelismo no se han acordado
con el equipo y quedan fuera del alcance actual; podrían valorarse después.

## Flujo Git del PB02

- `main`: base inicial y, posteriormente, código estable de entrega.
- `develop`: integración del equipo.
- `feature/...`: ramas de trabajo creadas desde `develop`.
- Integrar mediante PR hacia `develop`; resolver conflictos en la rama de trabajo.
- Cada integrante debe acreditar al menos una PR revisada y mergeada.
- Pasar a `main` cuando la entrega esté integrada y CLI/Streamlit sean ejecutables.

Ramas iniciales sugeridas:

| Trabajo | Rama |
|---|---|
| Supervisor y grafo | `feature/supervisor-grafo` |
| Especialista y conector RAG | `feature/especialista-rag` |
| Streamlit | `feature/streamlit-ui` |
| Nueva tarea acordada | `feature/nombre-de-la-tarea` |

Cada PR indica alcance, módulos, contrato afectado, comprobaciones realizadas y
limitaciones. Separar comentarios BLOQUEANTE, PREGUNTA y SUGERENCIA. Los cambios
de contrato requieren revisión de sus consumidores. Aprobar el último commit
antes de integrar; registrar sustituciones del revisor cuando sean necesarias.

## Configuración y archivos excluidos

Versionar `README.md`, `.gitignore`, `requirements.txt`,
`requirements-dev.txt` y `.env.example`. Las versiones de dependencias y valores
operativos se concretarán durante la implementación.

No subir `.env`, claves, entornos virtuales ni índices vectoriales pesados.
Documentar cómo preparar el índice del RAG y cómo ejecutar el proyecto cuando
esas operaciones estén verificadas.

## Criterios de cierre

- Supervisor, al menos dos especialistas, síntesis y aplicar con HITL.
- RAG completo, fuente externa con fallback, auxiliar y multimodal reales.
- Allowlist y límites controlados en Python.
- Checkpointer y continuidad mediante `thread_id`.
- Aprobación/rechazo, fuentes y debug desde CLI y Streamlit.
- README reproducible, informe de decisiones, evidencias y presentación.
- Contribuciones y revisiones individuales acreditadas en Git.

## Adenda — handoff de instalaciones y avisos (13 de octubre de 2026)

En la actualización del reparto, Miguel continuará el especialista de **Instalaciones y avisos**. Alejandra sigue con supervisor y grafo; Héctor, con la conexión del RAG; David, con Streamlit. Coordinar con Héctor y Alejandra los contratos antes de integrar módulos compartidos.

La comprobación registró la API CKAN del catálogo (82 registros) y las URLs `CONTENT-URL` de las fichas municipales. Las 82 fichas respondieron HTTP 200 en las consultas del 13/10/2026; en 12 se detectó un encabezado “Aviso a usuarios/as” (13 bloques). Las páginas de avisos son HTML; este resultado no valida vigencia, una integración del proyecto ni la ausencia de incidencias en las demás fichas.

El inventario de IDs, distritos, URLs y resultados observados está en [el handoff técnico del especialista](docs/decisiones/viabilidad_especialista_instalaciones_avisos.md). Esta adenda registra el reparto y la evidencia disponible; no amplía el alcance a otras tools o especialistas.
