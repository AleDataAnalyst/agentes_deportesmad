# Contrato del especialista de instalaciones y avisos

**Proyecto:** Proyect-Break-2  
**Responsable:** Miguel López  
**Rama:** `feature/instalaciones-avisos`  
**Estado:** Contrato funcional acordado; pendiente de validación de compatibilidad con las interfaces compartidas.

## 1. Objetivo

Definir la entrada, la salida y el comportamiento del especialista de instalaciones y avisos municipales para integrarlo en el sistema multiagente de LangGraph.

La implementación cubre dos modos:

- `catalogo`: consulta el catálogo municipal de centros deportivos mediante CKAN.
- `avisos`: consulta la ficha HTML oficial de un centro y extrae de forma conservadora los bloques que siguen al encabezado `Aviso a usuarios/as`.

Si la fuente principal falla, se podrá utilizar un fallback local fechado, siempre que exista un conjunto de datos válido para la consulta.

La ocupación de instalaciones queda fuera del MVP.

## 2. Fuentes de datos

### 2.1. Catálogo CKAN

Endpoint:

`https://datos.madrid.es/api/3/action/datastore_search`

El catálogo debe normalizar cada registro a los siguientes campos:

| Campo | Tipo | Descripción |
|---|---|---|
| `pk` | `str` | Identificador del centro, procedente de `PK`. |
| `nombre` | `str` | Nombre del centro, procedente de `NOMBRE`. |
| `distrito` | `str` | Distrito municipal, procedente de `DISTRITO`. |
| `content_url` | `str` | URL de la ficha, procedente de `CONTENT-URL`. |

El fallback del catálogo corresponde a la captura del 13 de octubre de 2026 y debe documentar su fuente y fecha de captura.

### 2.2. Avisos HTML

La consulta recibe el identificador `centro_id`, correspondiente al `PK` del catálogo. La herramienta resuelve la URL de la ficha a partir del catálogo y consulta su HTML.

El parser debe:

1. Localizar el encabezado `Aviso a usuarios/as`, tolerando diferencias de mayúsculas y espacios.
2. Extraer el contenido asociado al encabezado.
3. Admitir varios bloques de aviso para un mismo centro.
4. Conservar el texto original sin interpretar fechas, duraciones ni vigencia.
5. Registrar advertencias si no puede determinarse el contenido.

La captura de referencia del 13/10/2026 identificó 12 centros con encabezados de aviso y 13 bloques en total. Esta cifra es una referencia histórica, no una garantía de que el contenido siga igual.

## 3. Contrato de entrada

La función pública de la herramienta tendrá la siguiente interfaz:

```python
def consultar_instalaciones(
    modo: Modo,
    centro_id: str | None = None,
) -> ToolResultInstalaciones:
    ...
```

Reglas:

- `modo="catalogo"` consulta el catálogo completo. `centro_id` no es necesario.
- `modo="avisos"` requiere `centro_id`.
- Si falta `centro_id` en modo `avisos`, se devuelve un error explícito.
- La función es síncrona y devuelve un resultado estructurado; no modifica directamente el estado del grafo.
- Las consultas HTTP deben tener timeout y un `User-Agent` identificable.

## 4. Tipos de datos

Los tipos de referencia son compatibles con Python 3.10 o superior.

```python
from typing import Literal, Optional, TypedDict

Modo = Literal["catalogo", "avisos"]
Origen = Literal["api", "html", "fallback"]
Deteccion = Optional[bool]


class ItemCatalogo(TypedDict):
    pk: str
    nombre: str
    distrito: str
    content_url: str


class BloqueAviso(TypedDict):
    centro_id: str
    centro_nombre: str
    distrito: str
    url_ficha: str
    aviso_detectado: Deteccion
    texto_aviso: Optional[str]
    origen: Literal["html", "fallback"]
    fecha_consulta: str
    advertencias: list[str]


class ToolResultInstalaciones(TypedDict):
    ok: bool
    modo: Modo
    datos: list[ItemCatalogo] | list[BloqueAviso]
    fuente: str
    origen: Origen
    fecha_consulta: str
    fecha_captura_fallback: Optional[str]
    advertencias: list[str]
    error: Optional[str]
```

### 4.1. Semántica de los campos

