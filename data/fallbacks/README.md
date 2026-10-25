# Capturas locales de fallback

Datos reales capturados de fuentes oficiales del Ayuntamiento de Madrid.
Se usan cuando la API o la web no están disponibles. **Nunca sustituyen
silenciosamente una consulta válida sin resultados.**

## catalogo_centros_2026-10-16.json

- **Fuente:** CKAN `datastore_search`, recurso `200186-0-polideportivos-csv`.
- **Endpoint:** `https://datos.madrid.es/id/api/3/action/datastore_search`
- **Fecha de captura:** 2026-10-16
- **Contenido:** 82 centros con `pk`, `nombre`, `distrito`, `content_url`.
- **Uso:** fallback del modo `catalogo` cuando CKAN falla.

## avisos_centros_2026-10-19.json

- **Fuente:** fichas oficiales `www.madrid.es` (HTML).
- **Fecha de captura:** 2026-10-19
- **Contenido:** 82 centros consultados.
  - 12 con `aviso_detectado=true` (coincide con el handoff del 13/10/2026).
  - 70 con `aviso_detectado=null` (`no_verificable`: la ficha respondió pero
    no se encontró el `modal-alert` con título "Aviso a usuarios/as").
  - 0 con `aviso_detectado=false` (el parser no puede confirmar ausencia).
- **Uso:** fallback del modo `avisos` cuando la consulta HTML falla.

### Limitaciones

- Un `no_verificable` **no significa que no haya incidencia**.
- La ausencia del encabezado **no confirma** que el centro esté operativo.
- Las fechas de los avisos pueden estar en el pasado o ser ambiguas
  ("hasta nuevo aviso", sin año). El texto se conserva literal, sin
  interpretar.
- Las capturas **no confirman** disponibilidad de plazas ni reservas.
- Regenerar con: `python -m scripts.generar_fallback_catalogo` y
  `python -m scripts.generar_fallback_avisos`.
