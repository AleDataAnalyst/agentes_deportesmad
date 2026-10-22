# Ejemplo de llamada y respuesta del nodo `instalaciones`

Documento de integración para el grafo de Alejandra. Muestra cómo se invoca el nodo y qué *patch* devuelve en cuatro escenarios: catálogo correcto, avisos correctos, error con *fallback* y error sin *fallback*.

## Contrato de entrada (AgentState mínimo)

El nodo solo lee `user_message`. El resto del `AgentState` puede estar vacío o contener datos de otros especialistas, que se conservan según el contrato del nodo.

```python
state = {
    "user_message": "¿hay avisos en el centro 114782?",
    "thread_id": "demo",
    "supervisor_decision": None,
    "specialist_results": {},  # Se conserva lo que haya
    "final_answer": "",
    "plan": [],
    "pending_action": None,
    "approved": None,
    "iterations": 0,
    "done": False,
    "debug_trace": ["inicio de pedido"],
}
```

## Ejemplo de llamada

```python
from agentes.nodes.instalaciones import nodo_instalaciones

patch = nodo_instalaciones(state)
```

## Escenario 1 — Modo catálogo (ok)

### Entrada

```python
state = {
    "user_message": "lista los centros deportivos",
    "specialist_results": {},
    "debug_trace": ["inicio de pedido"],
    # Resto de campos por defecto
}
```

**Llamada:** `nodo_instalaciones(state)` → internamente `consultar_instalaciones(modo="catalogo", centro_id=None)`.

### Respuesta (patch)

```python
{
    "specialist_results": {
        "instalaciones": ToolResult(
            status="ok",
            answer=(
                "Catálogo: 82 centros disponibles. Primeros: "
                "Centro Deportivo Municipal Alcántara (SALAMANCA), "
                "Centro Deportivo Municipal Alfredo Goyeneche (MONCLOA-ARAVACA), "
                "... (y 77 más)."
            ),
            evidence=[
                Evidence(
                    source="http://www.madrid.es/sites/v/index.jsp?...",
                    content="Centro Deportivo Municipal Alcántara (SALAMANCA)",
                    score=None,
                    metadata={"pk": "10183549", "distrito": "SALAMANCA"},
                ),
                # ... 81 más
            ],
            error=None,
            data={
                "modo": "catalogo",
                "origen": "api",
                "fuente": "200186-0-polideportivos-csv",
                "fecha_consulta": "2026-10-20T10:00:00+02:00",
                "fecha_captura_fallback": None,
                "advertencias": [],
                "n_resultados": 82,
                "datos_raw": [...],
            },
        )
    },
    "debug_trace": [
        "instalaciones: modo=catalogo centro_id=- status=ok n=82 origen=api"
    ],
}
```

## Escenario 2 — Modo avisos con PK (ok)

### Entrada

```python
state = {
    "user_message": "¿hay avisos en el centro 114782?",
    "specialist_results": {},
    "debug_trace": ["inicio de pedido"],
}
```

**Llamada:** `nodo_instalaciones(state)` → internamente `consultar_instalaciones(modo="avisos", centro_id="114782")`.

### Respuesta (patch)

```python
{
    "specialist_results": {
        "instalaciones": ToolResult(
            status="ok",
            answer=(
                "Avisos detectados (1): Aviso a usuarios/as A partir del día "
                "1 de julio de 2026, el centro deportivo permanecerá cerrado "
                "con motivo de la ejecución de obras de mejora en las "
                "instalaciones. La duración estimada de las mismas será de "
                "aproximadamente cinco meses. Disculpen las molestias."
            ),
            evidence=[
                Evidence(
                    source="http://www.madrid.es/sites/v/index.jsp?...",
                    content="Aviso a usuarios/as A partir del día 1 de julio...",
                    score=None,
                    metadata={
                        "centro_id": "114782",
                        "aviso_detectado": True,
                        "origen": "html",
                    },
                )
            ],
            error=None,
            data={
                "modo": "avisos",
                "origen": "html",
                "fuente": "http://www.madrid.es/sites/v/index.jsp?...",
                "fecha_consulta": "2026-10-20T10:00:00+02:00",
                "fecha_captura_fallback": None,
                "advertencias": [],
                "n_resultados": 1,
                "datos_raw": [
                    {
                        "centro_id": "114782",
                        "centro_nombre": "Centro Deportivo Municipal Alfredo Goyeneche",
                        "distrito": "MONCLOA-ARAVACA",
                        "url_ficha": "http://www.madrid.es/sites/v/index.jsp?...",
                        "aviso_detectado": True,
                        "texto_aviso": "Aviso a usuarios/as A partir del día 1 de julio...",
                        "origen": "html",
                        "fecha_consulta": "2026-10-20T10:00:00+02:00",
                        "advertencias": [],
                    }
                ],
            },
        )
    },
    "debug_trace": [
        "instalaciones: modo=avisos centro_id=114782 status=ok n=1 origen=html"
    ],
}
```