- `ok`: indica si la consulta devuelve un resultado utilizable. No garantiza que un centro esté abierto ni que un aviso continúe vigente.
- `modo`: modo solicitado.
- `datos`: lista de registros de catálogo o lista de bloques de aviso, según el modo.
- `fuente`: descripción de la fuente consultada o del fichero de fallback utilizado.
- `origen`: procedencia del resultado principal: `api`, `html` o `fallback`.
- `fecha_consulta`: fecha y hora de la consulta en formato ISO 8601.
- `fecha_captura_fallback`: fecha de la captura histórica, si se utiliza un fallback; en caso contrario, `None`.
- `advertencias`: lista de limitaciones, incidencias o avisos de antigüedad.
- `error`: `None` cuando el resultado es utilizable; mensaje explícito cuando no se puede obtener un resultado válido.

En modo `avisos`, `datos` puede contener cero, uno o varios bloques. Cada bloque conserva la procedencia y las advertencias específicas.

## 5. Reglas de detección de avisos

| Situación | `aviso_detectado` | `texto_aviso` |
|---|---|---|
| Se extrae contenido asociado al encabezado | `True` | Texto literal extraído. |
| La ficha se interpreta correctamente, pero no aparece el encabezado | `False` | `None`. |
| La ficha no se puede consultar o interpretar de forma fiable | `None` | `None`, salvo que exista contenido extraído de forma fiable. |

Cuando `aviso_detectado=False`, el bloque debe incluir la advertencia:

`no garantiza ausencia de incidencia`

La ausencia del encabezado no demuestra que no exista una incidencia. Tampoco debe sustituirse una consulta HTML válida sin encabezado por un aviso histórico.

Si hay varios bloques asociados al encabezado, se devuelve un bloque por cada aviso extraído.

## 6. Reglas de fallback

Los fallbacks son copias locales de datos reales capturados previamente, no respuestas inventadas ni mensajes genéricos de error.

Ficheros previstos:

- `data/fallbacks/catalogo_centros_2026-10-13.json`
- `data/fallbacks/avisos_2026-10-13.json`
- `data/fallbacks/README.md`

Cada captura debe documentar fuente, fecha de captura y contenido incluido.

Reglas:

1. Si la fuente principal falla, se intenta recuperar un fallback válido para el modo y, en modo `avisos`, para el centro solicitado.
2. Cuando se utiliza el fallback, `origen` debe ser `fallback` y `fecha_captura_fallback` debe estar informada.
3. Se añade una advertencia que identifica la antigüedad y la causa del fallback.
4. Si no existe un fallback válido, se devuelve `ok=False`, `datos=[]` y un mensaje en `error`.
5. Una respuesta válida sin resultados no se considera automáticamente un fallo de conexión.
6. Un catálogo vacío devuelto correctamente por CKAN puede producir `ok=True`, `datos=[]` y una advertencia.
7. Una ficha HTML consultada e interpretada correctamente sin el encabezado de avisos produce `aviso_detectado=False`; no se reemplaza silenciosamente por un aviso histórico.
8. Los datos históricos no se presentan como confirmación de la situación actual.

## 7. Ejemplos del contrato

Los siguientes ejemplos son ilustrativos. Los identificadores y contenidos genéricos no representan registros municipales verificados.

### Ejemplo 1. Catálogo correcto

```json
{
  "ok": true,
  "modo": "catalogo",
  "datos": [
    {
      "pk": "EJEMPLO-001",
      "nombre": "Centro de ejemplo",
      "distrito": "Distrito de ejemplo",
      "content_url": "https://example.org/centro"
    }
  ],
  "fuente": "CKAN - catálogo municipal de centros deportivos",
  "origen": "api",
  "fecha_consulta": "2026-10-15T10:00:00+02:00",
  "fecha_captura_fallback": null,
  "advertencias": [],
  "error": null
}
```

### Ejemplo 2. Aviso detectado

```json
{
  "ok": true,
  "modo": "avisos",
  "datos": [
    {
      "centro_id": "EJEMPLO-001",
      "centro_nombre": "Centro de ejemplo",
      "distrito": "Distrito de ejemplo",
      "url_ficha": "https://example.org/centro",
      "aviso_detectado": true,
      "texto_aviso": "Texto literal de ejemplo extraído de la ficha.",
      "origen": "html",
      "fecha_consulta": "2026-10-15T10:00:00+02:00",
      "advertencias": []
    }
  ],
  "fuente": "Ficha HTML oficial del centro",
  "origen": "html",
  "fecha_consulta": "2026-10-15T10:00:00+02:00",
  "fecha_captura_fallback": null,
  "advertencias": [],
  "error": null
}
```

### Ejemplo 3. Aviso no detectado

