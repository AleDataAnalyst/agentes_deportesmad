# SDD de supervisor y grafo: preparación para integrar especialistas

## Estado y alcance

Este documento recoge mi propuesta de desarrollo guiado por especificaciones
para supervisor y grafo síncrono.

Describe el comportamiento esperado, las decisiones de coordinación,
los criterios de aceptación y los puntos pendientes de integración.
Se actualizará cuando se reciban y revisen los contratos de los especialistas.

Los formatos provisionales aquí descritos permiten avanzar con dobles.
No se consideran contratos acordados por el equipo. Las interfaces compartidas
y su estado de validación se documentan en `contratos.md`.

# Especificación de integración de especialistas

**Identificador:** SPEC-INTEGRACION-01 · **Versión:** 0.1 · **Fecha:** 14/10/2026  
**Estado:** propuesta de integración; contratos externos pendientes de recepción.  
**Objetivo:** integrar cada contrato real mediante un adaptador pequeño, conservando
fuentes, abstenciones y errores, sin rehacer el especialista ni el RAG.

## 1. Cómo utilizar este documento

1. El responsable entrega su contrato y ejemplos reales con la ficha de la sección 3.
2. Completar el mapeo de la sección 4 antes de escribir el adaptador.
3. Resolver solo los desacuerdos que afectan a la integración; registrar los demás
   como pendientes con responsable y efecto conocido.
4. Implementar y probar el adaptador aislado; después sustituir un doble en el grafo.
5. Verificar los escenarios de aceptación y adjuntar la evidencia a la PR.

Mantener una ficha y un mapeo por especialista, dentro de este documento o en un
archivo enlazado. Ningún campo marcado «pendiente» se interpreta como confirmado.
Una interfaz nueva debe actualizar ficha, mapeo y pruebas en la misma PR.

## 2. Alcance y referencias

El alcance actual es **síncrono**: supervisor, documental, instalaciones,
síntesis y aplicar con pausa humana. Los adaptadores se inyectan en
`AgentService`; el montaje no importa implementaciones de especialistas.

Referencias de requisitos y comportamiento:

- [README local y reparto](../../README.md).
- [Contrato interno y API de clientes](contratos.md).
- [Seguimiento del PB02](seguimiento_pb02.md).
- README del PB02 del bootcamp.
- Guía HTML del PB02.

El PB02 requiere herramientas reales, RAG completo, límites en Python y HITL en
CLI y Streamlit. Esta especificación permite preparar la integración; completarla
no acredita por sí sola todos los requisitos de entrega.

### Responsables y situación de partida

| Rol del grafo | Responsable confirmado | Alcance confirmado | Contrato externo |
|---|---|---|---|
| `documental` | Héctor | Especialista documental y conexión del RAG existente | Pendiente |
| `instalaciones` | Miguel | Especialista de instalaciones y avisos | Pendiente |
| Supervisor y montaje | Alejandra | Rutas, límites, fallback e integración del grafo | Contrato interno implementado; integración real pendiente |
| Cliente Streamlit | David | Presentar resultados, fuentes, debug y decisión HITL | API interna documentada; revisar su consumo |

La síntesis, aplicar, las tools restantes y la CLI conservan el reparto pendiente
del README. Este documento no les asigna un responsable automáticamente. Los
docstrings de módulos base y `RAG_CALLABLE` en `.env.example` no prueban una firma
real ni amplían las responsabilidades acordadas.

## 3. Ficha de recepción del contrato

Duplicar esta ficha para cada especialista. El responsable debe aportar los
datos desde su implementación, no adaptar su implementación a una firma supuesta.

