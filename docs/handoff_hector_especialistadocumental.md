# Handoff: Especialista documental y multimodal

- **Fecha:** 2026-10-22
- **Autor/a:** Héctor González Lebredo
- **Rama / PR:** `feature/especialista-documental` a `develop`
- **Estado:** borrador / ~listo para revisión~ / ~aceptado~

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

Esto es especialmente importante en PB02: el README distingue claramente el backend, el RAG documental, instalaciones y el cliente Streamlit. [48]

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
python -B main.py --modo demo
python -B -m pytest -q -p no:cacheprovider tests/test_runtime.py
```

Añade variables de entorno necesarias **sin valores sensibles**, referenciando `.env.example`.

## 7. Evidencias y límites

- Comandos ejecutados y resultado.
- Tests pasados, con fecha y alcance.
- Qué **no** valida esa evidencia.
- Limitaciones conocidas: sin persistencia durable, sin router LLM, sin instalaciones reales, etc.

El README ya establece una distinción importante: las pruebas con dobles no acreditan RAG, instalaciones ni servicios externos reales. [48]

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