```json
{
  "ok": true,
  "modo": "avisos",
  "datos": [
    {
      "centro_id": "EJEMPLO-001",
      "centro_nombre": "Centro de ejemplo",
      "distrito": "Distrito de ejemplo",
      "url_ficha": "https://example.org/centro",
      "aviso_detectado": false,
      "texto_aviso": null,
      "origen": "html",
      "fecha_consulta": "2026-10-15T10:00:00+02:00",
      "advertencias": [
        "no garantiza ausencia de incidencia"
      ]
    }
  ],
  "fuente": "Ficha HTML oficial del centro",
  "origen": "html",
  "fecha_consulta": "2026-10-15T10:00:00+02:00",
  "fecha_captura_fallback": null,
  "advertencias": [
    "no garantiza ausencia de incidencia"
  ],
  "error": null
}
```

### Ejemplo 4. Fallback utilizado

```json
{
  "ok": true,
  "modo": "avisos",
  "datos": [
    {
      "centro_id": "EJEMPLO-001",
      "centro_nombre": "Centro de ejemplo",
      "distrito": "Distrito de ejemplo",
      "url_ficha": "https://example.org/centro",
      "aviso_detectado": true,
      "texto_aviso": "Texto histórico de ejemplo conservado en la captura.",
      "origen": "fallback",
      "fecha_consulta": "2026-10-15T10:00:00+02:00",
      "advertencias": [
        "Datos históricos: no confirman la situación actual."
      ]
    }
  ],
  "fuente": "data/fallbacks/avisos_2026-10-13.json",
  "origen": "fallback",
  "fecha_consulta": "2026-10-15T10:00:00+02:00",
  "fecha_captura_fallback": "2026-10-13",
  "advertencias": [
    "Consulta HTML fallida; se ha utilizado el fallback histórico.",
    "Datos históricos: no confirman la situación actual."
  ],
  "error": null
}
```

### Ejemplo 5. Error sin fallback válido

```json
{
  "ok": false,
  "modo": "avisos",
  "datos": [],
  "fuente": "Ficha HTML oficial del centro",
  "origen": "html",
  "fecha_consulta": "2026-10-15T10:00:00+02:00",
  "fecha_captura_fallback": null,
  "advertencias": [
    "No se ha encontrado un fallback válido para el centro solicitado."
  ],
  "error": "No ha sido posible consultar la ficha ni recuperar un fallback válido."
}
```

## 8. Contrato del nodo LangGraph

Archivo previsto: `agentes/nodes/instalaciones.py`.

El nodo:

1. Recibe el `AgentState` compartido.
2. Obtiene los parámetros necesarios para ejecutar la consulta.
3. Llama a `consultar_instalaciones()`.
4. Añade el resultado en `specialist_results["instalaciones"]`.
5. Conserva los resultados de los demás especialistas.
6. Devuelve únicamente los eventos nuevos en `debug_trace`.
7. Preserva la fuente, las fechas, las advertencias y los errores del resultado de la herramienta.

El nodo es síncrono y devuelve un diccionario parcial compatible con el estado compartido. La estructura exacta de lectura y actualización del estado debe ajustarse a las interfaces reales de `AgentState`, `contracts.py` y al contrato común validado por el equipo.

## 9. Pruebas aisladas requeridas

Archivo previsto: `tests/test_tools.py`.

Como mínimo, se probarán:

1. Consulta CKAN correcta.
2. Catálogo válido sin registros.
3. Aviso HTML detectado.
4. Ficha válida sin encabezado de aviso.
5. Error HTTP.
6. Error de conexión.
7. HTML inesperado o extracción no fiable.
8. Fallback utilizado con fecha y advertencia.
9. Ausencia de fallback válido.
10. Conservación literal de fechas y textos ambiguos.

Las pruebas deben evitar depender de la disponibilidad real de Internet: se utilizarán respuestas simuladas cuando corresponda.

## 10. Límites de integración

Este contrato no autoriza a modificar unilateralmente los siguientes archivos compartidos:

- `agentes/contracts.py`
- `agentes/state.py`
- `agentes/tools/registry.py`

Cualquier ajuste necesario se coordinará con Héctor y Alejandra antes de integrarlo.

La integración final requiere registrar la herramienta según la allowlist del proyecto y conectar el nodo al grafo existente.

## 11. Criterios de aceptación

- [ ] Contrato de entrada y salida documentado.
- [ ] Tipos y cinco ejemplos definidos.
- [ ] Catálogo CKAN normalizado.
- [ ] Parser HTML conservador.
- [ ] Fallbacks fechados, documentados y verificables.
- [ ] Al menos diez casos de prueba aislada.
- [ ] Nodo compatible con el estado compartido.
- [ ] Resultados, fuentes y trazas conservados.
- [ ] Integración revisada por el equipo antes de modificar contratos compartidos.