| Dato | Valor que debe completar el responsable |
|---|---|
| Rol / responsable / fecha | Pendiente |
| Enlace al contrato y versión | Pendiente |
| Rama y commit revisable | Pendiente |
| Módulo y callable público importable | Pendiente |
| Firma exacta, tipos y valores predeterminados | Pendiente |
| Entrada de ejemplo válida | Pendiente |
| Entrada inválida y comportamiento esperado | Pendiente |
| Salida exacta: texto, dict, dataclass u otro tipo | Pendiente |
| Caso con respuesta válida y fuentes | Pendiente |
| Caso sin datos/evidencia | Pendiente |
| Caso con fallo técnico | Pendiente |
| Excepciones que puede lanzar | Pendiente |
| Síncrono o asíncrono; streaming, si existe | Pendiente |
| Campos de fuentes y fragmentos | Pendiente |
| Significado de score, si existe | Pendiente |
| Fallback real: procedencia, fecha y cómo se identifica | Pendiente / no aplica |
| Limitaciones o resultados parciales | Pendiente |
| Tools del rol y allowlist efectiva | Pendiente |
| Límite de tools, timeout y política de reintentos | Pendiente |
| Eventos de tool: nombre, argumentos, estado y preview | Pendiente |
| Dependencias y variables de entorno; sin valores secretos | Pendiente |
| Preparación previa: corpus, índice o datos; comando | Pendiente |
| Comando para probar el especialista sin UI | Pendiente |
| Campos del estado que necesita leer, si recibe estado | Pendiente |
| Campos que escribe, si ya es un nodo LangGraph | Pendiente |
| Restricciones de uso y efectos externos de la llamada | Pendiente |

**Entrega mínima:** contrato versionado, callable accesible, ejemplos de respuesta,
abstención y error, y comando de prueba aislada. Si un caso no aplica, explicar
por qué; no sustituirlo por un ejemplo de éxito.

### Cuestiones específicas que cerrar

**Documental:** cómo consultar el RAG sin Streamlit, qué identifica cada fuente,
cómo comunica abstención y cómo preparar el índice fuera del turno. Confirmar la
firma real; `responder(pregunta, top_k=None)` sigue siendo una previsión del módulo
base. Conservar el RAG PB1: no rehacer ingesta, chunking o embeddings por el adaptador.

**Instalaciones:** filtros soportados y su validación, identificación de centros,
procedencia del catálogo y de cada aviso, fecha de consulta y semántica del fallback.
No interpretar la ausencia de aviso como garantía de ausencia de incidencias ni
deducir plazas disponibles o reservas a partir del catálogo.

## 4. Mapeo del contrato real al contrato interno

Los campos de [contracts.py](../../agentes/contracts.py) son una propuesta interna.
Completar la columna «origen real» con nombres o reglas concretas del contrato
recibido. Si no existe una equivalencia, registrar una decisión antes de codificar.

| Destino interno | Origen real / regla acordada | Criterio de integración |
|---|---|---|
| `ToolResult.status` | Pendiente | Distinguir `ok`, `abstained` y `error`; no inferirlo solo de texto libre ambiguo |
| `ToolResult.answer` | Pendiente | Texto del resultado; puede estar vacío en abstención/error |
| `ToolResult.evidence` | Pendiente | Conservar las fuentes disponibles, sin crearlas si faltan |
| `Evidence.source` | Pendiente | Identificador o localización trazable de la fuente |
| `Evidence.content` | Pendiente | Fragmento realmente aportado; no fabricarlo a partir de una URL |
| `Evidence.score` | Pendiente / no aplica | Mantener su significado; usar `None` si no existe |
| `Evidence.metadata` | Pendiente | Metadatos reales de procedencia, fechas u otros datos documentados |
| `ToolResult.error` | Pendiente | Fallo técnico comprensible, sin secretos ni traceback expuesto al usuario |
| `ToolResult.data` | Pendiente | Datos estructurados, limitaciones, fallback y eventos que deban conservarse |

Si solo se entregan URLs sin fragmentos, decidir cómo conservarlas en `data` o
revisar `Evidence` con sus consumidores; no inventar contenido para satisfacer
el formato provisional. No imponer un rango común a scores de distinta procedencia.
Los datos incorporados al estado deben admitir copia y checkpoint; no incluir
clientes HTTP, sesiones, generadores, conexiones ni el índice vectorial completo.

### Actualización del nodo que consume el grafo