## Escenario 3 — Error con fallback

### Entrada

```python
state = {
    "user_message": "¿avisos en el centro 114782?",
    "specialist_results": {},
    "debug_trace": ["inicio de pedido"],
}
```

Supongamos que la ficha HTML falla (HTTP 403), pero el *fallback* del `2026-10-19` contiene información del centro.

### Respuesta (patch)

```python
{
    "specialist_results": {
        "instalaciones": ToolResult(
            status="ok",
            answer=(
                "Avisos detectados (1): Aviso a usuarios/as A partir del día "
                "1 de julio de 2026, el centro deportivo permanecerá cerrado... "
                "Advertencias: La consulta oficial falló: Error HTTP al consultar "
                "la ficha oficial: código 403. Se utiliza la captura del "
                "2026-10-19; el aviso puede haber cambiado desde entonces."
            ),
            evidence=[
                Evidence(
                    source="http://www.madrid.es/sites/v/index.jsp?...",
                    content="Aviso a usuarios/as A partir del día 1 de julio...",
                    score=None,
                    metadata={
                        "centro_id": "114782",
                        "aviso_detectado": True,
                        "origen": "fallback",
                    },
                )
            ],
            error=None,
            data={
                "modo": "avisos",
                "origen": "fallback",
                "fuente": "avisos_centros_2026-10-19.json",
                "fecha_consulta": "2026-10-20T10:00:00+02:00",
                "fecha_captura_fallback": "2026-10-19",
                "advertencias": [
                    "La consulta oficial falló: Error HTTP al consultar la ficha oficial: código 403.",
                    "Se utiliza la captura del 2026-10-19; el aviso puede haber cambiado desde entonces.",
                ],
                "n_resultados": 1,
                "datos_raw": [...],
            },
        )
    },
    "debug_trace": [
        "instalaciones: modo=avisos centro_id=114782 status=ok n=1 origen=fallback"
    ],
}
```

## Escenario 4 — Error sin fallback

### Entrada

Se utiliza la misma consulta del escenario 3, pero no hay un *fallback* disponible.

```python
state = {
    "user_message": "¿avisos en el centro 114782?",
    "specialist_results": {},
    "debug_trace": ["inicio de pedido"],
}
```

### Respuesta (patch)

```python
{
    "specialist_results": {
        "instalaciones": ToolResult(
            status="error",
            answer=(
                "No se han encontrado resultados en la consulta de avisos. "
                "Centro 114782: falló la consulta oficial (Error HTTP: código 403) "
                "y no hay un fallback utilizable (No hay capturas locales de avisos.)."
            ),
            evidence=[],
            error=(
                "Centro 114782: falló la consulta oficial (Error HTTP: código 403) "
                "y no hay un fallback utilizable (No hay capturas locales de avisos.)."
            ),
            data={
                "modo": "avisos",
                "origen": "html",
                "fuente": "Ficha oficial del centro",
                "fecha_consulta": "2026-10-20T10:00:00+02:00",
                "fecha_captura_fallback": None,
                "advertencias": [],
                "n_resultados": 0,
                "datos_raw": [],
            },
        )
    },
    "debug_trace": [
        "instalaciones: modo=avisos centro_id=114782 status=error n=0 origen=html error=Centro 114782: falló la consulta oficial..."
    ],
}
```

## Notas

- Los objetos `ToolResult` y `Evidence` representan las estructuras devueltas por el nodo; los ejemplos no son diccionarios JSON directamente serializables.
- Los valores abreviados con `...` son marcadores ilustrativos, no código Python ejecutable tal cual.
- Las fechas, los identificadores, el número de resultados y los textos de ejemplo deben contrastarse con los datos reales del servicio y del *fallback*.
