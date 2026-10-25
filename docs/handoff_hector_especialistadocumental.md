# Handoff: Especialista documental y multimodal

**Fecha:** 2026-10-22  
**Autor/a:** Héctor González Lebredo   
**Rama / PR:** `feature/especialista-documental` a `develop`  
**Estado:** borrador / ~listo para revisión~ / ~aceptado~

## 1. Objetivo

Implementar el especialista documental con funciones OCR y capacidad multimodal con descripción de imagen, con el objetivo de responder a consultas sobre el Deporte Municipal del Ayuntamiento de Madrid, basado en documentación que incorpora centros, horarios, características, competiciones, instalaciones perpétuas y estación estival, ...entre otros.

El módulo debe devolver información trazable desde el catálogo municipal y las fichas oficiales, declarando abstención explícita ante error o limitación cuando no se puede verificar la información basada en los documentos curados para el consumo del especialista.

pedido → supervisor → `instalaciones` → síntesis → HITL → aplicar

## 2. Alcance implementado

| Componente | Estado | Archivos principales | Comprobado con |
|---|---|---|---|
| Nodo de especialista | Implementado | `agentes/nodes/documental` | pytest / demo / prueba manual |
| Indexación del catálogo | Implementado | `rag/pipeline` | pytest / demo / prueba manual |
| 
| Visión | Parcial | `...` | Qué falta exactamente |

No mezcles aquí lo que está hecho con lo que está previsto.

## 3. Contrato expuesto

Define exactamente qué recibe y qué devuelve tu módulo:

- Entrada: campos, tipos, validaciones y ejemplos.
- Salida: `ToolResult`, fuentes, errores, abstención, fallback y trazas.
- Efectos: qué escribe, qué no modifica y qué no debe hacer.
- Errores: códigos, condiciones y comportamiento esperado.

Ejemplo:

```python
ToolResult(
    ok=True,
    data={...},
    sources=[...],
    abstained=False,
    error=None,
)
```

## 4. Puntos de conexión

Indica el punto exacto donde otra persona debe enchufar tu trabajo:

| Consumidor | Punto de integración | Qué debe hacer |
|---|---|---|
| Alejandra / runtime | `crear_servicio_real()` | Sustituir el stub por la operación pública |
| David / Streamlit | `AgentService` | Consumir el mismo `thread_id` y `plan_id` |
| Héctor / RAG | Adaptador documental | Entregar índice compatible y consulta de aceptación |

## 5. Pendientes y criterio de cierre

| Pendiente | Responsable | Criterio de aceptación |
|---|---|---|
| Operación pública de instalaciones | Miguel | Devuelve `ToolResult` real con fuentes, error, abstención y fallback fechado |
| Índice RAG reproducible | Héctor | Consulta con fuente esperada, abstención y fallo controlado verificados |
| Integración real en Streamlit | David | Sin fallback automático, HITL funcional y errores acotados |

No pongas “terminar el módulo”; define una condición verificable. El handoff existente hace bien esto al exigir, por ejemplo, que un error o una demo no cuenten como aceptación real. [28]

## 6. Instrucciones de ejecución

Incluye solo comandos reproducibles:

```console
source .venv/bin/activate
python -B -m pytest -q -p no:cacheprovider \
  tests/test_tool_rag.py \
  tests/test_rag_error_boundary.py \
  tests/test_node_documental.py \
  tests/test_documental_adapter.py
```

Añade variables de entorno necesarias **sin valores sensibles**, referenciando `.env.example`.

## 7. Evidencias y límites

- Comandos ejecutados y resultado.
- Tests pasados, con fecha y alcance.
- Qué **no** valida esa evidencia.
- Limitaciones conocidas: sin persistencia durable, sin router LLM, sin instalaciones reales, etc.

### Limpieza y cobertura de pruebas — 25/10/2026

Se revisó la carpeta `tests/` para eliminar duplicidades y dejar clara la cobertura del especialista documental. La limpieza no modifica el contrato público de la tool RAG ni el comportamiento del nodo documental.

#### Decisión de limpieza