| Aspecto | Requisito del adaptador |
|---|---|
| Firma interna | Callable síncrono: recibe `AgentState`, devuelve un `dict` parcial |
| Lectura | `user_message` y los campos de contexto acordados en la ficha |
| Escritura principal | `specialist_results[rol] = resultado_normalizado` |
| Conservación | Mantener resultados de otros roles; no sustituirlos por un dict de un solo rol |
| Traza opcional | Devolver solo eventos nuevos en `debug_trace`; el acumulador del estado los combina en LangGraph |
| Mutabilidad | No modificar el estado recibido ni colecciones de otros nodos |
| Finalización del rol | Registrar un resultado también en abstención o fallo técnico esperado |
| Campos ajenos | No escribir `approved`, `done`, decisiones del supervisor, contador, plan o respuesta final |

Patrón de actualización **ilustrativo**, no firma impuesta al especialista:

```python
# resultado ya normalizado y validado por el adaptador
return {
    "specialist_results": {
        **state.get("specialist_results", {}),
        rol: resultado,
    },
    "debug_trace": [
        f"{rol}: {resultado.status}",
    ],
}
```

El acumulador de `debug_trace` conserva los eventos de la conversación mientras
se reutiliza el mismo `thread_id`. Cada pedido añade una marca de inicio y
reinicia resultados, respuesta, plan, aprobación y contador. Un hilo nuevo
tiene una traza independiente. Esto cambia el comportamiento anterior, que
sustituía la traza por pedido. Ningún otro campo tiene acumulador.
`state_from_graph` conserva `deepcopy` para aislar estructuras anidadas; copia
una salida ya acumulada, sin volver a combinar eventos. Un `dict.update(...)`
de Python puro reemplaza la lista y no reproduce el acumulador de LangGraph.
El envoltorio de aplicar conserva los eventos nuevos del nodo y añade una sola
decisión HITL; el nodo inyectado debe dejar ese evento HITL al envoltorio.

El supervisor cuenta la presencia de la clave como intento completado. Un error
esperado no debe dejar esa clave ausente y provocar repeticiones. Una salida que
incumple el contrato debe producir un error de integración explícito; no ocultarlo
como abstención. Capturar las excepciones esperadas que especifique la ficha.

**Validación pendiente de implementar en cada adaptador:** las dataclasses no
validan tipos en ejecución y el grafo no filtra actualmente las actualizaciones
de los especialistas. Las restricciones de esta sección deben acreditarse con
pruebas del adaptador; no asumir que ya están garantizadas por el montaje.

### Decisiones que pueden requerir cambiar módulos comunes

| Diferencia recibida | Acción antes de integrar |
|---|---|
| Resultado real compatible pero con otros nombres | Mapeo en adaptador; conservar el formato externo |
| Fuentes o estados incompatibles con la propuesta | Proponer cambio en contracts/state y revisar síntesis y consumidores |
| Solo callable asíncrono | Acordar adaptación síncrona o cambio de alcance; no añadir `asyncio.run` dentro de un loop activo |
| Imagen, request_id o traza de tools necesarios | Definir campo, propietario, reset y consumo; no darlo por existente en AgentState |
| Especialista ya devuelve actualizaciones LangGraph | Revisar firma y campos; reutilizarlo si cumple el contrato interno |
| Nuevo rol o tool adicional | Acordar alcance y límites antes de cambiar rutas o registro |

## 5. Secuencia de integración por especialista

| Paso | Acción | Evidencia para pasar al siguiente |
|---|---|---|
| I1 · Recepción | Completar ficha y localizar el código real | Contrato, commit y tres ejemplos identificados |
| I2 · Acuerdo | Completar mapeo y resolver diferencias bloqueantes | Reglas de transformación y campos autorizados escritos |
| I3 · Adaptación | Implementar el nodo/adaptador en la ubicación acordada | Imports limpios; prueba sin UI; sin rehacer RAG |
| I4 · Prueba aislada | Ejecutar los escenarios A1–A5 | Resultados y comando reproducible |
| I5 · Grafo mixto | Inyectar un especialista real y dobles explícitos para el resto | Resultado real llega a síntesis; pausa HITL intacta |
| I6 · Integración conjunta | Inyectar ambos especialistas reales | Fuentes de ambos conservadas; sin sobreescrituras |
| I7 · Revisión | Abrir PR hacia develop y revisar consumidores | Contrato actualizado, pruebas, evidencias y revisión del último commit |