- Se elimina `tests/test_tools.py` porque duplica la cobertura de la tool RAG ya incluida en `tests/test_tool_rag.py`: contrato de salida, consulta vacía, error interno y evaluación contra el índice. 
- Se conserva `tests/test_rag_error_boundary.py`, reducido a `TimeoutError` y `ConnectionError`. Estos casos comprueban que un fallo de red o timeout se normaliza como `error`, sin lanzar excepción, sin devolver respuesta y sin confundirse con una abstención.
- El caso genérico `RuntimeError` permanece en `tests/test_tool_rag.py::test_error_interno_no_lanza`, evitando duplicarlo.
- `tests/test_tool_rag.py` se mantiene como única suite principal de la tool RAG: valida el contrato `respuesta`, `fuentes`, `abstained` y `error`; la consulta vacía; el fallo interno; el diagnóstico opcional y la evaluación con índice cuando está disponible.

#### Cobertura por capas

| Capa | Archivo de prueba | Alcance |
|---|---|---|
| Tool RAG | `tests/test_tool_rag.py` | Contrato público, consulta vacía, fallo interno, diagnóstico opcional y evaluación con índice cuando existe |
| Frontera de errores RAG | `tests/test_rag_error_boundary.py` | Normalización de `TimeoutError` y `ConnectionError` como error controlado |
| Nodo documental | `tests/test_node_documental.py` | Contrato del nodo, fuentes, abstención, presupuesto de tools, contexto permitido y error de tool |
| Adaptador documental | `tests/test_documental_adapter.py` | Conversión del sobre documental a `ToolResult`, validación de `request_id`, aislamiento del estado y opciones |
| Integración simulada | `tests/test_golden_graph.py`, `tests/test_export_evidence.py` | Recorridos completos con especialistas dobles; no validan RAG ni visión reales |

#### Comprobación reproducible

```console
python -B -m pytest -q -p no:cacheprovider \
  tests/test_tool_rag.py \
  tests/test_rag_error_boundary.py \
  tests/test_node_documental.py \
  tests/test_documental_adapter.py
```

#### Evidencia obtenida

- La tool RAG devuelve un diccionario controlado con `respuesta`, `fuentes`, `abstained` y `error`.
- Los fallos técnicos se representan como `error`; no se convierten en respuesta válida ni en abstención.
- El nodo documental conserva fuentes, abstención, limitaciones y eventos, actualizando únicamente su campo autorizado del estado.
- El adaptador documental valida el sobre recibido, comprueba la coincidencia de `request_id` y lo convierte en un `ToolResult` para el grafo.

#### Límites de esta evidencia

- Estas pruebas usan dobles, fixtures o simulaciones; no acreditan recuperación real, generación con LLM ni calidad semántica sobre el corpus municipal.
- No validan un índice Chroma poblado ni compatible con la configuración de embeddings empleada.
- La visión multimodal no dispone todavía de una suite dedicada. El caso de imagen no disponible está cubierto en `tests/test_node_documental.py`.
- Falta `tests/test_tool_vision.py` para validar imagen válida, imagen inexistente, formato no soportado y contenido ilegible.
- La eliminación de `tests/test_tools.py` no reduce la cobertura efectiva:
  sus casos relevantes ya están representados en `tests/test_tool_rag.py`.

## 8. Decisiones abiertas

| Decisión | Opciones | Impacto | Responsable de decidir |
|---|---|---|---|
| Renombrar `specialist` a `next_node` | Mantener / renombrar | Contrato y consumidores | Equipo |
| Historial conversacional en estado | Cliente / estado común | CLI y Streamlit | Equipo |

## 9. Riesgos y no hacer

- No aprobar automáticamente un plan HITL.
- No convertir un error en evidencia.
- No activar demo como fallback de un modo real.
- No subir `.env`, claves, índices ni volcados completos de estado.
- No cambiar contratos sin revisión de consumidores.

## 10. Checklist de aceptación

- [ ] El módulo se ejecuta con los comandos documentados.
- [ ] El contrato de entrada/salida está definido.
- [ ] Hay pruebas específicas de la integración.
- [ ] Se separan evidencias simuladas y reales.
- [ ] Los errores y abstenciones se propagan correctamente.
- [ ] El README y el handoff quedan actualizados.
- [ ] La cobertura de RAG está consolidada en `tests/test_tool_rag.py` y la frontera de errores de red/timeout en `tests/test_rag_error_boundary.py`.
- [ ] `tests/test_tools.py` ha sido eliminado o justificado explícitamente si se conserva.
- [ ] La suite de visión dedicada (`tests/test_tool_vision.py`) está implementada o registrada como pendiente.