En I5 usar el constructor actual: `AgentService(documental_node=...,
instalaciones_node=..., sintetizar_node=..., aplicar_node=...)`. Crear el servicio
una vez y reutilizarlo. No introducir imports concretos en `graph.py`.
Un grafo mixto se identifica como prueba de integración; no como demo final real.

## 6. Escenarios de aceptación

Las pruebas del adaptador se ejecutan con ejemplos del contrato; la verificación
contra RAG/API reales se registra aparte. Las pruebas existentes del backend
usan dobles y no prueban aún los contratos externos.

| ID | Dado / cuando | Resultado exigido |
|---|---|---|
| A1 | Consulta válida con respuesta y fuentes reales | `ok`; respuesta y procedencia conservadas; datos reales llegan a síntesis |
| A2 | Consulta sin evidencia o sin coincidencias | `abstained`; limitación visible; rol registrado una sola vez; sin datos inventados |
| A3 | Excepción técnica documentada | `error` o fallback real identificado según acuerdo; origen/fecha preservados; sin ocultarlo como éxito normal |
| A4 | Estado con resultado del otro especialista | Su resultado no cambia; la entrada no se muta y las colecciones no se comparten accidentalmente |
| A5 | Entrada inválida o salida incompatible | Rechazo según ficha o error de integración explícito; no llamada incorrecta ni aprobación/cierre del pedido |
| A6 | Dos especialistas conectados | Ambas contribuciones y fuentes disponibles en el mismo pedido; supervisor no repite roles completados |
| A7 | Síntesis válida y llegada a aplicar | Plan y respuesta no vacíos; snapshot.next incluye aplicar; approved=None y done=False |
| A8 | Aprobar / rechazar con plan_id vigente | Aprobar: done=True; rechazar: done=False; mismo hilo; siguiente pedido con resultados limpios |
| A9 | Decisión repetida, plan antiguo u otro hilo | Sin segunda aplicación para repetición idéntica; plan antiguo y decisión ajena rechazados |
| A10 | Tool no permitida o límite alcanzado | Python bloquea/corta; traza documenta el resultado; no depende solo de instrucciones al modelo |
| A11 | Especialista/RAG desde una consola sin Streamlit | Consulta reproducible; indexado separado; sin secretos ni ajuste manual de sys.path |

Para cada escenario registrar: especialista, versión/commit, entrada, resultado
esperado, resultado observado, comando, fecha y tipo de evidencia (doble o real).
Los ejemplos se sanitizan antes de versionarlos. Usar una ubicación acordada en
`tests/` para fixtures y en `entregables/` para evidencia; no versionar índices pesados.

Comprobación de regresión del backend desde la raíz:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Pruebas actuales de referencia: [grafo](../../tests/test_sync_integration.py) y
[servicio](../../tests/test_agent_service.py). Los tests específicos del adaptador
se añaden al recibir cada interfaz. Registrar el número observado de pruebas,
no una cifra fija que se quede obsoleta.

## 7. Registro de decisiones y cierre de la PR

| Decisión | Especialista / versión | Desacuerdo | Acuerdo y motivo | Consumidores afectados | Revisor / estado |
|---|---|---|---|---|---|
| D-01 | Pendiente | Pendiente | Pendiente | Pendiente | Pendiente |

Antes de marcar un especialista como **integrado**:

- [ ] Ficha y ejemplos recibidos; versión y commit identificados.
- [ ] Mapeo completo y diferencias bloqueantes resueltas.
- [ ] Entradas/salidas validadas en el adaptador; fuentes y errores preservados.
- [ ] A1–A5 y escenarios de grafo aplicables verificados.
- [ ] Pruebas reales distinguidas de dobles; límites y allowlist acreditados.
- [ ] Dependencias, preparación y comando documentados.
- [ ] Contratos comunes actualizados cuando cambien; consumidores revisados.
- [ ] PR revisada hacia develop; integrar tras revisión del último commit.

El cierre de los dos especialistas no cierra todo el PB02: permanecen los
criterios del [seguimiento](seguimiento_pb02.md), incluidas CLI, Streamlit,
multimodal, informe y presentación. No aprobar el cambio de un contrato común
sin comprobar su efecto en síntesis, estado y presentación de fuentes.
